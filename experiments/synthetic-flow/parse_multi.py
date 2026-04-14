"""Parse a directory of Python files. Returns functions keyed by qualified name.

Keying:
  - module-level function `foo` in file `pkg/mod.py` → "foo" (file path stored alongside)
  - method `bar` of class `Baz` → "Baz.bar"

We key by name suffix (not full module path) because the ground-truth flow uses
short names. Collisions within this codebase are checked and reported.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FuncInfo:
    qname: str
    file: str
    docstring: str
    source: str


def _extract_source(src_lines: list[str], node: ast.AST) -> str:
    start = node.lineno - 1
    end = node.end_lineno or (start + 1)
    return "\n".join(src_lines[start:end])


def parse_directory(root: Path) -> dict[str, FuncInfo]:
    out: dict[str, FuncInfo] = {}
    collisions: dict[str, list[str]] = {}

    for py in sorted(root.rglob("*.py")):
        if ".venv" in py.parts or "__pycache__" in py.parts:
            continue
        try:
            src = py.read_text()
            tree = ast.parse(src)
        except (SyntaxError, UnicodeDecodeError):
            continue
        src_lines = src.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Class method? Walk parents to find enclosing class
                # ast doesn't give parents, so do a separate pass
                pass

        # Do a pass for module-level functions and class methods separately
        for top in tree.body:
            if isinstance(top, ast.FunctionDef):
                qname = top.name
                info = FuncInfo(
                    qname=qname,
                    file=str(py.relative_to(root)),
                    docstring=ast.get_docstring(top) or "",
                    source=_extract_source(src_lines, top),
                )
                collisions.setdefault(qname, []).append(info.file)
                out[qname] = info
            elif isinstance(top, ast.ClassDef):
                cls = top.name
                for item in top.body:
                    if isinstance(item, ast.FunctionDef):
                        qname = f"{cls}.{item.name}"
                        info = FuncInfo(
                            qname=qname,
                            file=str(py.relative_to(root)),
                            docstring=ast.get_docstring(item) or "",
                            source=_extract_source(src_lines, item),
                        )
                        collisions.setdefault(qname, []).append(info.file)
                        out[qname] = info

    # Report duplicates (different files with same qname)
    dups = {k: v for k, v in collisions.items() if len(set(v)) > 1}
    if dups:
        print("WARNING: qname collisions across files:")
        for k, files in dups.items():
            print(f"  {k}: {files}")
    return out
