from golden_app.core import greeting_for


def test_greeting_trims_and_defaults() -> None:
    assert greeting_for("  Ada  ") == "Hello, Ada!"
    assert greeting_for("") == "Hello, world!"
    assert greeting_for("   ") == "Hello, world!"
