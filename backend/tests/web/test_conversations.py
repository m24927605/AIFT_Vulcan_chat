from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web.routes import conversations


_DEFAULT_SESSION = {
    "session_id": "test-session", "ua_hash": "h", "ip_prefix": "127.0",
    "created_at": 0, "last_seen_at": 0, "expires_at": 999999999999,
    "rotated_to": None, "revoked_at": None, "telegram_chat_id": None,
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(conversations.router)
    storage = AsyncMock()
    storage.get_web_session.return_value = _DEFAULT_SESSION
    app.state.conversation_storage = storage
    with TestClient(app) as c:
        yield c, storage


def test_list_without_ids_returns_all_for_session(client):
    c, storage = client
    storage.list_conversations_by_web_owner.return_value = [
        {"id": "conv-1", "title": "First", "telegram_chat_id": None, "created_at": "2026-03-03"},
        {"id": "conv-2", "title": "Second", "telegram_chat_id": 123, "created_at": "2026-03-03"},
    ]
    r = c.get("/api/conversations")
    assert r.status_code == 200
    data = r.json()
    assert len(data["conversations"]) == 2


def test_list_with_ids_filters_for_session(client):
    c, storage = client
    storage.list_conversations_by_web_owner.return_value = [
        {"id": "conv-1", "title": "First", "telegram_chat_id": None, "created_at": "2026-03-03"},
        {"id": "conv-2", "title": "Second", "telegram_chat_id": 123, "created_at": "2026-03-03"},
    ]
    r = c.get("/api/conversations?ids=conv-2")
    assert r.status_code == 200
    data = r.json()
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["id"] == "conv-2"


def test_list_returns_session_telegram_chat_id(client):
    c, storage = client
    storage.get_web_session.return_value = {
        "session_id": "s1", "ua_hash": "h", "ip_prefix": "127.0",
        "created_at": 0, "last_seen_at": 0, "expires_at": 999999999999,
        "rotated_to": None, "revoked_at": None, "telegram_chat_id": 12345,
    }
    storage.list_conversations_by_web_owner.return_value = [
        {"id": "conv-1", "title": "First", "telegram_chat_id": 12345, "created_at": "2026-03-04"},
    ]
    r = c.get("/api/conversations")
    assert r.status_code == 200
    data = r.json()
    assert data["session_telegram_chat_id"] == 12345
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["id"] == "conv-1"


def test_create_sets_cookie_and_owner(client):
    c, storage = client
    c.cookies.set("csrf_token", "test-csrf")
    storage.create_conversation.return_value = {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "title": "Test",
        "telegram_chat_id": None,
    }
    r = c.post(
        "/api/conversations",
        json={"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Test"},
        headers={"X-CSRF-Token": "test-csrf"},
    )
    assert r.status_code == 200
    assert "vulcan_session" in r.cookies
    args = storage.create_conversation.await_args.kwargs
    assert args["web_owner_session_id"]


def test_create_auto_links_telegram_from_session(client):
    c, storage = client
    conv_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    storage.get_web_session.return_value = {
        "session_id": "s1", "ua_hash": "h", "ip_prefix": "127.0",
        "created_at": 0, "last_seen_at": 0, "expires_at": 999999999999,
        "rotated_to": None, "revoked_at": None, "telegram_chat_id": 44444,
    }
    storage.create_conversation.return_value = {
        "id": conv_id, "title": "Test", "telegram_chat_id": 44444,
    }
    c.cookies.set("csrf_token", "test-csrf")
    r = c.post(
        "/api/conversations",
        json={"id": conv_id, "title": "Test"},
        headers={"X-CSRF-Token": "test-csrf"},
    )
    assert r.status_code == 200
    kwargs = storage.create_conversation.await_args.kwargs
    assert kwargs["telegram_chat_id"] == 44444


def test_get_forbidden_for_other_session(client):
    c, storage = client
    c.cookies.set("vulcan_session", "session-a")
    storage.get_conversation.return_value = {
        "id": "conv-1",
        "web_owner_session_id": "session-b",
        "telegram_chat_id": None,
        "title": "First",
        "created_at": "2026-03-03",
    }
    r = c.get("/api/conversations/conv-1")
    assert r.status_code == 403


def test_get_claims_owner_when_unset(client):
    """Auto-claim requires matching Telegram chat ID between session and conversation."""
    c, storage = client
    c.cookies.set("vulcan_session", "session-a")
    # Session must have a telegram_chat_id that matches the conversation's
    storage.get_web_session.return_value = {
        **_DEFAULT_SESSION,
        "session_id": "session-a",
        "telegram_chat_id": 12345,
    }
    storage.get_conversation.side_effect = [
        {
            "id": "conv-1",
            "web_owner_session_id": None,
            "telegram_chat_id": 12345,
            "title": "Legacy",
            "created_at": "2026-03-03",
        },
        {
            "id": "conv-1",
            "web_owner_session_id": "session-a",
            "telegram_chat_id": 12345,
            "title": "Legacy",
            "created_at": "2026-03-03",
        },
    ]
    storage.claim_conversation_owner_if_unset.return_value = True
    r = c.get("/api/conversations/conv-1")
    assert r.status_code == 200
    storage.claim_conversation_owner_if_unset.assert_awaited_once()
    args = storage.claim_conversation_owner_if_unset.await_args.args
    assert args[0] == "conv-1"


def test_unlink_calls_session_level_unlink(client):
    import hashlib
    import time as _time
    now = int(_time.time())
    ua_hash = hashlib.sha256("testclient".encode()).hexdigest()
    c, storage = client
    c.cookies.set("vulcan_session", "my-sess")
    storage.get_web_session.return_value = {
        "session_id": "my-sess", "ua_hash": ua_hash, "ip_prefix": "testclient",
        "created_at": now, "last_seen_at": now, "expires_at": now + 86400 * 30,
        "rotated_to": None, "revoked_at": None, "telegram_chat_id": 55555,
    }
    storage.get_conversation.return_value = {
        "id": "conv-1", "web_owner_session_id": "my-sess",
        "telegram_chat_id": 55555, "title": "T", "created_at": "2026-03-04",
    }
    c.cookies.set("csrf_token", "test-csrf")
    r = c.post(
        "/api/conversations/conv-1/unlink-telegram",
        headers={"X-CSRF-Token": "test-csrf"},
    )
    assert r.status_code == 200
    storage.unlink_telegram_session.assert_awaited_once_with("my-sess")


def test_create_conversation_requires_csrf_token(client):
    c, storage = client
    storage.create_conversation.return_value = {
        "id": "conv-1", "title": "Test", "telegram_chat_id": None,
    }
    # POST without CSRF token → 403
    r = c.post("/api/conversations", json={"title": "Test"})
    assert r.status_code == 403


def test_delete_conversation_requires_csrf_token(client):
    c, storage = client
    r = c.request("DELETE", "/api/conversations/conv-1")
    assert r.status_code == 403
