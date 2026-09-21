"""Convert the conservative single-language tree-sitter RAW index to execution IR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flowcode.entrypoint_heuristics import detect_entrypoints, load_flowcode_config
from flowcode.execution_ir.validate import (
    EXECUTION_IR_SCHEMA_VERSION,
    validate_execution_ir,
)


def _fn_id(language: str, qualified: str) -> str:
    return f"{language}:fn:{qualified}"


def build_execution_ir_from_treesitter_raw(raw: dict[str, Any]) -> dict[str, Any]:
    language = str(raw.get("language") or "")
    if not language:
        raise ValueError("tree-sitter RAW document is missing language")
    symbols = [
        symbol
        for symbol in raw.get("symbols", [])
        if isinstance(symbol, dict) and symbol.get("kind") == "function"
    ]
    by_qualified = {str(symbol["qualified_name"]): symbol for symbol in symbols}
    by_leaf: dict[str, list[str]] = {}
    for qualified, symbol in by_qualified.items():
        by_leaf.setdefault(str(symbol.get("name") or qualified.rsplit(".", 1)[-1]), []).append(
            qualified
        )

    nodes: list[dict[str, Any]] = []
    for qualified, symbol in sorted(by_qualified.items()):
        file_id = str(symbol.get("file_id", ""))
        relative = file_id.removeprefix("file:")
        nodes.append(
            {
                "id": _fn_id(language, qualified),
                "kind": "function",
                "language": language,
                "label": qualified,
                "location": {
                    "path": relative,
                    "start_line": int(symbol.get("line") or 0),
                    "end_line": int(symbol.get("end_line") or symbol.get("line") or 0),
                    "start_column": int(symbol.get("column") or 1),
                    "end_column": int(symbol.get("end_column") or 1),
                },
                "raw_symbol_id": symbol.get("id"),
            }
        )

    linked: set[tuple[str, str, int, str]] = set()
    unknown: list[tuple[str, dict[str, Any]]] = []
    for caller, symbol in sorted(by_qualified.items()):
        caller_id = _fn_id(language, caller)
        caller_parent = caller.rpartition(".")[0]
        for call in symbol.get("calls", []):
            callee = str(call.get("callee") or "")
            line = int(call.get("line") or 0)
            candidates: list[str] = []
            local = f"{caller_parent}.{callee}" if caller_parent else callee
            if call.get("direct"):
                local_candidates = [
                    qualified
                    for qualified in by_leaf.get(callee, [])
                    if qualified == local
                    or qualified.startswith(f"{local}$overload_")
                ]
                # Java methods are owner-scoped: a missing inherited target
                # must not resolve to an unrelated class with the same name.
                candidates = local_candidates if language == 'java' else local_candidates or by_leaf.get(callee, [])
            elif language == 'java' and call.get('receiver_type'):
                receiver_type = call['receiver_type']
                candidates = [qualified for qualified in by_leaf.get(callee, [])
                              if qualified.rpartition('.')[0] == receiver_type
                              or qualified.rpartition('.')[0].endswith('.' + receiver_type)]
            if language == 'java' and isinstance(call.get('arity'), int):
                candidates = [qualified for qualified in candidates
                              if by_qualified[qualified].get('arity') in {None, call['arity']}]
            if len(candidates) == 1:
                confidence = 'resolved' if call.get('direct') else 'heuristic'
                linked.add((caller_id, _fn_id(language, candidates[0]), line, confidence))
            else:
                unknown.append(
                    (
                        caller_id,
                        {
                            "callee": callee,
                            "line": line,
                            "reason": "ambiguous" if len(candidates) > 1 else "unresolved",
                        },
                    )
                )

    boundary = f"{language}:boundary:unresolved"
    if unknown:
        nodes.append(
            {
                "id": boundary,
                "kind": "dynamic_callsite",
                "language": language,
                "label": f"Unresolved / not traced ({language} v0)",
            }
        )

    rows: list[tuple[str, str, str, dict[str, Any]]] = []
    for source, target, line, confidence in sorted(linked):
        rows.append((source, target, confidence, {"line": line}))
    for source, callsite in sorted(
        unknown, key=lambda item: (item[0], item[1]["line"], item[1]["callee"])
    ):
        rows.append((source, boundary, "unknown", callsite))
    edges = []
    for index, (source, target, confidence, callsite) in enumerate(rows):
        edge = {
            "id": f"e:{index}",
            "from": source,
            "to": target,
            "kind": "calls",
            "confidence": confidence,
            "callsite": callsite,
        }
        if confidence == "heuristic":
            edge["evidence"] = "declared_receiver_type_and_arity"
        if confidence == "unknown":
            edge["evidence"] = "unresolved_or_ambiguous_direct_call"
        edges.append(edge)

    root = Path(str(raw.get("root") or "")).resolve()
    entrypoints = detect_entrypoints(nodes, edges, config=load_flowcode_config(root))
    document = {
        "schema_version": EXECUTION_IR_SCHEMA_VERSION,
        "repo_root": str(root),
        "languages": [language],
        "entrypoints": entrypoints,
        "producers": [
            {"name": "flowcode.execution_ir.treesitter_from_raw", "version": "0"}
        ],
        "nodes": nodes,
        "edges": edges,
    }
    errors = validate_execution_ir(document)
    if errors:
        raise ValueError("invalid execution IR: " + "; ".join(errors))
    return document
