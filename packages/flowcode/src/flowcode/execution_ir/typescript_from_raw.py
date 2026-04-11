"""Build execution IR from a TypeScript RAW index (tree-sitter v0).

Produces call graph edges by re-parsing source files and resolving Name-style
call expressions against the import map + in-scope symbol table.  Attribute /
method calls go to a boundary node as `confidence: unknown`.

Node ID prefix: ts:fn:
Boundary node:  ts:boundary:unresolved
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flowcode.execution_ir.validate import EXECUTION_IR_SCHEMA_VERSION, validate_execution_ir

BOUNDARY_UNRESOLVED_ID = "ts:boundary:unresolved"


def ts_fn_id(qualified_name: str) -> str:
    return f"ts:fn:{qualified_name}"


def _get_parser():
    try:
        import tree_sitter as ts
        import tree_sitter_typescript as tsts
    except ImportError as e:
        raise ImportError(
            "TypeScript IR builder requires tree-sitter: pip install flowcode[ts]"
        ) from e
    return ts.Parser(ts.Language(tsts.language_typescript()))


def _node_text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _build_import_map(root_node: Any, source: bytes) -> dict[str, str]:
    """local_name -> module specifier for imported names."""
    imp_map: dict[str, str] = {}
    for child in root_node.children:
        if child.type == "import_statement":
            module = ""
            for gc in child.children:
                if gc.type == "string":
                    module = _node_text(gc, source).strip("\"'")
            clause = child.child_by_field_name("source") or None
            # Find import_clause child
            for gc in child.children:
                if gc.type == "import_clause":
                    for ggc in gc.children:
                        if ggc.type == "named_imports":
                            for spec in ggc.children:
                                if spec.type == "import_specifier":
                                    # name node
                                    name_node = spec.child_by_field_name("name") or spec.children[0] if spec.children else None
                                    alias_node = spec.child_by_field_name("alias")
                                    if name_node:
                                        orig = _node_text(name_node, source)
                                        local = _node_text(alias_node, source) if alias_node else orig
                                        imp_map[local] = f"{module}.{orig}"
                        elif ggc.type == "identifier":
                            # default import: import foo from "..."
                            local = _node_text(ggc, source)
                            imp_map[local] = module
    return imp_map


class _CallVisitor:
    def __init__(
        self,
        module_q: str,
        sym_by_qual: dict[str, Any],
        import_map: dict[str, str],
        source: bytes,
        resolved_edges: set[tuple[str, str]],
        unknown_records: list[tuple[str, dict[str, Any]]],
    ) -> None:
        self.module_q = module_q
        self.sym_by_qual = sym_by_qual
        self.import_map = import_map
        self.source = source
        self.resolved_edges = resolved_edges
        self.unknown_records = unknown_records
        self._scope: list[str] = []
        self._current_fn_qual: str | None = None

    def _qual(self, name: str) -> str:
        parts = ([self.module_q] if self.module_q else []) + self._scope + [name]
        return ".".join(parts)

    def _resolve_name(self, name: str) -> str | None:
        # Check import map
        if name in self.import_map:
            imp = self.import_map[name]
            # Try direct lookup
            if imp in self.sym_by_qual:
                return imp
            # Strip module prefix, try name portion
            _, _, sym_name = imp.rpartition(".")
            for qual in self.sym_by_qual:
                if qual.endswith(f".{sym_name}") or qual == sym_name:
                    return qual
            return None
        # Try in-scope lookups
        for i in range(len(self._scope), -1, -1):
            prefix = ([self.module_q] if self.module_q else []) + self._scope[:i]
            cand = ".".join(prefix + [name]) if prefix else name
            if cand in self.sym_by_qual:
                return cand
        return None

    def _current_id(self) -> str | None:
        if self._current_fn_qual and self._current_fn_qual in self.sym_by_qual:
            return ts_fn_id(self._current_fn_qual)
        return None

    def _visit_call(self, node: Any) -> None:
        fr = self._current_id()
        if fr is None:
            return
        func_node = node.child_by_field_name("function")
        if func_node is None:
            return
        line = node.start_point[0] + 1

        if func_node.type == "identifier":
            name = _node_text(func_node, self.source)
            resolved = self._resolve_name(name)
            if resolved:
                self.resolved_edges.add((fr, ts_fn_id(resolved)))
            else:
                imp = self.import_map.get(name)
                pay: dict[str, Any] = {"callee": name, "line": line}
                if imp:
                    pay["import_ref"] = imp
                self.unknown_records.append((fr, pay))
        else:
            expr = _node_text(func_node, self.source).replace("\n", " ")[:200]
            self.unknown_records.append((fr, {"callee_expression": expr, "line": line}))

    def visit(self, node: Any) -> None:
        t = node.type

        if t == "call_expression":
            self._visit_call(node)
            for child in node.children:
                self.visit(child)
            return

        if t == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _node_text(name_node, self.source)
                self._scope.append(name)
                prev = self._current_fn_qual
                cq = ".".join(([self.module_q] if self.module_q else []) + self._scope)
                self._current_fn_qual = cq if cq in self.sym_by_qual else prev
                for child in node.children:
                    self.visit(child)
                self._current_fn_qual = prev
                self._scope.pop()
                return

        if t in ("arrow_function", "function"):
            # May be named via variable_declarator — scope already pushed by parent
            for child in node.children:
                self.visit(child)
            return

        if t in ("variable_declaration", "lexical_declaration"):
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    val_node = child.child_by_field_name("value")
                    if name_node and val_node and val_node.type in (
                        "arrow_function", "function", "generator_function"
                    ):
                        name = _node_text(name_node, self.source)
                        self._scope.append(name)
                        prev = self._current_fn_qual
                        cq = ".".join(([self.module_q] if self.module_q else []) + self._scope)
                        self._current_fn_qual = cq if cq in self.sym_by_qual else prev
                        self.visit(val_node)
                        self._current_fn_qual = prev
                        self._scope.pop()
                    else:
                        for subchild in child.children:
                            self.visit(subchild)
            return

        if t == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = _node_text(name_node, self.source)
                self._scope.append(class_name)
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type == "method_definition":
                            mname_node = child.child_by_field_name("name")
                            if mname_node:
                                mname = _node_text(mname_node, self.source)
                                self._scope.append(mname)
                                prev = self._current_fn_qual
                                cq = ".".join(([self.module_q] if self.module_q else []) + self._scope)
                                self._current_fn_qual = cq if cq in self.sym_by_qual else prev
                                mbody = child.child_by_field_name("body")
                                if mbody:
                                    for sub in mbody.children:
                                        self.visit(sub)
                                self._current_fn_qual = prev
                                self._scope.pop()
                self._scope.pop()
            return

        if t == "export_statement":
            for child in node.children:
                self.visit(child)
            return

        # Generic recurse
        for child in node.children:
            self.visit(child)


def build_execution_ir_from_ts_raw(raw_doc: dict[str, Any]) -> dict[str, Any]:
    from flowcode.entrypoint_heuristics import detect_entrypoints, load_flowcode_config

    root = Path(str(raw_doc.get("root", ""))).resolve()
    symbols = [
        s
        for s in raw_doc.get("symbols", [])
        if isinstance(s, dict) and s.get("kind") == "function"
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
        nodes.append({
            "id": ts_fn_id(qn),
            "kind": "function",
            "language": "typescript",
            "label": qn,
            "location": {
                "path": rel,
                "start_line": int(s.get("line") or 0),
                "end_line": int(s.get("end_line") or s.get("line") or 0),
            },
            "raw_symbol_id": s.get("id"),
        })

    try:
        parser = _get_parser()
    except ImportError:
        raise

    files = {str(f.get("id")): f for f in raw_doc.get("files", []) if isinstance(f, dict)}
    resolved_edges: set[tuple[str, str]] = set()
    unknown_records: list[tuple[str, dict[str, Any]]] = []

    # Group symbols by file
    syms_by_file: dict[str, list[dict[str, Any]]] = {}
    for s in symbols:
        fid = str(s.get("file_id", ""))
        syms_by_file.setdefault(fid, []).append(s)

    for fid, file_syms in syms_by_file.items():
        frow = files.get(fid)
        if not frow:
            continue
        if frow.get("analysis", {}).get("parse_ok") is not True:
            continue
        rel = str(frow.get("path", ""))
        path = root / rel
        if not path.is_file():
            continue
        try:
            source = path.read_bytes()
            tree = parser.parse(source)
        except Exception:
            continue

        from flowcode.ts_indexer import _ts_module_qualname
        module_q = _ts_module_qualname(Path(rel))
        imp_map = _build_import_map(tree.root_node, source)

        vis = _CallVisitor(
            module_q=module_q,
            sym_by_qual=sym_by_qual,
            import_map=imp_map,
            source=source,
            resolved_edges=resolved_edges,
            unknown_records=unknown_records,
        )
        vis.visit(tree.root_node)

    # Contains edges: parent_qual contains child_qual
    contains_pairs: set[tuple[str, str]] = set()
    for s in symbols:
        qn = str(s.get("qualified_name", ""))
        if not qn:
            continue
        parent_qn, _, _leaf = qn.rpartition(".")
        if parent_qn and parent_qn in sym_by_qual:
            contains_pairs.add((ts_fn_id(parent_qn), ts_fn_id(qn)))

    if unknown_records:
        nodes.append({
            "id": BOUNDARY_UNRESOLVED_ID,
            "kind": "dynamic_callsite",
            "language": "typescript",
            "label": "Unresolved / not traced (ts v0)",
        })

    def _unk_key(t: tuple[str, dict[str, Any]]) -> tuple[str, int, str]:
        fr, d = t
        return (fr, int(d.get("line") or 0), str(d.get("callee") or d.get("callee_expression") or ""))

    edge_rows: list[tuple[str, str, str, str, dict[str, Any] | None]] = []
    for fr, to in sorted(contains_pairs):
        edge_rows.append(("contains", fr, to, "resolved", None))
    for fr, to in sorted(resolved_edges):
        edge_rows.append(("calls", fr, to, "resolved", None))
    for fr, cs in sorted(unknown_records, key=_unk_key):
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

    config = load_flowcode_config(root)
    entrypoints = detect_entrypoints(nodes, edges, config=config)

    doc: dict[str, Any] = {
        "schema_version": EXECUTION_IR_SCHEMA_VERSION,
        "repo_root": str(root),
        "languages": ["typescript"],
        "entrypoints": entrypoints,
        "producers": [{"name": "flowcode.execution_ir.typescript_from_raw", "version": "0"}],
        "nodes": nodes,
        "edges": edges,
    }
    errs = validate_execution_ir(doc)
    if errs:
        raise ValueError("invalid execution IR: " + "; ".join(errs))
    return doc
