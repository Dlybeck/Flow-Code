"""Single-language tree-sitter adapters for Java, C, C#, and Haskell.

The adapter emits the same RAW shape as the Python and browser indexers. It
records conservative direct call sites beside symbols so the language-neutral
IR conversion does not need to parse source a second time.
"""

from __future__ import annotations

import hashlib
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flowcode.sources import source_files


@dataclass(frozen=True)
class LanguageSpec:
    name: str
    extensions: frozenset[str]
    grammar_module: str
    function_types: frozenset[str]
    call_types: frozenset[str]
    container_types: frozenset[str]
    known_limits: tuple[str, ...]


LANGUAGE_SPECS: dict[str, LanguageSpec] = {
    "java": LanguageSpec(
        "java",
        frozenset({".java"}),
        "tree_sitter_java",
        frozenset({"method_declaration", "constructor_declaration"}),
        frozenset({"method_invocation"}),
        frozenset(
            {
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
                "record_declaration",
            }
        ),
        (
            "Overload resolution and dynamic dispatch are not type-aware.",
            "Calls through objects, reflection, and generated sources can remain unresolved.",
        ),
    ),
    "c": LanguageSpec(
        "c",
        frozenset({".c", ".h"}),
        "tree_sitter_c",
        frozenset({"function_definition"}),
        frozenset({"call_expression"}),
        frozenset(),
        (
            "Function pointers, macros, conditional compilation, and generated sources are not resolved.",
            "Headers are indexed as selected source and can duplicate declarations implemented elsewhere.",
        ),
    ),
    "csharp": LanguageSpec(
        "csharp",
        frozenset({".cs"}),
        "tree_sitter_c_sharp",
        frozenset(
            {"method_declaration", "constructor_declaration", "local_function_statement"}
        ),
        frozenset({"invocation_expression"}),
        frozenset(
            {
                "namespace_declaration",
                "class_declaration",
                "struct_declaration",
                "interface_declaration",
                "record_declaration",
            }
        ),
        (
            "Overload resolution, delegates, LINQ lowering, and dynamic dispatch are not type-aware.",
            "Generated code and framework wiring can remain unresolved.",
        ),
    ),
    "haskell": LanguageSpec(
        "haskell",
        frozenset({".hs"}),
        "tree_sitter_haskell",
        frozenset({"function", "bind"}),
        frozenset({"apply"}),
        frozenset(),
        (
            "Higher-order calls, operators, typeclass dispatch, and Template Haskell are not resolved.",
            "Only named top-level function and bind declarations are indexed.",
        ),
    ),
}

COMPILED_EXTENSIONS = frozenset(
    extension for spec in LANGUAGE_SPECS.values() for extension in spec.extensions
)


def language_for_path(path: Path) -> str | None:
    for name, spec in LANGUAGE_SPECS.items():
        if path.suffix in spec.extensions:
            return name
    return None


def _parser(spec: LanguageSpec):
    try:
        import tree_sitter

        grammar = importlib.import_module(spec.grammar_module)
    except ImportError as exc:
        raise ImportError(
            f"{spec.name} indexing requires the flowcode[languages] dependencies"
        ) from exc
    return tree_sitter.Parser(tree_sitter.Language(grammar.language()))


def _text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _declarator_name(node: Any, source: bytes) -> str | None:
    current = node.child_by_field_name("declarator") or node.child_by_field_name("name")
    while current is not None:
        if current.type in {"identifier", "field_identifier", "type_identifier", "variable"}:
            return _text(current, source)
        current = current.child_by_field_name("declarator") or current.child_by_field_name("name")
    return None


def _name(node: Any, source: bytes) -> str | None:
    named = node.child_by_field_name("name")
    if named is not None:
        return _text(named, source)
    return _declarator_name(node, source)


def _file_prefix(relative: Path, language: str) -> list[str]:
    parts = list(relative.with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if language in {"java", "csharp"}:
        return parts[:-1]
    return parts


def _declared_prefix(root: Any, source: bytes, language: str) -> list[str]:
    for child in root.named_children:
        if language == "java" and child.type == "package_declaration":
            name = next(
                (
                    part
                    for part in child.named_children
                    if part.type in {"identifier", "scoped_identifier"}
                ),
                None,
            )
            if name is not None:
                return _text(name, source).split(".")
        if language == "csharp" and child.type == "file_scoped_namespace_declaration":
            name = child.child_by_field_name("name")
            if name is not None:
                return _text(name, source).split(".")
    return []


def _containers(node: Any, source: bytes, spec: LanguageSpec) -> list[str]:
    result: list[str] = []
    current = node.parent
    while current is not None:
        if current.type in spec.container_types:
            name = _name(current, source)
            if name:
                result.append(name)
        current = current.parent
    result.reverse()
    return result


def _java_arity(node: Any, *, call: bool) -> int | None:
    container = node.child_by_field_name('arguments' if call else 'parameters')
    if container is None:
        return None
    parameters = [child for child in container.named_children if child.type != 'comment']
    if any(child.type == 'spread_parameter' for child in parameters):
        return None
    return len(parameters)


def _java_receiver_type(call: Any, function: Any, source: bytes) -> str | None:
    """Use a unique explicit local/parameter type, never a method-name match.

    This deliberately excludes fields, chained expressions, implicit imports and
    shadowed locals. A declared type is a candidate, not proof of runtime dispatch.
    """
    receiver = call.child_by_field_name('object')
    if receiver is None or receiver.type != 'identifier':
        return None
    name = _text(receiver, source)
    bindings = []
    pending = list(function.named_children)
    while pending:
        node = pending.pop()
        if node.type in {'class_declaration', 'method_declaration', 'lambda_expression'}:
            continue
        variable = node.child_by_field_name('name')
        if variable is not None and _text(variable, source) == name:
            type_node = node.child_by_field_name('type')
            if node.type == 'variable_declarator':
                type_node = node.parent.child_by_field_name('type')
            if node.type in {'formal_parameter', 'variable_declarator', 'catch_formal_parameter'}:
                scope = function if node.type == 'formal_parameter' else node.parent.parent if node.type == 'variable_declarator' else node.parent
                visible = scope.start_byte <= call.start_byte and call.end_byte <= scope.end_byte
                if visible and node.end_byte < call.start_byte:
                    bindings.append(_text(type_node, source) if type_node is not None else None)
        pending.extend(node.named_children)
    if len(bindings) == 1 and bindings[0]:
        return bindings[0].split('<', 1)[0].strip()
    return None


def _direct_callee(node: Any, source: bytes, language: str) -> tuple[str, bool] | None:
    if language == "java":
        name = node.child_by_field_name("name")
        if name is None:
            return None
        receiver = node.child_by_field_name("object")
        return _text(name, source), receiver is None or _text(receiver, source) == "this"
    if language == "c":
        function = node.child_by_field_name("function")
        if function is None:
            return None
        return _text(function, source), function.type == "identifier"
    if language == "csharp":
        function = node.child_by_field_name("function")
        if function is None:
            return None
        value = _text(function, source)
        if function.type == "identifier":
            return value, True
        return value.rsplit(".", 1)[-1], value.startswith("this.")
    if language == "haskell":
        function = node.child_by_field_name("function")
        if function is None:
            return None
        return _text(function, source), function.type in {"variable", "constructor"}
    return None


def _calls(function: Any, source: bytes, spec: LanguageSpec) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if node is not function and node.type in spec.function_types:
            return
        if node.type in spec.call_types:
            callee = _direct_callee(node, source, spec.name)
            if callee is not None:
                name, direct = callee
                calls.append(
                    {
                        "callee": name,
                        "direct": direct,
                        **({"arity": _java_arity(node, call=True), "receiver_type": _java_receiver_type(node, function, source)} if spec.name == "java" else {}),
                        "line": node.start_point[0] + 1,
                    }
                )
        for child in node.named_children:
            visit(child)

    visit(function)
    return sorted(calls, key=lambda item: (item["line"], item["callee"]))


def index_treesitter_repo(
    repo_root: Path | str,
    *,
    language: str,
    src_roots: list[str] | None = None,
) -> dict[str, Any]:
    """Index one supported compiled/functional language into the RAW schema."""
    if language not in LANGUAGE_SPECS:
        raise ValueError(f"Unsupported tree-sitter language: {language}")
    spec = LANGUAGE_SPECS[language]
    parser = _parser(spec)
    root = Path(repo_root).resolve()
    roots = src_roots if src_roots is not None else ["src"] if (root / "src").is_dir() else ["."]
    files = source_files(root, roots, spec.extensions)
    file_rows: list[dict[str, Any]] = []
    symbols: list[dict[str, Any]] = []

    for path in files:
        relative = path.relative_to(root)
        rel = relative.as_posix()
        file_id = f"file:{rel}"
        try:
            source = path.read_bytes()
        except OSError as exc:
            file_rows.append(
                {
                    "id": file_id,
                    "path": rel,
                    "analysis": {"completeness": "failed", "parse_ok": False, "error": str(exc)},
                }
            )
            continue
        sha = hashlib.sha256(source).hexdigest()
        tree = parser.parse(source)
        parse_ok = not tree.root_node.has_error
        file_rows.append(
            {
                "id": file_id,
                "path": rel,
                "sha256": sha,
                "analysis": {
                    "completeness": "partial" if parse_ok else "failed",
                    "parse_ok": parse_ok,
                },
            }
        )
        if not parse_ok:
            continue
        prefix = _declared_prefix(tree.root_node, source, language) or _file_prefix(
            relative, language
        )
        stack = [tree.root_node]
        seen: dict[str, int] = {}
        symbol_indexes: dict[str, int] = {}
        while stack:
            node = stack.pop()
            stack.extend(reversed(node.named_children))
            if node.type not in spec.function_types:
                continue
            name = _name(node, source)
            if not name:
                continue
            parts = [*prefix, *_containers(node, source, spec), name]
            qualified = ".".join(part for part in parts if part)
            calls = _calls(node, source, spec)
            if language == "haskell" and qualified in symbol_indexes:
                existing = symbols[symbol_indexes[qualified]]
                existing["line"] = min(existing["line"], node.start_point[0] + 1)
                existing["end_line"] = max(existing["end_line"], node.end_point[0] + 1)
                existing["calls"] = sorted(
                    [*existing["calls"], *calls],
                    key=lambda item: (item["line"], item["callee"]),
                )
                continue
            count = seen.get(qualified, 0)
            seen[qualified] = count + 1
            stable_qualified = qualified if count == 0 else f"{qualified}$overload_{count + 1}"
            symbol_indexes[qualified] = len(symbols)
            symbols.append(
                {
                    "id": f"sym:{rel}:{stable_qualified}",
                    "kind": "function",
                    "name": name,
                    "qualified_name": stable_qualified,
                    "file_id": file_id,
                    "language": language,
                    "line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "column": node.start_point[1] + 1,
                    "end_column": node.end_point[1] + 1,
                    "calls": calls,
                    **({"arity": _java_arity(node, call=False)} if language == "java" else {}),
                }
            )

    return {
        "schema_version": 0,
        "indexer": f"flowcode.{language}_treesitter_v0",
        "language": language,
        "index_meta": {
            "completeness": "partial",
            "engine": "tree-sitter",
            "known_limits": list(spec.known_limits),
        },
        "root": str(root),
        "files": file_rows,
        "symbols": symbols,
        "edges": [],
    }
