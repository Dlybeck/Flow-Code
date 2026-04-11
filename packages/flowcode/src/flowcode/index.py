"""v0 indexer: stdlib `ast` only. Partial RAW — no type-aware refs (see README)."""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 0

# Phase 4: explicit limits of this indexer (SPEC §7) — never silent "complete graph".
INDEX_META_V0: dict[str, Any] = {
    "completeness": "partial",
    "engine": "ast",
    "known_limits": [
        "Structural AST only — no type-aware call graph.",
        "Import edges record static import / import-from statements only.",
        "Dynamic imports, reflection, and string-based imports are invisible.",
    ],
}

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
        "dist",
        "build",
        ".egg-info",
    }
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _posix_relpath(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def module_qualname_from_path(relpath: Path) -> str:
    """src/golden_app/app.py -> golden_app.app"""
    parts = list(relpath.parts)
    if parts[0] == "src":
        parts = parts[1:]
    if not parts or not parts[-1].endswith(".py"):
        return ""
    stem = parts[-1][:-3]
    if stem == "__init__":
        parts = parts[:-1]
    else:
        parts[-1] = stem
    return ".".join(parts) if parts else ""


@dataclass
class IndexBuild:
    root: Path
    files: list[dict[str, Any]] = field(default_factory=list)
    symbols: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "indexer": "flowcode.ast_v0",
            "index_meta": dict(INDEX_META_V0),
            "root": str(self.root.resolve()),
            "files": self.files,
            "symbols": self.symbols,
            "edges": self.edges,
        }


def _iter_py_files(root: Path, rel_roots: list[str]) -> list[Path]:
    out: list[Path] = []
    for rel in rel_roots:
        base = (root / rel).resolve()
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            out.append(p)
    return sorted(out, key=lambda x: str(x))


def _detect_src_roots(root: Path) -> list[str]:
    if (root / "src").is_dir():
        return ["src"]
    return ["."]


class _ModuleIndexer(ast.NodeVisitor):
    def __init__(
        self,
        *,
        file_id: str,
        relpath: str,
        module_q: str,
        symbols: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> None:
        self.file_id = file_id
        self.relpath = relpath
        self.module_q = module_q
        self.symbols = symbols
        self.edges = edges
        self._scope: list[str] = []

    def _qual(self, name: str) -> str:
        parts = [self.module_q] if self.module_q else []
        parts.extend(self._scope)
        parts.append(name)
        return ".".join(parts)

    def _add_symbol(self, kind: str, name: str, node: ast.AST) -> str:
        q = self._qual(name)
        sid = f"sym:{self.relpath}:{q}"
        lineno = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", lineno)
        self.symbols.append(
            {
                "id": sid,
                "kind": kind,
                "name": name,
                "qualified_name": q,
                "file_id": self.file_id,
                "line": lineno,
                "end_line": end,
            }
        )
        return sid

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            mod = alias.name.split(".")[0]
            self.edges.append(
                {
                    "kind": "import",
                    "from_file": self.file_id,
                    "module": mod,
                    "line": node.lineno,
                }
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = node.module or ""
        self.edges.append(
            {
                "kind": "import_from",
                "from_file": self.file_id,
                "module": base,
                "names": [a.name for a in node.names],
                "line": node.lineno,
                "level": node.level,
            }
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol("class", node.name, node)
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add_symbol("function", node.name, node)
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add_symbol("async_function", node.name, node)
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()


def index_repo(
    root: Path | str,
    *,
    src_roots: list[str] | None = None,
) -> dict[str, Any]:
    root_p = Path(root).resolve()
    rel_roots = src_roots if src_roots is not None else _detect_src_roots(root_p)
    build = IndexBuild(root=root_p)

    for path in _iter_py_files(root_p, rel_roots):
        rel = _posix_relpath(path, root_p)
        file_id = f"file:{rel}"
        data = path.read_bytes()
        file_row: dict[str, Any] = {
            "id": file_id,
            "path": rel,
            "sha256": _sha256_bytes(data),
        }
        mq = module_qualname_from_path(Path(rel))
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            file_row["analysis"] = {
                "completeness": "failed",
                "parse_ok": False,
                "error": f"utf-8 decode: {e}",
            }
            build.files.append(file_row)
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as e:
            file_row["analysis"] = {
                "completeness": "failed",
                "parse_ok": False,
                "error": f"{type(e).__name__}: {e}",
            }
            build.files.append(file_row)
            continue
        file_row["analysis"] = {
            "completeness": "complete",
            "parse_ok": True,
        }
        build.files.append(file_row)
        vis = _ModuleIndexer(
            file_id=file_id,
            relpath=rel,
            module_q=mq,
            symbols=build.symbols,
            edges=build.edges,
        )
        vis.visit(tree)

    return build.to_document()


def write_index(doc: dict[str, Any], out: Path | None) -> None:
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
