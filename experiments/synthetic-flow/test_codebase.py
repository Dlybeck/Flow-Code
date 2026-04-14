"""Tiny signup flow for the synthetic-vs-actual flow experiment.

Intentionally clear names + docstrings so a reader (human or LLM) can
predict the execution flow from semantics alone.
"""

_USER_DB: dict[str, dict] = {}


def handle_signup(data):
    """Entry point: handles a new user signup request."""
    if not validate_input(data):
        return log_invalid_input(data)

    if check_user_exists(data["email"]):
        return return_conflict_error(data["email"])

    user = create_user(data)
    send_welcome_email(user)
    return user


def validate_input(data):
    """Check that a signup payload has the required fields."""
    return "email" in data and "password" in data


def log_invalid_input(data):
    """Record a rejected signup attempt for later debugging."""
    print(f"invalid signup: {data}")
    return None


def check_user_exists(email):
    """Return True if a user with this email is already registered."""
    return email in _USER_DB


def return_conflict_error(email):
    """Produce an error response indicating the email is already taken."""
    return {"error": "conflict", "email": email}


def create_user(data):
    """Persist a new user record to the user database."""
    _USER_DB[data["email"]] = data
    return data


def send_welcome_email(user):
    """Send a welcome email to a newly-registered user."""
    print(f"welcome {user['email']}")
