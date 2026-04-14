"""Parse a single-file Python codebase into functions + static call edges."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FuncInfo:
    name: str
    docstring: str
    source: str
    calls: list[str]  # names of functions called from within this function


def parse_codebase(path: Path) -> dict[str, FuncInfo]:
    src = path.read_text()
    tree = ast.parse(src)
    source_lines = src.splitlines()

    functions: dict[str, FuncInfo] = {}
    func_names: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            func_names.add(node.name)

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        doc = ast.get_docstring(node) or ""
        start = node.lineno - 1
        end = node.end_lineno or (start + 1)
        source = "\n".join(source_lines[start:end])

        calls: list[str] = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name) and func.id in func_names:
                    if func.id not in calls:
                        calls.append(func.id)
        functions[node.name] = FuncInfo(
            name=node.name, docstring=doc, source=source, calls=calls
        )
    return functions
