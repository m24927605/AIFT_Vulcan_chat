import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.web.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_notify_sends_message(client):
    with patch("app.web.routes.notify.get_bot") as mock_get_bot:
        mock_bot = AsyncMock()
        mock_get_bot.return_value = mock_bot

        response = client.post("/api/notify", json={
            "chat_id": 123,
            "message": "Test notification",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"


def test_notify_rejects_empty_message(client):
    response = client.post("/api/notify", json={
        "chat_id": 123,
        "message": "",
    })
    assert response.status_code == 422


def test_broadcast_sends_to_subscribers(client):
    with (
        patch("app.web.routes.notify.get_bot") as mock_get_bot,
        patch("app.web.routes.notify.get_storage") as mock_get_storage,
    ):
        mock_bot = AsyncMock()
        mock_get_bot.return_value = mock_bot

        mock_storage = AsyncMock()
        mock_storage.get_subscriber_chat_ids.return_value = [123, 456]
        mock_get_storage.return_value = mock_storage

        response = client.post("/api/notify/broadcast", json={
            "message": "Broadcast test",
            "target": "subscribers",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["sent_count"] == 2
