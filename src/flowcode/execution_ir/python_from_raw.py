"""
Slice 3 — build execution IR from existing RAW index (Python AST v0).

Emits function nodes and `calls` edges for `Name(...)` callees that resolve via
import-from map or same-module qualified names. Unresolved `Name` calls (with
optional ``import_ref``) and `Attribute` / method calls emit ``confidence: unknown``
edges to a boundary node, one edge per callsite with a ``callsite`` payload for labeling.
"""

from __future__ import annotations

import ast
import builtins
from pathlib import Path
from typing import Any

# Unresolved `Name(...)` callees in this set are skipped (no unknown edge) — avoids noise
# from `dict()`, `len()`, etc. Unresolved non-builtins (e.g. third-party constructors) still
# become `confidence: unknown` to the boundary node.
_BUILTIN_NAMES = frozenset(vars(builtins))

from flowcode.execution_ir.validate import EXECUTION_IR_SCHEMA_VERSION, validate_execution_ir
from flowcode.index import module_qualname_from_path

BOUNDARY_UNRESOLVED_ID = "py:boundary:unresolved"


def flow_fn_id(qualified_name: str) -> str:
    return f"py:fn:{qualified_name}"


def _resolve_import_base(module: str | None, level: int, current_module_q: str) -> str:
    if level == 0:
        return (module or "").strip()
    parts = current_module_q.split(".")
    if level > len(parts):
        return ""
    base = ".".join(parts[:-level])
    if module:
        return f"{base}.{module}" if base else module
    return base


def _import_name_to_qual(tree: ast.Module, module_q: str) -> dict[str, str]:
    """Local name -> fully qualified *symbol* name for imported functions/classes."""
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            base = _resolve_import_base(node.module, node.level or 0, module_q)
            for a in node.names:
                if a.name == "*":
                    continue
                local = a.asname or a.name
                out[local] = f"{base}.{a.name}" if base else a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                local = a.asname or a.name.split(".")[0]
                out[local] = a.name
    return out


def _collect_function_local_imports(fn_node: ast.AST, module_q: str) -> dict[str, str]:
    """Walk fn_node's body for ImportFrom/Import statements (lazy imports), but
    do not descend into nested function or class bodies — those have their own
    scopes. Returns local-name → fully-qualified-symbol map.
    """
    out: dict[str, str] = {}
    # Iterate the function body using a stack so we can prune nested defs.
    body = getattr(fn_node, "body", None) or []
    stack: list[ast.AST] = list(body)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # nested scopes have their own imports
        if isinstance(n, ast.ImportFrom):
            base = _resolve_import_base(n.module, n.level or 0, module_q)
            for a in n.names:
                if a.name == "*":
                    continue
                local = a.asname or a.name
                out[local] = f"{base}.{a.name}" if base else a.name
            continue
        if isinstance(n, ast.Import):
            for a in n.names:
                local = a.asname or a.name.split(".")[0]
                out[local] = a.name
            continue
        # Recurse into other compound statements (if/try/with/for/while/etc.)
        for child in ast.iter_child_nodes(n):
            stack.append(child)
    return out


_MISSING = object()


def _resolve_re_export(import_qual: str, sym_by_qual: dict[str, Any]) -> str | None:
    """If `import_qual` was imported via a package re-export (e.g.
    `from pkg import f` where `f` is actually defined in `pkg.submodule.f`),
    find the real qualified name. Returns None if no unique match exists.
    """
    pkg, _, leaf = import_qual.rpartition(".")
    if not pkg or not leaf:
        return None
    candidates = [
        q for q in sym_by_qual
        if q.startswith(pkg + ".") and (q == f"{pkg}.{leaf}" or q.endswith(f".{leaf}"))
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


class _CallGraphVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        module_q: str,
        sym_by_qual: dict[str, dict[str, Any]],
        import_map: dict[str, str],
        resolved_edges: set[tuple[str, str]],
        unknown_records: list[tuple[str, dict[str, Any]]],
        source: str,
    ) -> None:
        self.module_q = module_q
        self.sym_by_qual = sym_by_qual
        self.import_map = import_map
        self._resolved_edges = resolved_edges
        self._unknown_records = unknown_records
        self._source = source
        self._scope: list[str] = []
        self._current_fn_qual: str | None = None

    def _qual_path(self) -> str:
        parts = [self.module_q] if self.module_q else []
        parts.extend(self._scope)
        return ".".join(parts)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def _enter_function_scope(self, node: ast.AST) -> dict[str, Any]:
        """Push function name onto scope, set _current_fn_qual, and push any
        function-local imports (lazy imports) into self.import_map. Returns a
        state dict to restore in _leave_function_scope.
        """
        name = getattr(node, "name", "")
        self._scope.append(name)
        prev_fn = self._current_fn_qual
        cq = self._qual_path()
        self._current_fn_qual = cq if cq in self.sym_by_qual else prev_fn

        local_imports = _collect_function_local_imports(node, self.module_q)
        saved: dict[str, Any] = {}
        for k, v in local_imports.items():
            saved[k] = self.import_map.get(k, _MISSING)
            self.import_map[k] = v
        return {"prev_fn": prev_fn, "saved": saved}

    def _leave_function_scope(self, state: dict[str, Any]) -> None:
        for k, v in state["saved"].items():
            if v is _MISSING:
                self.import_map.pop(k, None)
            else:
                self.import_map[k] = v
        self._current_fn_qual = state["prev_fn"]
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        state = self._enter_function_scope(node)
        self.generic_visit(node)
        self._leave_function_scope(state)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        state = self._enter_function_scope(node)
        self.generic_visit(node)
        self._leave_function_scope(state)

    def _resolve_name_callee(self, name: str) -> str | None:
        if name in self.import_map:
            raw = self.import_map[name]
            if raw in self.sym_by_qual:
                return raw
            # Re-export through __init__.py: import target points at the package,
            # but the symbol actually lives in a submodule. Look for a unique match.
            re_exported = _resolve_re_export(raw, self.sym_by_qual)
            if re_exported:
                return re_exported
            return None
        for i in range(len(self._scope), -1, -1):
            prefix = ([self.module_q] if self.module_q else []) + self._scope[:i]
            cand = ".".join(prefix + [name]) if prefix else name
            if cand in self.sym_by_qual:
                return cand
        return None

    def _snippet(self, node: ast.AST) -> str:
        if not self._source:
            return ""
        seg = ast.get_source_segment(self._source, node)
        if not seg:
            return ""
        one = seg.strip().replace("\n", " ")
        return one if len(one) <= 200 else one[:197] + "..."

    def _append_unknown(self, fr: str, node: ast.Call, payload: dict[str, Any]) -> None:
        line = int(getattr(node, "lineno", 0) or 0)
        body = {"line": line, "snippet": self._snippet(node), **payload}
        self._unknown_records.append((fr, body))

    def visit_Call(self, node: ast.Call) -> None:
        if self._current_fn_qual and self._current_fn_qual in self.sym_by_qual:
            fr = flow_fn_id(self._current_fn_qual)
            if isinstance(node.func, ast.Name):
                callee_qual = self._resolve_name_callee(node.func.id)
                if callee_qual:
                    self._resolved_edges.add((fr, flow_fn_id(callee_qual)))
                elif node.func.id not in _BUILTIN_NAMES:
                    name = node.func.id
                    pay: dict[str, Any] = {"callee": name}
                    imp = self.import_map.get(name)
                    if imp:
                        pay["import_ref"] = imp
                    self._append_unknown(fr, node, pay)
            elif isinstance(node.func, ast.Attribute):
                try:
                    expr = ast.unparse(node.func)
                except (AttributeError, TypeError, ValueError):
                    expr = "?"
                self._append_unknown(fr, node, {"callee_expression": expr})
        self.generic_visit(node)


def build_execution_ir_from_raw(raw_doc: dict[str, Any]) -> dict[str, Any]:
    from flowcode.entrypoint_heuristics import detect_entrypoints, load_flowcode_config

    root = Path(str(raw_doc.get("root", ""))).resolve()
    symbols = [
        s
        for s in raw_doc.get("symbols", [])
        if isinstance(s, dict) and s.get("kind") in ("function", "async_function")
    ]
    sym_by_qual: dict[str, dict[str, Any]] = {}
    for s in symbols:
        qn = str(s.get("qualified_name", ""))
        if qn:
            sym_by_qual[qn] = s

    nodes: list[dict[str, Any]] = []
    for s in symbols:
        qn = str(s.get("qualified_name", ""))
        if not qn:
            continue
        fid = str(s.get("file_id", ""))
        rel = fid[5:] if fid.startswith("file:") else fid
        nodes.append(
            {
                "id": flow_fn_id(qn),
                "kind": "function",
                "language": "python",
                "label": qn,
                "location": {
                    "path": rel,
                    "start_line": int(s.get("line") or 0),
                    "end_line": int(s.get("end_line") or s.get("line") or 0),
                },
                "raw_symbol_id": s.get("id"),
            },
        )

    resolved_edges: set[tuple[str, str]] = set()
    unknown_records: list[tuple[str, dict[str, Any]]] = []
    files = {str(f.get("id")): f for f in raw_doc.get("files", []) if isinstance(f, dict)}

    visited_file_ids: set[str] = set()
    for s in symbols:
        fid = str(s.get("file_id", ""))
        if fid in visited_file_ids:
            continue
        frow = files.get(fid)
        if not frow:
            continue
        analysis = frow.get("analysis") or {}
        if analysis.get("parse_ok") is not True:
            continue
        rel = str(frow.get("path", ""))
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        visited_file_ids.add(fid)
        mq = module_qualname_from_path(Path(rel))
        imp = _import_name_to_qual(tree, mq)
        vis = _CallGraphVisitor(
            module_q=mq,
            sym_by_qual=sym_by_qual,
            import_map=imp,
            resolved_edges=resolved_edges,
            unknown_records=unknown_records,
            source=text,
        )
        vis.visit(tree)

    contains_pairs: set[tuple[str, str]] = set()
    for s in symbols:
        qn = str(s.get("qualified_name", ""))
        if not qn:
            continue
        parent_qn, _, _leaf = qn.rpartition(".")
        if parent_qn and parent_qn in sym_by_qual:
            contains_pairs.add((flow_fn_id(parent_qn), flow_fn_id(qn)))

    if unknown_records:
        nodes.append(
            {
                "id": BOUNDARY_UNRESOLVED_ID,
                "kind": "dynamic_callsite",
                "language": "python",
                "label": "Unresolved / not traced (v0)",
            },
        )

    def _unknown_sort_key(t: tuple[str, dict[str, Any]]) -> tuple[str, int, str]:
        fr, d = t
        line = int(d.get("line") or 0)
        key = str(d.get("callee") or d.get("callee_expression") or "")
        return (fr, line, key)

    edge_rows: list[tuple[str, str, str, str, dict[str, Any] | None]] = []
    for fr, to in sorted(contains_pairs):
        edge_rows.append(("contains", fr, to, "resolved", None))
    for fr, to in sorted(resolved_edges):
        edge_rows.append(("calls", fr, to, "resolved", None))
    for fr, cs in sorted(unknown_records, key=_unknown_sort_key):
        edge_rows.append(("calls", fr, BOUNDARY_UNRESOLVED_ID, "unknown", cs))

    edges: list[dict[str, Any]] = []
    for i, (kind, fr, to, confidence, callsite) in enumerate(edge_rows):
        edge: dict[str, Any] = {
            "id": f"e:{i}",
            "from": fr,
            "to": to,
            "kind": kind,
            "confidence": confidence,
        }
        if confidence == "unknown":
            edge["evidence"] = "unresolved_name_or_attribute_call"
            if callsite is not None:
                edge["callsite"] = callsite
        edges.append(edge)

    # Use generalized entrypoint detection
    config = load_flowcode_config(root)
    entrypoints = detect_entrypoints(nodes, edges, config=config)

    doc: dict[str, Any] = {
        "schema_version": EXECUTION_IR_SCHEMA_VERSION,
        "repo_root": str(root),
        "languages": ["python"],
        "entrypoints": entrypoints,
        "producers": [{"name": "flowcode.execution_ir.python_from_raw", "version": "0"}],
        "nodes": nodes,
        "edges": edges,
    }
    errs = validate_execution_ir(doc)
    if errs:
        raise ValueError("invalid execution IR: " + "; ".join(errs))
    return doc
