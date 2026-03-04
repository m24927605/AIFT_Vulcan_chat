import pytest
from unittest.mock import AsyncMock, MagicMock

from app.telegram.scheduler import DigestScheduler


@pytest.fixture
def mock_chat_service():
    return AsyncMock()


@pytest.fixture
def mock_storage():
    return AsyncMock()


@pytest.fixture
def mock_bot():
    return AsyncMock()


@pytest.fixture
def scheduler(mock_chat_service, mock_storage, mock_bot):
    return DigestScheduler(
        chat_service=mock_chat_service,
        storage=mock_storage,
        bot=mock_bot,
    )


@pytest.mark.asyncio
async def test_execute_digest_sends_message(scheduler, mock_chat_service, mock_bot):
    from app.core.models.events import ChunkEvent, DoneEvent, PlannerEvent

    async def mock_process(message, history=None):
        yield PlannerEvent(needs_search=True, reasoning="r", search_queries=["q"], query_type="temporal")
        yield ChunkEvent(content="Today's news summary")
        yield DoneEvent()

    mock_chat_service.process_message = mock_process

    await scheduler.execute_digest(chat_id=123, topic="科技新聞")

    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args[1]
    assert call_kwargs["chat_id"] == 123
    assert "news summary" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_execute_digest_handles_error(scheduler, mock_chat_service, mock_bot):
    mock_chat_service.process_message = MagicMock(side_effect=Exception("API Error"))

    await scheduler.execute_digest(chat_id=123, topic="科技新聞")

    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args[1]
    assert "錯誤" in call_kwargs["text"] or "error" in call_kwargs["text"].lower()
