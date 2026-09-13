"""Shared browser syntax identities for indexing and call attribution."""

FUNCTION_EXPRESSIONS = frozenset(
    {"function", "function_expression", "arrow_function", "generator_function"}
)


def expression_name(node, source: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is not None:
        return source[name.start_byte : name.end_byte].decode("utf-8", errors="replace")
    return f"$callback_{node.start_point[0] + 1}_{node.start_point[1] + 1}"
