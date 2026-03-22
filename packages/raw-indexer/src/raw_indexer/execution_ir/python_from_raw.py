"""
Slice 3 — build execution IR from existing RAW index (Python AST v0).

Emits function nodes and `calls` edges for `Name(...)` callees that resolve via
import-from map or same-module qualified names. Unresolved `Name` calls and
`Attribute` / method calls emit `confidence: unknown` edges to a boundary node.
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

from raw_indexer.execution_ir.validate import EXECUTION_IR_SCHEMA_VERSION, validate_execution_ir
from raw_indexer.index import module_qualname_from_path

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


class _CallGraphVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        module_q: str,
        sym_by_qual: dict[str, dict[str, Any]],
        import_map: dict[str, str],
        resolved_edges: set[tuple[str, str]],
        unknown_from: set[str],
    ) -> None:
        self.module_q = module_q
        self.sym_by_qual = sym_by_qual
        self.import_map = import_map
        self._resolved_edges = resolved_edges
        self._unknown_from = unknown_from
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

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scope.append(node.name)
        prev = self._current_fn_qual
        cq = self._qual_path()
        self._current_fn_qual = cq if cq in self.sym_by_qual else prev
        self.generic_visit(node)
        self._current_fn_qual = prev
        self._scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scope.append(node.name)
        prev = self._current_fn_qual
        cq = self._qual_path()
        self._current_fn_qual = cq if cq in self.sym_by_qual else prev
        self.generic_visit(node)
        self._current_fn_qual = prev
        self._scope.pop()

    def _resolve_name_callee(self, name: str) -> str | None:
        if name in self.import_map:
            raw = self.import_map[name]
            if raw in self.sym_by_qual:
                return raw
            return None
        for i in range(len(self._scope), -1, -1):
            prefix = ([self.module_q] if self.module_q else []) + self._scope[:i]
            cand = ".".join(prefix + [name]) if prefix else name
            if cand in self.sym_by_qual:
                return cand
        return None

    def visit_Call(self, node: ast.Call) -> None:
        if self._current_fn_qual and self._current_fn_qual in self.sym_by_qual:
            fr = flow_fn_id(self._current_fn_qual)
            if isinstance(node.func, ast.Name):
                callee_qual = self._resolve_name_callee(node.func.id)
                if callee_qual:
                    self._resolved_edges.add((fr, flow_fn_id(callee_qual)))
                elif node.func.id not in _BUILTIN_NAMES:
                    self._unknown_from.add(fr)
        self.generic_visit(node)


def build_execution_ir_from_raw(raw_doc: dict[str, Any]) -> dict[str, Any]:
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
    unknown_from: set[str] = set()
    files = {str(f.get("id")): f for f in raw_doc.get("files", []) if isinstance(f, dict)}

    for s in symbols:
        fid = str(s.get("file_id", ""))
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
        mq = module_qualname_from_path(Path(rel))
        imp = _import_name_to_qual(tree, mq)
        vis = _CallGraphVisitor(
            module_q=mq,
            sym_by_qual=sym_by_qual,
            import_map=imp,
            resolved_edges=resolved_edges,
            unknown_from=unknown_from,
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

    if unknown_from:
        nodes.append(
            {
                "id": BOUNDARY_UNRESOLVED_ID,
                "kind": "dynamic_callsite",
                "language": "python",
                "label": "Unresolved / not traced (v0)",
            },
        )

    edge_rows: list[tuple[str, str, str, str]] = []
    for fr, to in sorted(contains_pairs):
        edge_rows.append(("contains", fr, to, "resolved"))
    for fr, to in sorted(resolved_edges):
        edge_rows.append(("calls", fr, to, "resolved"))
    for fr in sorted(unknown_from):
        edge_rows.append(("calls", fr, BOUNDARY_UNRESOLVED_ID, "unknown"))

    edges: list[dict[str, Any]] = []
    for i, (kind, fr, to, confidence) in enumerate(edge_rows):
        edge: dict[str, Any] = {
            "id": f"e:{i}",
            "from": fr,
            "to": to,
            "kind": kind,
            "confidence": confidence,
        }
        if confidence == "unknown":
            edge["evidence"] = "unresolved_name_or_attribute_call"
        edges.append(edge)

    entrypoints: list[str] = []
    for n in nodes:
        lab = str(n.get("label", ""))
        if lab.endswith(".create_app") or lab == "create_app":
            entrypoints.append(n["id"])
    if not entrypoints and nodes:
        entrypoints = [nodes[0]["id"]]

    doc: dict[str, Any] = {
        "schema_version": EXECUTION_IR_SCHEMA_VERSION,
        "repo_root": str(root),
        "languages": ["python"],
        "entrypoints": entrypoints,
        "producers": [{"name": "raw_indexer.execution_ir.python_from_raw", "version": "0"}],
        "nodes": nodes,
        "edges": edges,
    }
    errs = validate_execution_ir(doc)
    if errs:
        raise ValueError("invalid execution IR: " + "; ".join(errs))
    return doc
