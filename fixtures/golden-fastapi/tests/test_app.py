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
    # Bob has length 3, which gives index 3 -> "Greetings, Bob!"
    assert r.json() == {"message": "Greetings, Bob!"}


def test_greet_default() -> None:
    client = TestClient(create_app())
    r = client.get("/greet/")
    assert r.status_code == 200
    # Default name is "world" which has length 5, 5 % 5 = 0 -> "Hello, world!"
    assert r.json() == {"message": "Hello, world!"}


def test_goodbye() -> None:
    client = TestClient(create_app())
    r = client.get("/goodbye/Alice")
    assert r.status_code == 200
    # Alice has length 5, 5 % 5 = 0 -> "Goodbye, Alice!"
    assert r.json() == {"message": "Goodbye, Alice!"}


def test_goodbye_default() -> None:
    client = TestClient(create_app())
    r = client.get("/goodbye/")
    assert r.status_code == 200
    # Default name is "world" which has length 5, 5 % 5 = 0 -> "Goodbye, world!"
    assert r.json() == {"message": "Goodbye, world!"}
