"""Pure logic tested without HTTP."""

import random

_GREETINGS = [
    "Hello, {name}!",
    "Hi there, {name}!",
    "Greetings, {name}!",
    "Hey {name}!",
    "Howdy {name}!",
]

_GOODBYES = [
    "Goodbye, {name}!",
    "Farewell, {name}!",
    "See you later, {name}!",
    "Bye {name}!",
    "Take care, {name}!",
]


def greeting_for(name: str | None) -> str:
    """Return a short greeting string."""
    if name is None:
        name = "friend"
    name = name.strip()
    if not name:
        name = "friend"
    template = random.choice(_GREETINGS)
    return template.format(name=name)


def goodbye_for(name: str | None) -> str:
    """Return a short goodbye string."""
    if name is None:
        name = "friend"
    name = name.strip()
    if not name:
        name = "friend"
    template = random.choice(_GOODBYES)
    return template.format(name=name)
