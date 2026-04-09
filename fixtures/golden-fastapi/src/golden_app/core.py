"""Pure logic tested without HTTP."""


def greeting_for(name: str | None) -> str:
    """Return a short greeting string."""
    if name is None:
        cleaned = "world"
    else:
        cleaned = name.strip() or "world"
    # Choose greeting based on the length of the cleaned name for deterministic variety
    greetings = [
        f"Hello, {cleaned}!",
        f"Hi, {cleaned}!",
        f"Welcome, {cleaned}!",
        f"Greetings, {cleaned}!",
        f"Hey there, {cleaned}!",
    ]
    # Use the length of the name modulo number of greetings to pick deterministically
    index = len(cleaned) % len(greetings)
    return greetings[index]


def goodbye_for(name: str | None) -> str:
    """Return a short goodbye string."""
    if name is None:
        cleaned = "world"
    else:
        cleaned = name.strip() or "world"
    # Choose goodbye based on the length of the cleaned name for deterministic variety
    goodbyes = [
        f"Goodbye, {cleaned}!",
        f"Farewell, {cleaned}!",
        f"See you later, {cleaned}!",
        f"Take care, {cleaned}!",
        f"Bye, {cleaned}!",
    ]
    # Use the length of the name modulo number of goodbyes to pick deterministically
    index = len(cleaned) % len(goodbyes)
    return goodbyes[index]
