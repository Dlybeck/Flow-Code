from golden_app.core import greeting_for, goodbye_for


def test_greeting_trims_and_defaults() -> None:
    # Test trimming
    assert greeting_for("  Ada  ") in [
        "Hello, Ada!",
        "Hi, Ada!",
        "Welcome, Ada!",
        "Greetings, Ada!",
        "Hey there, Ada!",
    ]
    # Test empty string
    assert greeting_for("") in [
        "Hello, world!",
        "Hi, world!",
        "Welcome, world!",
        "Greetings, world!",
        "Hey there, world!",
    ]
    # Test whitespace
    assert greeting_for("   ") in [
        "Hello, world!",
        "Hi, world!",
        "Welcome, world!",
        "Greetings, world!",
        "Hey there, world!",
    ]
    # Test None
    assert greeting_for(None) in [
        "Hello, world!",
        "Hi, world!",
        "Welcome, world!",
        "Greetings, world!",
        "Hey there, world!",
    ]


def test_goodbye_trims_and_defaults() -> None:
    # Test trimming
    assert goodbye_for("  Bob  ") in [
        "Goodbye, Bob!",
        "Farewell, Bob!",
        "See you later, Bob!",
        "Take care, Bob!",
        "Bye, Bob!",
    ]
    # Test empty string
    assert goodbye_for("") in [
        "Goodbye, world!",
        "Farewell, world!",
        "See you later, world!",
        "Take care, world!",
        "Bye, world!",
    ]
    # Test whitespace
    assert goodbye_for("   ") in [
        "Goodbye, world!",
        "Farewell, world!",
        "See you later, world!",
        "Take care, world!",
        "Bye, world!",
    ]
    # Test None
    assert goodbye_for(None) in [
        "Goodbye, world!",
        "Farewell, world!",
        "See you later, world!",
        "Take care, world!",
        "Bye, world!",
    ]


def test_greeting_variety() -> None:
    # Test that different names produce different greetings (deterministically)
    # "Ada" has length 3, 3 % 5 = 3 -> "Greetings, Ada!"
    assert greeting_for("Ada") == "Greetings, Ada!"
    # "Bob" has length 3, 3 % 5 = 3 -> "Greetings, Bob!"
    assert greeting_for("Bob") == "Greetings, Bob!"
    # "Charlie" has length 7, 7 % 5 = 2 -> "Welcome, Charlie!"
    assert greeting_for("Charlie") == "Welcome, Charlie!"


def test_goodbye_variety() -> None:
    # Test that different names produce different goodbyes (deterministically)
    # "Ada" has length 3, 3 % 5 = 3 -> "Take care, Ada!"
    assert goodbye_for("Ada") == "Take care, Ada!"
    # "Bob" has length 3, 3 % 5 = 3 -> "Take care, Bob!"
    assert goodbye_for("Bob") == "Take care, Bob!"
    # "Charlie" has length 7, 7 % 5 = 2 -> "See you later, Charlie!"
    assert goodbye_for("Charlie") == "See you later, Charlie!"
