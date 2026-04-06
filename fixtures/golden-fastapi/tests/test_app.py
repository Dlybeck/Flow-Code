from fastapi.testclient import TestClient

from golden_app.app import create_app

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


def test_health() -> None:
    """Test the health check endpoint returns OK status."""
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_greet() -> None:
    """Test the greet endpoint returns correct greeting message."""
    client = TestClient(create_app())
    r = client.get("/greet/Bob")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    expected_options = [g.format(name="Bob") for g in _GREETINGS]
    assert data["message"] in expected_options, f"Unexpected greeting: {data['message']}"

    # Test greeting without name
    r = client.get("/greet/")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    expected_options = [g.format(name="friend") for g in _GREETINGS]
    assert data["message"] in expected_options, f"Unexpected greeting: {data['message']}"


def test_goodbye() -> None:
    """Test the goodbye endpoint returns correct farewell message."""
    client = TestClient(create_app())
    r = client.get("/goodbye/Bob")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    expected_options = [g.format(name="Bob") for g in _GOODBYES]
    assert data["message"] in expected_options, f"Unexpected goodbye: {data['message']}"

    # Test goodbye without name
    r = client.get("/goodbye/")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    expected_options = [g.format(name="friend") for g in _GOODBYES]
    assert data["message"] in expected_options, f"Unexpected goodbye: {data['message']}"
