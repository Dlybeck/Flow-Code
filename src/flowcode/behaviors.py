"""Deterministic, source-grounded behavior layers for progressive exploration.

The execution IR remains the evidence graph.  This module projects it into
focused layers: a source function is the local root, its direct calls are nodes,
callable nodes with their own layers are seeds, and exits from the local root are
leaves.  A callee with no outgoing calls is therefore an ordinary node in its
parent layer, not a fabricated end of the whole behavior.
"""

from __future__ import annotations

import ast
import hashlib
import re
import textwrap
from collections import defaultdict, deque
from typing import Any


def _stable_id(*parts: object) -> str:
    body = "\0".join(str(part) for part in parts)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _humanize(value: str) -> str:
    value = value.rsplit(".", 1)[-1]
    value = re.sub(r"\$callback_\d+(?:_\d+)*", "callback", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:1].upper() + value[1:] if value else "Step"


def _display_label(node: dict[str, Any]) -> str:
    value = str(node.get("displayName") or node.get("label") or node.get("qname") or "")
    routes = node.get("routes") or []
    if routes and _humanize(value).lower() in {"endpoint", "handler", "route", "test"}:
        route = routes[0]
        method = str(route.get("method") or "").upper()
        path = str(route.get("path") or "")
        if method and path:
            parts = [_humanize(part) for part in path.strip("/").split("/") if part]
            destination = " › ".join(parts[-2:]) if parts else "Home"
            return destination if method == "GET" else f"{method} · {destination}"
    if re.match(r"^(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/", value):
        return value
    return _humanize(value)


def _python_return_label(value: ast.AST | None) -> str:
    if value is None or isinstance(value, ast.Constant) and value.value is None:
        return "Complete"
    if isinstance(value, ast.Name):
        return f"Return {_humanize(value.id)}"
    if isinstance(value, ast.Attribute):
        return f"Return {_humanize(value.attr)}"
    if isinstance(value, ast.Call):
        function = value.func
        if isinstance(function, ast.Name):
            return f"Return {_humanize(function.id)}"
        if isinstance(function, ast.Attribute):
            return f"Return {_humanize(function.attr)}"
    if isinstance(value, ast.Await):
        return _python_return_label(value.value)
    if isinstance(value, (ast.Dict, ast.List, ast.Set, ast.Tuple)):
        return "Return data"
    return "Return result"


class _PythonExitVisitor(ast.NodeVisitor):
    """Collect exits in one function without descending into nested functions."""

    def __init__(self) -> None:
        self.exits: list[dict[str, Any]] = []
        self._entered = False

    def _visit_function(self, node: ast.AST) -> None:
        if self._entered:
            return
        self._entered = True
        for statement in getattr(node, "body", []):
            self.visit(statement)

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function
    visit_Lambda = _visit_function

    def visit_Return(self, node: ast.Return) -> None:
        self.exits.append(
            {
                "kind": "return",
                "line_offset": int(node.lineno) - 1,
                "label": _python_return_label(node.value),
                "exceptional": False,
            }
        )

    def visit_Raise(self, node: ast.Raise) -> None:
        label = "Raise error"
        if isinstance(node.exc, ast.Call):
            if isinstance(node.exc.func, ast.Name):
                label = f"Raise {_humanize(node.exc.func.id)}"
            elif isinstance(node.exc.func, ast.Attribute):
                label = f"Raise {_humanize(node.exc.func.attr)}"
        elif isinstance(node.exc, ast.Name):
            label = f"Raise {_humanize(node.exc.id)}"
        self.exits.append(
            {
                "kind": "raise",
                "line_offset": int(node.lineno) - 1,
                "label": label,
                "exceptional": True,
            }
        )


_RETURN_PATTERN = re.compile(r"^\s*(?:return\b(?P<return>.*)|throw\b(?P<throw>.*))")


def _tree_sitter_exit_sites(source: str, language: str) -> list[dict[str, Any]] | None:
    """Collect exits while pruning nested functions when a grammar is available."""

    try:
        if language in {"javascript", "typescript"}:
            from flowcode.browser_syntax import FUNCTION_EXPRESSIONS
            from flowcode.execution_ir.typescript_from_raw import _get_parser

            parser = _get_parser()
            function_types = set(FUNCTION_EXPRESSIONS) | {
                "function_declaration",
                "generator_function_declaration",
                "method_definition",
            }
            candidates = [source, f"class FlowCodeExitProbe {{{source}}}"]
        else:
            from flowcode.treesitter_indexer import LANGUAGE_SPECS, _parser

            spec = LANGUAGE_SPECS.get(language)
            if spec is None:
                return None
            parser = _parser(spec)
            function_types = set(spec.function_types)
            candidates = [source]
            if language in {"java", "csharp"}:
                candidates.append(f"class FlowCodeExitProbe {{{source}}}")
    except ImportError:
        return None

    target = None
    for candidate in candidates:
        tree = parser.parse(candidate.encode())
        pending = [tree.root_node]
        while pending:
            current = pending.pop()
            if current.type in function_types:
                target = current
                break
            pending.extend(reversed(current.named_children))
        if target is not None:
            break
    if target is None:
        return None

    found: list[dict[str, Any]] = []

    def visit(node: Any, *, root: bool = False) -> None:
        if not root and node.type in function_types:
            return
        if node.type in {"return_statement", "throw_statement"}:
            exceptional = node.type == "throw_statement"
            found.append(
                {
                    "kind": "throw" if exceptional else "return",
                    "line_offset": int(node.start_point[0]),
                    "label": "Throw error" if exceptional else "Return result",
                    "exceptional": exceptional,
                }
            )
            return
        for child in node.named_children:
            visit(child)

    visit(target, root=True)
    return found


def extract_exit_sites(
    source: str,
    *,
    language: str,
    source_node_id: str,
    location: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return portable exit evidence without exporting source snippets.

    Python uses its AST.  Existing tree-sitter languages use conservative
    return/throw line recognition inside the already bounded function source.
    Languages without an explicit recognized exit receive a local completion
    boundary at the function's final line.
    """

    start = int(location.get("start_line") or 1)
    found: list[dict[str, Any]] = []
    if language == "python":
        try:
            tree = ast.parse(textwrap.dedent(source))
        except SyntaxError:
            tree = None
        if tree is not None:
            visitor = _PythonExitVisitor()
            visitor.visit(tree)
            found = visitor.exits
    else:
        parsed = _tree_sitter_exit_sites(source, language)
        if parsed is not None:
            found = parsed
        else:
            for offset, line in enumerate(source.splitlines()):
                match = _RETURN_PATTERN.match(line)
                if not match:
                    continue
                exceptional = match.group("throw") is not None
                found.append(
                    {
                        "kind": "throw" if exceptional else "return",
                        "line_offset": offset,
                        "label": "Throw error" if exceptional else "Return result",
                        "exceptional": exceptional,
                    }
                )

    if not any(not item["exceptional"] for item in found):
        found.append(
            {
                "kind": "complete",
                "line_offset": max(0, int(location.get("end_line") or start) - start),
                "label": "May complete",
                "exceptional": False,
                "inferred": True,
            }
        )

    rows = []
    for ordinal, item in enumerate(
        sorted(found, key=lambda row: (row["line_offset"], row["kind"], row["label"]))
    ):
        line = start + item["line_offset"]
        rows.append(
            {
                "id": f"exit:{_stable_id(source_node_id, line, item['kind'], ordinal)}",
                "kind": item["kind"],
                "label": item["label"],
                "exceptional": item["exceptional"],
                "inferred": bool(item.get("inferred")),
                "location": {
                    "path": location.get("path", ""),
                    "start_line": line,
                    "end_line": line,
                },
            }
        )
    return rows


def _source_reference(node: dict[str, Any]) -> dict[str, Any]:
    return {"node_id": node["id"], "location": dict(node.get("location", {}))}


def _exit_rank(exit_site: dict[str, Any], strategy: str) -> tuple[float, str]:
    normal = 1.0 if not exit_site.get("exceptional") else 0.15
    project = max(0.0, float(exit_site.get("project_similarity", 0.0)))
    local = max(0.0, float(exit_site.get("local_similarity", 0.0)))
    if strategy == "project":
        score = 0.72 * project + 0.28 * normal
    elif strategy == "local":
        score = 0.72 * local + 0.28 * normal
    elif strategy == "hybrid":
        score = 0.5 * local + 0.22 * project + 0.28 * normal
    else:
        raise ValueError(f"Unknown leaf ranking strategy: {strategy}")
    return score, exit_site["id"]


def _reachable(roots: list[str], children: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    pending = deque(roots)
    while pending:
        node = pending.popleft()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(sorted(children.get(node, set()) - seen))
    return seen


def _behavior_rank(
    node: dict[str, Any], children: dict[str, set[str]], total: int
) -> tuple[float, dict[str, float]]:
    evidence = set(node.get("entry_evidence", []))
    evidence_bonus = 0.0
    if evidence & {"configured_entry", "explicit_entry"}:
        evidence_bonus = 0.5
    elif evidence & {"declared_route", "route_registration_candidate"}:
        evidence_bonus = 0.32
    elif evidence & {
        "conventional_main",
        "main_label",
        "application_factory",
        "app_factory_candidate",
        "package_api_candidate",
    }:
        evidence_bonus = 0.22
    elif "event_listener_callback" in evidence:
        evidence_bonus = -0.2
    elif "module_initialization_candidate" in evidence:
        evidence_bonus = -0.08
    label = str(node.get("label", "")).lower()
    generic_penalty = (
        -0.18 if "$callback" in label or "callback · line" in label else 0.0
    )
    reach = len(_reachable([node["id"]], children)) / max(1, total)
    structure = min(0.16, 0.04 * len(children.get(node["id"], set())))
    score = float(node.get("importance", node.get("score", node.get("criticality", 0))))
    total_score = score + evidence_bonus + generic_penalty + 0.12 * reach + structure
    return total_score, {
        "semantic": score,
        "entry_evidence": evidence_bonus,
        "generic_penalty": generic_penalty,
        "reachable_fraction": reach,
        "direct_structure": structure,
    }


def build_behavior_map(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    entrypoints: list[str],
    *,
    leaf_ranking: str = "hybrid",
    primary_limit: int = 6,
) -> dict[str, Any]:
    """Project source functions into recursively focused behavior layers."""

    by_id = {node["id"]: node for node in nodes if node.get("id")}
    internal = [
        edge
        for edge in edges
        if edge.get("from") in by_id
        and edge.get("to") in by_id
        and edge.get("kind", "calls") == "calls"
    ]
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    children: dict[str, set[str]] = defaultdict(set)
    callers: dict[str, set[str]] = defaultdict(set)
    for edge in internal:
        outgoing[edge["from"]].append(edge)
        children[edge["from"]].add(edge["to"])
        callers[edge["to"]].add(edge["from"])
    for records in outgoing.values():
        records.sort(
            key=lambda edge: (
                int(edge.get("callsite", {}).get("line") or 0),
                edge["to"],
                edge.get("confidence", "unknown"),
            )
        )

    roots = [node for node in dict.fromkeys(entrypoints) if node in by_id]
    if not roots:
        roots = sorted(
            (node for node in by_id if not callers[node]),
            key=lambda node: (-float(by_id[node].get("score", 0)), node),
        )
    reachable = _reachable(roots, children)
    layer_ids = {node: f"layer:{_stable_id(node)}" for node in by_id}
    layers: dict[str, dict[str, Any]] = {}

    for source_id, source in sorted(by_id.items()):
        layer_id = layer_ids[source_id]
        root_id = f"root:{_stable_id(source_id)}"
        root = {
            "id": root_id,
            "kind": "root",
            "label": _display_label(source),
            "source_refs": [_source_reference(source)],
        }
        view_nodes = [root]
        events: list[dict[str, Any]] = []
        for ordinal, edge in enumerate(outgoing.get(source_id, [])):
            target = by_id[edge["to"]]
            line = int(edge.get("callsite", {}).get("line") or 0)
            occurrence_id = f"call:{_stable_id(source_id, edge['to'], line, ordinal)}"
            recursive = edge["to"] == source_id
            seed = bool(outgoing.get(edge["to"])) and not recursive
            occurrence = {
                "id": occurrence_id,
                "kind": "seed" if seed else "node",
                "label": _display_label(target),
                "source_refs": [_source_reference(target)],
                "callsite": {
                    "path": source.get("location", {}).get("path", ""),
                    "line": line,
                    "confidence": edge.get("confidence", "unknown"),
                },
                **({"recursive": True} if recursive else {}),
                **({"child_layer_id": layer_ids[edge["to"]]} if seed else {}),
            }
            view_nodes.append(occurrence)
            events.append({"line": line, "node": occurrence})

        exits = [dict(exit_site) for exit_site in source.get("exits", [])]
        if not exits:
            exits = extract_exit_sites(
                "",
                language=source.get("language", ""),
                source_node_id=source_id,
                location=source.get("location", {}),
            )
        ordered_exits: dict[str, list[str]] = {}
        for strategy in ("project", "local", "hybrid"):
            ordered_exits[strategy] = [
                row["id"]
                for row in sorted(
                    exits, key=lambda row: _exit_rank(row, strategy), reverse=True
                )
            ]
        for exit_site in exits:
            leaf = {
                "id": exit_site["id"],
                "kind": "leaf",
                "label": exit_site["label"],
                "exceptional": bool(exit_site.get("exceptional")),
                "inferred": bool(exit_site.get("inferred")),
                "source_refs": [
                    {"node_id": source_id, "location": dict(exit_site["location"])}
                ],
                "project_similarity": float(exit_site.get("project_similarity", 0)),
                "local_similarity": float(exit_site.get("local_similarity", 0)),
            }
            view_nodes.append(leaf)
            events.append(
                {"line": int(exit_site["location"]["start_line"]), "node": leaf}
            )

        calls = sorted(
            (event for event in events if event["node"]["kind"] != "leaf"),
            key=lambda event: (event["line"], event["node"]["id"]),
        )
        leaves = [event for event in events if event["node"]["kind"] == "leaf"]
        view_edges: list[dict[str, Any]] = []
        previous = root_id
        for event in calls:
            view_edges.append(
                {
                    "from": previous,
                    "to": event["node"]["id"],
                    "kind": "source_order",
                    "confidence": "lexical",
                }
            )
            previous = event["node"]["id"]
        for event in leaves:
            predecessor = root_id
            preceding = [call for call in calls if call["line"] <= event["line"]]
            if preceding:
                predecessor = preceding[-1]["node"]["id"]
            view_edges.append(
                {
                    "from": predecessor,
                    "to": event["node"]["id"],
                    "kind": "completion",
                    "confidence": (
                        "inferred" if event["node"].get("inferred") else "structural"
                    ),
                }
            )

        layers[layer_id] = {
            "id": layer_id,
            "source_node_id": source_id,
            "root_id": root_id,
            "nodes": view_nodes,
            "edges": view_edges,
            "leaf_ids": ordered_exits[leaf_ranking],
            "leaf_orders": ordered_exits,
            "ordering": {
                "method": "callsite source order with structural exits",
                "runtime_guarantee": False,
            },
        }

    behaviors = []
    for root in roots:
        node = by_id[root]
        layer = layers[layer_ids[root]]
        rank, rank_signals = _behavior_rank(node, children, len(by_id))
        behaviors.append(
            {
                "id": f"behavior:{_stable_id(root)}",
                "label": _display_label(node),
                "root_node_id": root,
                "root_layer_id": layer["id"],
                "leaf_ids": list(layer["leaf_ids"]),
                "score": float(
                    node.get(
                        "importance",
                        node.get("score", node.get("criticality", 0)),
                    )
                ),
                "rank": rank,
                "rank_signals": rank_signals,
                "entry_evidence": list(node.get("entry_evidence", [])),
            }
        )
    behaviors.sort(key=lambda behavior: (-behavior["rank"], behavior["id"]))

    readable_behaviors = [
        row for row in behaviors if not row["label"].startswith("Callback · line ")
    ]
    primary_behaviors = (readable_behaviors or behaviors)[:primary_limit]
    unplaced = sorted(set(by_id) - reachable)
    return {
        "schema_version": 1,
        "language": {
            "root": "root node",
            "node": "node",
            "seed": "seed node",
            "leaf": "leaf node",
        },
        "leaf_ranking": leaf_ranking,
        "primary_behavior_ids": [row["id"] for row in primary_behaviors],
        "behaviors": behaviors,
        "layers": layers,
        "coverage": {
            "analyzed_functions": len(by_id),
            "functions_with_layers": len(layers),
            "reachable_from_roots": len(reachable),
            "unplaced_function_ids": unplaced,
            "accounted_function_ids": sorted(by_id),
        },
        "known_limits": [
            "Callsites are ordered lexically; the view does not claim observed runtime order.",
            "Static analysis may miss dynamic dispatch, reflection, framework wiring, and cross-process continuation.",
            "A focused layer explains one source function; grouped semantic stages are a later projection over the same evidence.",
        ],
    }
