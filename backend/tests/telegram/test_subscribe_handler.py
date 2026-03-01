import pytest
from unittest.mock import AsyncMock, MagicMock

from app.telegram.handlers.subscribe import SubscribeHandler


@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    storage.list.return_value = []
    return storage


@pytest.fixture
def handler(mock_storage):
    return SubscribeHandler(storage=mock_storage)


def _make_update(text, chat_id=123):
    update = AsyncMock()
    update.message.text = text
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_subscribe_success(handler, mock_storage):
    update = _make_update("/subscribe 科技新聞 daily 09:00")
    context = MagicMock()
    context.args = ["科技新聞", "daily", "09:00"]

    await handler.subscribe(update, context)

    mock_storage.add.assert_called_once_with(
        chat_id=123, topic="科技新聞", frequency="daily", time="09:00"
    )
    call_text = update.message.reply_text.call_args[0][0]
    assert "科技新聞" in call_text


@pytest.mark.asyncio
async def test_subscribe_missing_args(handler):
    update = _make_update("/subscribe")
    context = MagicMock()
    context.args = []

    await handler.subscribe(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "格式" in call_text or "/subscribe" in call_text


@pytest.mark.asyncio
async def test_subscribe_invalid_frequency(handler):
    update = _make_update("/subscribe 科技 monthly 09:00")
    context = MagicMock()
    context.args = ["科技", "monthly", "09:00"]

    await handler.subscribe(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "daily" in call_text or "weekly" in call_text


@pytest.mark.asyncio
async def test_unsubscribe_success(handler, mock_storage):
    mock_storage.remove.return_value = True
    update = _make_update("/unsubscribe 科技新聞")
    context = MagicMock()
    context.args = ["科技新聞"]

    await handler.unsubscribe(update, context)

    mock_storage.remove.assert_called_once_with(chat_id=123, topic="科技新聞")


@pytest.mark.asyncio
async def test_unsubscribe_not_found(handler, mock_storage):
    mock_storage.remove.return_value = False
    update = _make_update("/unsubscribe 不存在")
    context = MagicMock()
    context.args = ["不存在"]

    await handler.unsubscribe(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "找不到" in call_text


@pytest.mark.asyncio
async def test_list_empty(handler, mock_storage):
    mock_storage.list.return_value = []
    update = _make_update("/list")
    context = MagicMock()

    await handler.list_subscriptions(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "沒有" in call_text


@pytest.mark.asyncio
async def test_list_with_subscriptions(handler, mock_storage):
    mock_storage.list.return_value = [
        {"topic": "科技新聞", "frequency": "daily", "time": "09:00", "timezone": "Asia/Taipei"},
    ]
    update = _make_update("/list")
    context = MagicMock()

    await handler.list_subscriptions(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "科技新聞" in call_text
    assert "daily" in call_text
