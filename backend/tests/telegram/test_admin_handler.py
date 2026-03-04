import pytest
from unittest.mock import AsyncMock, MagicMock

from app.telegram.handlers.admin import AdminHandler


@pytest.fixture
def mock_storage():
    return AsyncMock()


@pytest.fixture
def handler(mock_storage):
    return AdminHandler(storage=mock_storage, admin_ids=[111, 222])


def _make_update(chat_id):
    update = AsyncMock()
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_stats_shows_info_for_admin(handler, mock_storage):
    mock_storage.list_all.return_value = [
        {"chat_id": 1, "topic": "A", "frequency": "daily", "time": "09:00", "timezone": "Asia/Taipei"},
        {"chat_id": 2, "topic": "B", "frequency": "weekly", "time": "10:00", "timezone": "Asia/Taipei"},
    ]

    update = _make_update(chat_id=111)
    context = MagicMock()

    await handler.stats(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "2" in call_text


@pytest.mark.asyncio
async def test_stats_denied_for_non_admin(handler):
    update = _make_update(chat_id=999)
    context = MagicMock()

    await handler.stats(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "權限" in call_text or "denied" in call_text.lower()
