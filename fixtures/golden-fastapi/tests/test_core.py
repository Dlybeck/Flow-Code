from golden_app.core import greeting_for, goodbye_for

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


def test_greeting_trims_and_defaults() -> None:
    """Test that greeting_for properly trims whitespace and defaults to 'friend'."""
    # Test with trimmed name
    result = greeting_for("  Ada  ")
    expected_options = [g.format(name="Ada") for g in _GREETINGS]
    assert result in expected_options, f"Unexpected greeting: {result}"
    
    # Test with empty string
    result = greeting_for("")
    expected_options = [g.format(name="friend") for g in _GREETINGS]
    assert result in expected_options, f"Unexpected greeting: {result}"
    
    # Test with whitespace only
    result = greeting_for("   ")
    expected_options = [g.format(name="friend") for g in _GREETINGS]
    assert result in expected_options, f"Unexpected greeting: {result}"
    
    # Test with None
    result = greeting_for(None)
    expected_options = [g.format(name="friend") for g in _GREETINGS]
    assert result in expected_options, f"Unexpected greeting: {result}"


def test_goodbye_trims_and_defaults() -> None:
    """Test that goodbye_for properly trims whitespace and defaults to 'friend'."""
    # Test with trimmed name
    result = goodbye_for("  Ada  ")
    expected_options = [g.format(name="Ada") for g in _GOODBYES]
    assert result in expected_options, f"Unexpected goodbye: {result}"
    
    # Test with empty string
    result = goodbye_for("")
    expected_options = [g.format(name="friend") for g in _GOODBYES]
    assert result in expected_options, f"Unexpected goodbye: {result}"
    
    # Test with whitespace only
    result = goodbye_for("   ")
    expected_options = [g.format(name="friend") for g in _GOODBYES]
    assert result in expected_options, f"Unexpected goodbye: {result}"
    
    # Test with None
    result = goodbye_for(None)
    expected_options = [g.format(name="friend") for g in _GOODBYES]
    assert result in expected_options, f"Unexpected goodbye: {result}"
