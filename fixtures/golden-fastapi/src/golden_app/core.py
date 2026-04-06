"""Pure logic tested without HTTP."""


def greeting_for(name: str | None) -> str:
    """Return a short greeting string."""
    if name is None:
        name = "friend"
    name = name.strip()
    if not name:
        name = "friend"
    return f"Hello, {name}!"


def goodbye_for(name: str | None) -> str:
    """Return a short goodbye string."""
    if name is None:
        name = "friend"
    name = name.strip()
    if not name:
        name = "friend"
    return f"Goodbye, {name}!"
