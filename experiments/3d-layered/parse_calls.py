"""Parse a directory of Python files into functions + call edges.

Extends the earlier parse_multi. Keys functions by qname (module-level name or
`ClassName.method`). Call edges resolved heuristically:
  - `self.foo()` inside class Bar → `Bar.foo` (if it exists)
  - `foo()` for a known module-level function → `foo`
  - `obj.foo()` for any `.foo` matching one known method → that method
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FuncInfo:
    qname: str
    file: str
    class_name: str | None
    docstring: str
    source: str
    calls: list[str] = field(default_factory=list)


def _source(lines: list[str], node: ast.AST) -> str:
    start = (node.lineno or 1) - 1
    end = node.end_lineno or (start + 1)
    return "\n".join(lines[start:end])


# Method names that are almost always dict / stdlib / third-party calls in Python.
# If one of these appears on a non-self receiver we refuse to match it even if it's
# unique in the known set — otherwise a single user-defined `MyClass.get` gets linked
# to every `dict.get()`, `config.get()`, `os.environ.get()` in the whole codebase,
# creating phantom architectural spines.
_GENERIC_METHOD_NAMES = frozenset({
    "get", "set", "update", "pop", "popitem", "keys", "values", "items", "setdefault",
    "append", "extend", "insert", "remove", "index", "count", "clear", "copy", "sort",
    "add", "discard", "union", "intersection", "difference",
    "load", "loads", "dump", "dumps", "save", "read", "write", "close", "open",
    "encode", "decode", "strip", "split", "join", "format", "replace", "startswith",
    "endswith", "lower", "upper", "find", "rfind",
    "send", "recv", "start", "stop", "run", "execute", "call", "apply",
    "next", "iter", "__init__", "__enter__", "__exit__",
})


def _collect_callees(fn_node: ast.FunctionDef, class_name: str | None, known: set[str]) -> list[str]:
    out: set[str] = set()
    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        candidate: str | None = None
        if isinstance(f, ast.Name):
            # bare_call()
            if f.id in known:
                candidate = f.id
        elif isinstance(f, ast.Attribute):
            # obj.method() — try class context first
            if (
                isinstance(f.value, ast.Name)
                and f.value.id == "self"
                and class_name
                and f"{class_name}.{f.attr}" in known
            ):
                candidate = f"{class_name}.{f.attr}"
            elif isinstance(f.value, ast.Name) and f.attr not in _GENERIC_METHOD_NAMES:
                # Simple-receiver call like `parser.add_argument()` or `env.log_error()`.
                # We require the receiver to be a plain Name (not a chained Attribute like
                # `env.config.get()`) — chains usually traverse into third-party types,
                # where matching against the user's codebase creates phantom edges.
                matches = [k for k in known if k.endswith(f".{f.attr}") or k == f.attr]
                if len(matches) == 1:
                    candidate = matches[0]
        if candidate:
            out.add(candidate)
    return sorted(out)


def parse_directory(root: Path) -> dict[str, FuncInfo]:
    # Pass 1: collect all qnames
    files: list[tuple[Path, ast.AST, list[str]]] = []
    for py in sorted(root.rglob("*.py")):
        if any(skip in py.parts for skip in (".venv", "__pycache__", "site-packages")):
            continue
        try:
            src = py.read_text()
            tree = ast.parse(src)
        except (SyntaxError, UnicodeDecodeError):
            continue
        files.append((py, tree, src.splitlines()))

    known: set[str] = set()
    for _py, tree, _lines in files:
        for top in tree.body:
            if isinstance(top, ast.FunctionDef):
                known.add(top.name)
            elif isinstance(top, ast.ClassDef):
                for item in top.body:
                    if isinstance(item, ast.FunctionDef):
                        known.add(f"{top.name}.{item.name}")

    # Pass 2: extract info + call edges
    out: dict[str, FuncInfo] = {}
    for py, tree, lines in files:
        rel = str(py.relative_to(root))
        for top in tree.body:
            if isinstance(top, ast.FunctionDef):
                out[top.name] = FuncInfo(
                    qname=top.name,
                    file=rel,
                    class_name=None,
                    docstring=ast.get_docstring(top) or "",
                    source=_source(lines, top),
                    calls=_collect_callees(top, None, known),
                )
            elif isinstance(top, ast.ClassDef):
                for item in top.body:
                    if isinstance(item, ast.FunctionDef):
                        qn = f"{top.name}.{item.name}"
                        out[qn] = FuncInfo(
                            qname=qn,
                            file=rel,
                            class_name=top.name,
                            docstring=ast.get_docstring(item) or "",
                            source=_source(lines, item),
                            calls=_collect_callees(item, top.name, known),
                        )
    return out
