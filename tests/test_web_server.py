"""Smoke test del servidor FastAPI."""
from fastapi.testclient import TestClient

from src.web_server import create_app


class _FakeState:
    paused = False
    enhancer_enabled = True
    groq = object()


def test_create_app_state_endpoint():
    app = create_app(_FakeState())
    client = TestClient(app)
    r = client.get("/api/state")
    assert r.status_code == 200
    assert r.json() == {
        "paused": False,
        "enhancer_enabled": True,
        "groq_available": True,
    }


def test_create_app_root_returns_placeholder_when_no_index():
    app = create_app(_FakeState())
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Batcave" in r.text


def test_create_app_state_endpoint_no_groq():
    class S:
        paused = True
        enhancer_enabled = False
        groq = None
    app = create_app(S())
    client = TestClient(app)
    r = client.get("/api/state")
    assert r.json() == {
        "paused": True,
        "enhancer_enabled": False,
        "groq_available": False,
    }
