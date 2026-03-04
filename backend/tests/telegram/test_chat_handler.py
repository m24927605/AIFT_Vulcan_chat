import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.telegram.handlers.chat import ChatHandler
from app.core.models.events import (
    PlannerEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)


@pytest.fixture
def mock_chat_service():
    return AsyncMock()


@pytest.fixture
def mock_rate_limiter():
    limiter = MagicMock()
    limiter.is_allowed.return_value = True
    limiter.remaining.return_value = 19
    return limiter


@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    storage.get_conversations_by_telegram_chat_id = AsyncMock(
        return_value=[{"id": "conv-1", "title": "Test", "telegram_chat_id": 123, "created_at": "2026-01-01"}]
    )
    storage.add_message = AsyncMock(return_value=1)
    storage.get_messages = AsyncMock(return_value=[])
    return storage


@pytest.fixture
def handler(mock_chat_service, mock_rate_limiter, mock_storage):
    return ChatHandler(
        chat_service=mock_chat_service,
        rate_limiter=mock_rate_limiter,
        storage=mock_storage,
    )


def _make_update(text="Hello", chat_id=123):
    update = AsyncMock()
    update.message.text = text
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_chat_handler_sends_response(handler, mock_chat_service):
    async def mock_process(message, history=None):
        yield PlannerEvent(needs_search=False, reasoning="test", search_queries=[], query_type="conversational")
        yield ChunkEvent(content="Hello!")
        yield DoneEvent()

    mock_chat_service.process_message = mock_process

    update = _make_update("Hi")
    context = MagicMock()

    await handler.handle(update, context)

    update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_chat_handler_rate_limited(handler, mock_rate_limiter):
    mock_rate_limiter.is_allowed.return_value = False

    update = _make_update("Hi")
    context = MagicMock()

    await handler.handle(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "太快" in call_text or "稍後" in call_text or "rate" in call_text.lower() or "limit" in call_text.lower()


@pytest.mark.asyncio
async def test_chat_handler_with_citations(handler, mock_chat_service):
    async def mock_process(message, history=None):
        yield PlannerEvent(needs_search=True, reasoning="searching", search_queries=["q"], query_type="temporal")
        yield ChunkEvent(content="Answer [1]")
        yield CitationsEvent(citations=[{"index": 1, "title": "T", "url": "https://ex.com", "snippet": "s"}])
        yield DoneEvent()

    mock_chat_service.process_message = mock_process

    update = _make_update("Stock?")
    context = MagicMock()

    await handler.handle(update, context)

    status_msg = update.message.reply_text.return_value
    status_msg.edit_text.assert_called()
    # Verify final message includes search indicator
    last_call_text = status_msg.edit_text.call_args[0][0]
    assert "🔍 Searched the web" in last_call_text


@pytest.mark.asyncio
async def test_chat_handler_no_search_indicator(handler, mock_chat_service):
    async def mock_process(message, history=None):
        yield PlannerEvent(needs_search=False, reasoning="general", search_queries=[], query_type="conversational")
        yield ChunkEvent(content="Hi there!")
        yield DoneEvent()

    mock_chat_service.process_message = mock_process

    update = _make_update("Hello")
    context = MagicMock()

    await handler.handle(update, context)

    status_msg = update.message.reply_text.return_value
    last_call_text = status_msg.edit_text.call_args[0][0]
    assert "💬 Answered directly" in last_call_text
