import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.web.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_notify_sends_message(client):
    with patch("app.web.routes.notify.get_bot") as mock_get_bot, \
         patch("app.core.auth.settings") as mock_settings:
        mock_settings.api_secret_key = ""  # dev mode: no auth
        mock_settings.frontend_url = "http://localhost:3000"
        mock_bot = AsyncMock()
        mock_get_bot.return_value = mock_bot

        response = client.post("/api/notify", json={
            "chat_id": 123,
            "message": "Test notification",
        }, headers={"X-API-Key": "any"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"


def test_notify_rejects_empty_message(client):
    with patch("app.core.auth.settings") as mock_settings:
        mock_settings.api_secret_key = ""
        mock_settings.frontend_url = "http://localhost:3000"
        response = client.post("/api/notify", json={
            "chat_id": 123,
            "message": "",
        }, headers={"X-API-Key": "any"})
    assert response.status_code == 422


def test_notify_rejects_missing_api_key(client):
    with patch("app.core.auth.settings") as mock_settings:
        mock_settings.api_secret_key = "real-secret"
        response = client.post("/api/notify", json={
            "chat_id": 123,
            "message": "Test",
        })
        assert response.status_code == 403  # missing header → None ≠ secret


def test_notify_rejects_wrong_api_key(client):
    with patch("app.core.auth.settings") as mock_settings:
        mock_settings.api_secret_key = "real-secret"
        response = client.post("/api/notify", json={
            "chat_id": 123,
            "message": "Test",
        }, headers={"X-API-Key": "wrong"})
        assert response.status_code == 403


def test_broadcast_sends_to_subscribers(client):
    with (
        patch("app.web.routes.notify.get_bot") as mock_get_bot,
        patch("app.web.routes.notify.get_storage") as mock_get_storage,
        patch("app.core.auth.settings") as mock_settings,
    ):
        mock_settings.api_secret_key = ""  # dev mode: no auth
        mock_settings.frontend_url = "http://localhost:3000"
        mock_bot = AsyncMock()
        mock_get_bot.return_value = mock_bot

        mock_storage = AsyncMock()
        mock_storage.get_subscriber_chat_ids.return_value = [123, 456]
        mock_get_storage.return_value = mock_storage

        response = client.post("/api/notify/broadcast", json={
            "message": "Broadcast test",
            "target": "subscribers",
        }, headers={"X-API-Key": "any"})

        assert response.status_code == 200
        data = response.json()
        assert data["sent_count"] == 2
