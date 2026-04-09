from fastapi.testclient import TestClient

from golden_app.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_greet() -> None:
    client = TestClient(create_app())
    r = client.get("/greet/Bob")
    assert r.status_code == 200
    assert r.json() == {"message": "Hello, Bob!"}
