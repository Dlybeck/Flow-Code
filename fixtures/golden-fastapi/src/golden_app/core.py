"""Pure logic tested without HTTP."""


def greeting_for(name: str) -> str:
    """Return a short greeting string."""
    cleaned = name.strip() or "world"
    return f"Hello, {cleaned}!"
