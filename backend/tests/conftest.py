import os

# Use the in-memory MongoDB mock and fixed settings for every test.
os.environ["MONGODB_URI"] = "mongomock://"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["ADMIN_USERNAME"] = "root"
os.environ["ADMIN_EMAIL"] = "root@example.com"
os.environ["ADMIN_PASSWORD"] = "rootpass123"
os.environ["OPENROUTER_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import chat  # noqa: E402


@pytest.fixture
def client():
    chat.message_limiter.reset()
    chat.ai_limiter.reset()
    chat.manager.sockets.clear()
    chat.manager.profiles.clear()
    with TestClient(app) as test_client:  # fresh in-memory database per test
        yield test_client


def login(client, username, password="password123"):
    res = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_user(client, username, role=None):
    """Registers a user (optionally promoted by the admin) and returns (token, id)."""
    res = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "password123"},
    )
    assert res.status_code == 201, res.text
    user_id = res.json()["id"]
    if role:
        admin_token = login(client, "root", "rootpass123")
        assert client.patch(f"/api/v1/admin/users/{user_id}/role", json={"role": role}, headers=auth(admin_token)).status_code == 200
    return login(client, username), user_id


def receive_until(ws, wanted_type, limit=20):
    for _ in range(limit):
        event = ws.receive_json()
        if event["type"] == wanted_type:
            return event
    raise AssertionError(f"No {wanted_type!r} event received")
