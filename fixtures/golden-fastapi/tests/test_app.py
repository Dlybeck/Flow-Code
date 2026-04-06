from fastapi.testclient import TestClient

from golden_app.app import create_app


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
    assert r.json() == {"message": "Hello, Bob!"}

    # Test greeting without name
    r = client.get("/greet/")
    assert r.status_code == 200
    assert r.json() == {"message": "Hello, friend!"}


def test_goodbye() -> None:
    """Test the goodbye endpoint returns correct farewell message."""
    client = TestClient(create_app())
    r = client.get("/goodbye/Bob")
    assert r.status_code == 200
    assert r.json() == {"message": "Goodbye, Bob!"}

    # Test goodbye without name
    r = client.get("/goodbye/")
    assert r.status_code == 200
    assert r.json() == {"message": "Goodbye, friend!"}
