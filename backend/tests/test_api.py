from starlette.websockets import WebSocketDisconnect

from app.services import chat
from tests.conftest import auth, login, make_user, receive_until


# ---------------------------------------------------------------- auth
def test_register_login_and_me(client):
    token, _ = make_user(client, "alice")
    me = client.get("/api/v1/users/me", headers=auth(token)).json()
    assert me["username"] == "alice" and me["role"] == "USER"


def test_duplicate_username_is_case_insensitive(client):
    make_user(client, "alice")
    res = client.post("/api/v1/auth/register", json={"username": "ALICE", "email": "x@example.com", "password": "password123"})
    assert res.status_code == 409


def test_wrong_password_rejected_and_logged(client):
    make_user(client, "alice")
    assert client.post("/api/v1/auth/login", data={"username": "alice", "password": "nope-nope"}).status_code == 401
    admin = login(client, "root", "rootpass123")
    actions = [row["action"] for row in client.get("/api/v1/logs", headers=auth(admin)).json()]
    assert "LOGIN_FAILED" in actions


def test_admin_is_created_from_environment(client):
    admin = login(client, "root", "rootpass123")
    assert client.get("/api/v1/users/me", headers=auth(admin)).json()["role"] == "ADMIN"


# ---------------------------------------------------------------- chat
def test_messages_are_broadcast_and_stored(client):
    alice, _ = make_user(client, "alice")
    bob, _ = make_user(client, "bob")
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as a, client.websocket_connect(f"/api/v1/chat/ws?token={bob}") as b:
        a.send_json({"type": "message", "message": "hello bob"})
        event = receive_until(b, "message")
        assert event["message"]["message"] == "hello bob" and event["message"]["username"] == "alice"
    history = client.get("/api/v1/chat/history", headers=auth(alice)).json()
    assert [m["message"] for m in history] == ["hello bob"]


def test_invalid_token_closes_with_auth_code(client):
    with client.websocket_connect("/api/v1/chat/ws?token=bad") as ws:
        try:
            ws.receive_json()
            raise AssertionError("socket should be closed")
        except WebSocketDisconnect as exc:
            assert exc.code == chat.CLOSE_AUTH_FAILED


def test_history_pagination(client):
    alice, _ = make_user(client, "alice")
    for i in range(5):
        client.post("/api/v1/chat/messages", json={"message": f"m{i}"}, headers=auth(alice))
        chat.message_limiter.reset()
    newest = client.get("/api/v1/chat/history?limit=2", headers=auth(alice)).json()
    assert [m["message"] for m in newest] == ["m3", "m4"]
    older = client.get(f"/api/v1/chat/history?limit=2&before={newest[0]['id']}", headers=auth(alice)).json()
    assert [m["message"] for m in older] == ["m1", "m2"]


def test_rate_limit(client):
    alice, _ = make_user(client, "alice")
    codes = [client.post("/api/v1/chat/messages", json={"message": "spam"}, headers=auth(alice)).status_code for _ in range(10)]
    assert codes.count(201) == chat.settings.RATE_LIMIT_MESSAGES and codes[-1] == 429


# ---------------------------------------------------------------- bug fixes
def test_mute_applies_immediately_to_connected_user(client):
    """Old bug: the socket kept a stale user, so a mute had no effect until reconnect."""
    mod, _ = make_user(client, "mod", role="MODERATOR")
    alice, alice_id = make_user(client, "alice")
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as ws:
        receive_until(ws, "session")
        assert client.post(f"/api/v1/chat/moderation/{alice_id}/mute", json={"minutes": 5}, headers=auth(mod)).status_code == 200
        assert receive_until(ws, "session")["muted_seconds"] == 300
        ws.send_json({"type": "message", "message": "can I still talk?"})
        assert "muted" in receive_until(ws, "error")["message"]


def test_muted_user_can_still_connect_and_read(client):
    """Old bug: a muted user was rejected on connect and the page reconnected forever."""
    mod, _ = make_user(client, "mod", role="MODERATOR")
    alice, alice_id = make_user(client, "alice")
    client.post(f"/api/v1/chat/moderation/{alice_id}/mute", json={"minutes": 10}, headers=auth(mod))
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as ws:
        assert receive_until(ws, "session")["muted_seconds"] > 0
        assert receive_until(ws, "presence")["users"][0]["username"] == "alice"


def test_unmute(client):
    mod, _ = make_user(client, "mod", role="MODERATOR")
    alice, alice_id = make_user(client, "alice")
    client.post(f"/api/v1/chat/moderation/{alice_id}/mute", json={}, headers=auth(mod))
    client.post(f"/api/v1/chat/moderation/{alice_id}/unmute", headers=auth(mod))
    assert client.post("/api/v1/chat/messages", json={"message": "free!"}, headers=auth(alice)).status_code == 201


def test_warning_is_delivered_to_the_user(client):
    """Old bug: warnings were only logged; the user never saw them."""
    mod, _ = make_user(client, "mod", role="MODERATOR")
    alice, alice_id = make_user(client, "alice")
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as ws:
        receive_until(ws, "session")
        res = client.post(f"/api/v1/chat/moderation/{alice_id}/warn", json={"reason": "Be nice"}, headers=auth(mod))
        assert res.json()["delivered"] is True
        warning = receive_until(ws, "warning")["warning"]
        assert warning["reason"] == "Be nice" and warning["from_username"] == "mod"


def test_offline_user_sees_warning_when_they_return(client):
    mod, _ = make_user(client, "mod", role="MODERATOR")
    alice, alice_id = make_user(client, "alice")
    res = client.post(f"/api/v1/chat/moderation/{alice_id}/warn", json={"reason": "Spam"}, headers=auth(mod))
    assert res.json()["delivered"] is False
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as ws:
        warning = receive_until(ws, "warning")["warning"]
        assert warning["reason"] == "Spam"


def test_acknowledged_warning_is_not_shown_again(client):
    mod, _ = make_user(client, "mod", role="MODERATOR")
    alice, alice_id = make_user(client, "alice")
    client.post(f"/api/v1/chat/moderation/{alice_id}/warn", json={"reason": "Spam"}, headers=auth(mod))
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as ws:
        warning_id = receive_until(ws, "warning")["warning"]["id"]
    assert client.post(f"/api/v1/users/me/warnings/{warning_id}/acknowledge", headers=auth(alice)).status_code == 200
    # Someone else can't acknowledge it, and it can't be acknowledged twice.
    assert client.post(f"/api/v1/users/me/warnings/{warning_id}/acknowledge", headers=auth(mod)).status_code == 404
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as ws:
        assert ws.receive_json()["type"] == "session"
        assert ws.receive_json()["type"] == "presence"  # no warning in between


def test_disabling_account_disconnects_socket(client):
    admin = login(client, "root", "rootpass123")
    alice, alice_id = make_user(client, "alice")
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as ws:
        receive_until(ws, "session")
        client.patch(f"/api/v1/admin/users/{alice_id}/status", json={"is_active": False}, headers=auth(admin))
        try:
            for _ in range(10):
                ws.receive_json()
            raise AssertionError("socket should be closed")
        except WebSocketDisconnect as exc:
            assert exc.code == chat.CLOSE_ACCOUNT_DISABLED
    assert client.get("/api/v1/users/me", headers=auth(alice)).status_code == 403


def test_ai_failure_does_not_break_the_chat(client, monkeypatch):
    """Old bug: any AI error crashed the socket loop and disconnected the user."""

    async def broken_ai(prompt, asked_by):
        raise RuntimeError("OpenRouter is down")

    monkeypatch.setattr(chat, "generate_ai_reply", broken_ai)
    alice, _ = make_user(client, "alice")
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as ws:
        ws.send_json({"type": "message", "message": "@ai what is TCP?"})
        assert "couldn't answer" in receive_until(ws, "notice")["message"]
        ws.send_json({"type": "message", "message": "still here"})
        assert receive_until(ws, "message")["message"]["message"] in ("@ai what is TCP?", "still here")


def test_ai_reply_is_broadcast_and_rate_limited(client, monkeypatch):
    async def fake_ai(prompt, asked_by):
        return f"Answer for {asked_by}: {prompt}"

    monkeypatch.setattr(chat, "generate_ai_reply", fake_ai)
    alice, _ = make_user(client, "alice")
    with client.websocket_connect(f"/api/v1/chat/ws?token={alice}") as ws:
        ws.send_json({"type": "message", "message": "@ai explain Docker"})
        replies = []
        while len(replies) < 2:
            event = receive_until(ws, "message")
            replies.append(event["message"])
        assert replies[1]["sender_role"] == "AI" and replies[1]["message"] == "Answer for alice: explain Docker"
        ws.send_json({"type": "message", "message": "@ai again?"})
        assert "once every" in receive_until(ws, "error")["message"]


# ---------------------------------------------------------------- permissions
def test_moderator_cannot_mute_admin_or_moderator(client):
    mod, _ = make_user(client, "mod", role="MODERATOR")
    _, other_mod_id = make_user(client, "mod2", role="MODERATOR")
    res = client.post(f"/api/v1/chat/moderation/{other_mod_id}/mute", json={}, headers=auth(mod))
    assert res.status_code == 403


def test_regular_user_cannot_moderate_or_see_logs(client):
    alice, _ = make_user(client, "alice")
    _, bob_id = make_user(client, "bob")
    assert client.post(f"/api/v1/chat/moderation/{bob_id}/mute", json={}, headers=auth(alice)).status_code == 403
    assert client.get("/api/v1/logs", headers=auth(alice)).status_code == 403
    assert client.get("/api/v1/admin/users", headers=auth(alice)).status_code == 403


def test_admin_cannot_lock_themselves_out(client):
    admin = login(client, "root", "rootpass123")
    admin_id = client.get("/api/v1/users/me", headers=auth(admin)).json()["id"]
    assert client.patch(f"/api/v1/admin/users/{admin_id}/role", json={"role": "USER"}, headers=auth(admin)).status_code == 400
    assert client.patch(f"/api/v1/admin/users/{admin_id}/status", json={"is_active": False}, headers=auth(admin)).status_code == 400


def test_ai_role_cannot_be_assigned(client):
    admin = login(client, "root", "rootpass123")
    _, alice_id = make_user(client, "alice")
    assert client.patch(f"/api/v1/admin/users/{alice_id}/role", json={"role": "AI"}, headers=auth(admin)).status_code == 422


def test_moderator_can_delete_messages(client):
    mod, _ = make_user(client, "mod", role="MODERATOR")
    alice, _ = make_user(client, "alice")
    msg = client.post("/api/v1/chat/messages", json={"message": "bad words"}, headers=auth(alice)).json()
    assert client.delete(f"/api/v1/chat/messages/{msg['id']}", headers=auth(alice)).status_code == 403
    assert client.delete(f"/api/v1/chat/messages/{msg['id']}", headers=auth(mod)).status_code == 200
    assert client.get("/api/v1/chat/history", headers=auth(alice)).json() == []


def test_admin_stats_and_log_filter(client):
    admin = login(client, "root", "rootpass123")
    make_user(client, "alice")
    stats = client.get("/api/v1/admin/stats", headers=auth(admin)).json()
    assert stats["users"] == 2 and stats["admins"] == 1
    rows = client.get("/api/v1/logs?action=REGISTER", headers=auth(admin)).json()
    assert rows and all(r["action"] == "REGISTER" for r in rows)


def test_cors_allows_only_configured_frontend(client):
    ok = client.options("/api/v1/users/me", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    bad = client.options("/api/v1/users/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers
