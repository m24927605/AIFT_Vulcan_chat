import os
import tempfile

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
        assert response.status_code == 403  # missing header -> None != secret


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
        patch("app.web.routes.notify.SubscriptionStorage") as MockStorageCls,
        patch("app.core.auth.settings") as mock_settings,
    ):
        mock_settings.api_secret_key = ""
        mock_settings.frontend_url = "http://localhost:3000"
        mock_bot = AsyncMock()
        mock_get_bot.return_value = mock_bot

        mock_storage = AsyncMock()
        mock_storage.get_subscriber_chat_ids.return_value = [123, 456]
        MockStorageCls.return_value = mock_storage

        response = client.post("/api/notify/broadcast", json={
            "message": "Broadcast test",
            "target": "subscribers",
        }, headers={"X-API-Key": "any"})

        assert response.status_code == 200
        data = response.json()
        assert data["sent_count"] == 2
        mock_storage.initialize.assert_called_once()
        mock_storage.close.assert_called_once()


def test_broadcast_rejects_target_all(client):
    """target=all is no longer accepted."""
    with patch("app.core.auth.settings") as mock_settings:
        mock_settings.api_secret_key = ""
        mock_settings.frontend_url = "http://localhost:3000"
        response = client.post("/api/notify/broadcast", json={
            "message": "Test",
            "target": "all",
        }, headers={"X-API-Key": "any"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_broadcast_initializes_and_closes_storage():
    """Broadcast must call initialize() and close() on real storage."""
    from app.telegram.storage import SubscriptionStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_subs.db")
        storage = SubscriptionStorage(db_path=db_path)
        await storage.initialize()
        await storage.add(chat_id=111, topic="test", frequency="daily", time="09:00")
        await storage.close()

        # Verify real storage path works
        storage2 = SubscriptionStorage(db_path=db_path)
        await storage2.initialize()
        chat_ids = await storage2.get_subscriber_chat_ids()
        assert chat_ids == [111]
        await storage2.close()


def test_broadcast_route_with_real_storage(client):
    """Integration test: broadcast route using real SubscriptionStorage, no storage mocks."""
    from app.telegram.storage import SubscriptionStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "broadcast_test.db")

        # Pre-populate the DB with subscribers
        import asyncio

        async def _seed():
            s = SubscriptionStorage(db_path=db_path)
            await s.initialize()
            await s.add(chat_id=111, topic="news", frequency="daily", time="09:00")
            await s.add(chat_id=222, topic="stocks", frequency="daily", time="09:00")
            await s.close()

        asyncio.get_event_loop().run_until_complete(_seed())

        # Patch only: bot (don't send real Telegram messages), auth, and DB path
        mock_bot = AsyncMock()
        with (
            patch("app.web.routes.notify.get_bot", return_value=mock_bot),
            patch("app.core.auth.settings") as mock_settings,
            patch(
                "app.web.routes.notify.SubscriptionStorage",
                lambda: SubscriptionStorage(db_path=db_path),
            ),
        ):
            mock_settings.api_secret_key = ""
            mock_settings.frontend_url = "http://localhost:3000"

            response = client.post("/api/notify/broadcast", json={
                "message": "Real storage broadcast",
                "target": "subscribers",
            }, headers={"X-API-Key": "any"})

        assert response.status_code == 200
        data = response.json()
        assert data["sent_count"] == 2
        # Verify bot was called with both subscriber chat_ids
        sent_ids = sorted(
            call.kwargs["chat_id"]
            for call in mock_bot.send_message.call_args_list
        )
        assert sent_ids == [111, 222]
