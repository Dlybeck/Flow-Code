"""TypeScript/JavaScript RAW indexer using tree-sitter.

Requires the optional [ts] dependency group:
    pip install flowcode[ts]  # tree-sitter + tree-sitter-typescript

Produces the same RAW JSON schema as the Python indexer (schema_version 0).
Symbol IDs: sym:{relpath}:{qualified_name}
File IDs:   file:{relpath}
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

_TS_EXTENSIONS = frozenset({".ts", ".tsx", ".js", ".mjs", ".jsx"})


def _ts_module_qualname(relpath: Path) -> str:
    """src/index.ts -> index, src/utils/helper.ts -> utils.helper"""
    parts = list(relpath.parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if not parts:
        return ""
    stem = parts[-1]
    for ext in (".ts", ".tsx", ".js", ".mjs", ".jsx"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    if stem == "index" and len(parts) > 1:
        parts = parts[:-1]
    else:
        parts[-1] = stem
    return ".".join(parts) if parts else ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _get_language():
    try:
        import tree_sitter as ts
        import tree_sitter_typescript as tsts
    except ImportError as e:
        raise ImportError(
            "TypeScript indexer requires tree-sitter: pip install flowcode[ts]"
        ) from e
    return ts.Language(tsts.language_typescript()), ts


def _node_text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _collect_call_expressions(node: Any, source: bytes) -> list[str]:
    """Recursively collect callee expressions for call_expression nodes."""
    results: list[str] = []
    if node.type == "call_expression":
        func_node = node.child_by_field_name("function")
        if func_node is not None:
            results.append(_node_text(func_node, source))
    for child in node.children:
        results.extend(_collect_call_expressions(child, source))
    return results


class _SymbolExtractor:
    def __init__(self, module_q: str, file_id: str, source: bytes) -> None:
        self.module_q = module_q
        self.file_id = file_id
        self.source = source
        self.symbols: list[dict[str, Any]] = []
        self._scope: list[str] = []

    def _qual_path(self, name: str) -> str:
        parts = ([self.module_q] if self.module_q else []) + self._scope + [name]
        return ".".join(parts)

    def _sym_id(self, qual: str) -> str:
        rel = self.file_id[5:] if self.file_id.startswith("file:") else self.file_id
        return f"sym:{rel}:{qual}"

    def _add_fn(self, name: str, node: Any, is_exported: bool = False) -> None:
        qual = self._qual_path(name)
        sym: dict[str, Any] = {
            "id": self._sym_id(qual),
            "kind": "function",
            "name": name,
            "qualified_name": qual,
            "file_id": self.file_id,
            "line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
        }
        if is_exported:
            sym["exported"] = True
        self.symbols.append(sym)

    def visit(self, node: Any, exported: bool = False) -> None:
        t = node.type

        if t == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _node_text(name_node, self.source)
                self._add_fn(name, node, is_exported=exported)
                self._scope.append(name)
                body = node.child_by_field_name("body")
                if body:
                    self._visit_body(body)
                self._scope.pop()
            return

        if t in ("function", "arrow_function", "generator_function"):
            # Anonymous function assigned via variable_declarator — handled by parent
            return

        if t == "variable_declaration" or t == "lexical_declaration":
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    val_node = child.child_by_field_name("value")
                    if name_node and val_node and val_node.type in (
                        "arrow_function", "function", "generator_function"
                    ):
                        name = _node_text(name_node, self.source)
                        # strip type annotation if present (identifier node)
                        if name_node.type == "identifier":
                            self._add_fn(name, val_node, is_exported=exported)
                            self._scope.append(name)
                            body = val_node.child_by_field_name("body")
                            if body:
                                self._visit_body(body)
                            self._scope.pop()
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
                                self._add_fn(mname, child)
                                self._scope.append(mname)
                                mbody = child.child_by_field_name("body")
                                if mbody:
                                    self._visit_body(mbody)
                                self._scope.pop()
                self._scope.pop()
            return

        if t == "export_statement":
            for child in node.children:
                if child.type in (
                    "function_declaration",
                    "class_declaration",
                    "lexical_declaration",
                    "variable_declaration",
                ):
                    self.visit(child, exported=True)
            return

        # Recurse into top-level statements
        if t == "program":
            for child in node.children:
                self.visit(child, exported=False)

    def _visit_body(self, body_node: Any) -> None:
        for child in body_node.children:
            if child.type in (
                "function_declaration",
                "lexical_declaration",
                "variable_declaration",
                "class_declaration",
                "export_statement",
            ):
                self.visit(child)


def _extract_imports(root_node: Any, source: bytes, module_q: str) -> list[dict[str, Any]]:
    """Extract import edges: import_from kind, similar to Python RAW format."""
    edges: list[dict[str, Any]] = []
    for child in root_node.children:
        if child.type == "import_statement":
            # Find the string (module path)
            for gc in child.children:
                if gc.type == "string":
                    raw = _node_text(gc, source).strip("\"'")
                    edges.append({
                        "kind": "import_from",
                        "from_module": module_q,
                        "module": raw,
                        "line": child.start_point[0] + 1,
                    })
                    break
    return edges


def index_ts_repo(
    repo_root: Path,
    src_roots: list[str] | None = None,
) -> dict[str, Any]:
    """Index a TypeScript/JavaScript repo and return a RAW JSON document."""
    lang, ts_mod = _get_language()
    parser = ts_mod.Parser(lang)

    repo_root = repo_root.resolve()
    if src_roots:
        search_roots = [repo_root / sr for sr in src_roots]
    else:
        default_src = repo_root / "src"
        search_roots = [default_src] if default_src.is_dir() else [repo_root]

    ts_files: list[Path] = []
    for sr in search_roots:
        if sr.is_dir():
            for ext in _TS_EXTENSIONS:
                ts_files.extend(sr.rglob(f"*{ext}"))
    ts_files.sort()

    file_rows: list[dict[str, Any]] = []
    symbol_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []

    for abs_path in ts_files:
        try:
            rel = abs_path.relative_to(repo_root)
        except ValueError:
            continue
        rel_posix = rel.as_posix()
        file_id = f"file:{rel_posix}"

        try:
            source = abs_path.read_bytes()
            sha = hashlib.sha256(source).hexdigest()
        except OSError as e:
            file_rows.append({
                "id": file_id,
                "path": rel_posix,
                "analysis": {"completeness": "failed", "parse_ok": False, "error": str(e)},
            })
            continue

        try:
            tree = parser.parse(source)
        except Exception as e:
            file_rows.append({
                "id": file_id,
                "path": rel_posix,
                "sha256": sha,
                "analysis": {"completeness": "failed", "parse_ok": False, "error": str(e)},
            })
            continue

        has_error = tree.root_node.has_error
        module_q = _ts_module_qualname(rel)

        file_rows.append({
            "id": file_id,
            "path": rel_posix,
            "sha256": sha,
            "analysis": {
                "completeness": "failed" if has_error else "complete",
                "parse_ok": not has_error,
            },
        })

        extractor = _SymbolExtractor(module_q, file_id, source)
        extractor.visit(tree.root_node)
        symbol_rows.extend(extractor.symbols)

        import_edges = _extract_imports(tree.root_node, source, module_q)
        for i, e in enumerate(import_edges):
            e["id"] = f"imp:{rel_posix}:{i}"
        edge_rows.extend(import_edges)

    return {
        "schema_version": 0,
        "indexer": "flowcode.ts_v0",
        "index_meta": {
            "completeness": "partial",
            "engine": "tree-sitter",
            "known_limits": [
                "Dynamic imports and require() calls are not traced.",
                "Type-only imports are not distinguished from value imports.",
                "Inferred arrow functions in object literals are not indexed.",
            ],
        },
        "root": str(repo_root),
        "files": file_rows,
        "symbols": symbol_rows,
        "edges": edge_rows,
    }
