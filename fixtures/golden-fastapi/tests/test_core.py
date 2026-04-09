from golden_app.core import greeting_for, goodbye_for


def test_greeting_trims_and_defaults() -> None:
    """Test that greeting_for properly trims whitespace and defaults to 'friend'."""
    assert greeting_for("  Ada  ") == "Hello, Ada!"
    assert greeting_for("") == "Hello, friend!"
    assert greeting_for("   ") == "Hello, friend!"
    assert greeting_for(None) == "Hello, friend!"


def test_goodbye_trims_and_defaults() -> None:
    """Test that goodbye_for properly trims whitespace and defaults to 'friend'."""
    assert goodbye_for("  Ada  ") == "Goodbye, Ada!"
    assert goodbye_for("") == "Goodbye, friend!"
    assert goodbye_for("   ") == "Goodbye, friend!"
    assert goodbye_for(None) == "Goodbye, friend!"
