"""Tests for multi-conversation Telegram sync.

Verifies that when multiple conversations are linked to the same Telegram
chat ID, incoming messages (user + assistant) are persisted to ALL linked
conversations.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.models.events import ChunkEvent, DoneEvent, PlannerEvent
from app.core.storage import ConversationStorage
from app.telegram.handlers.chat import ChatHandler
from app.telegram.rate_limiter import RateLimiter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def storage(tmp_path):
    """Real SQLite-backed ConversationStorage using a temporary directory."""
    db_path = str(tmp_path / "test_sync.db")
    s = ConversationStorage(db_path=db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def rate_limiter():
    limiter = MagicMock(spec=RateLimiter)
    limiter.is_allowed.return_value = True
    limiter.remaining.return_value = 19
    return limiter


@pytest.fixture
def chat_service():
    return AsyncMock()


def _make_update(text: str = "Hello", chat_id: int = 100) -> AsyncMock:
    """Build a minimal Telegram Update mock."""
    update = AsyncMock()
    update.message.text = text
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    # The status message returned by reply_text also needs edit_text
    status_msg = AsyncMock()
    update.message.reply_text.return_value = status_msg
    return update


# ---------------------------------------------------------------------------
# Test 1 - Messages sync to all linked conversations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telegram_message_syncs_to_all_linked_conversations(
    storage, chat_service, rate_limiter
):
    """When 3 conversations are linked to the same Telegram chat_id, a single
    incoming message should be written (user + assistant) to ALL 3."""

    chat_id = 100

    # Create 3 conversations and link them to the same chat_id
    await storage.create_conversation(id="conv-1", title="Conv 1")
    await storage.create_conversation(id="conv-2", title="Conv 2")
    await storage.create_conversation(id="conv-3", title="Conv 3")

    await storage.link_telegram("conv-1", chat_id)
    await storage.link_telegram("conv-2", chat_id)
    await storage.link_telegram("conv-3", chat_id)

    # Verify lookup returns all 3
    linked = await storage.get_conversations_by_telegram_chat_id(chat_id)
    assert len(linked) == 3
    linked_ids = {c["id"] for c in linked}
    assert linked_ids == {"conv-1", "conv-2", "conv-3"}

    # Set up chat_service to yield a simple response
    assistant_text = "This is the AI answer."

    async def mock_process(message, history=None):
        yield PlannerEvent(
            needs_search=False,
            reasoning="direct",
            search_queries=[],
            query_type="conversational",
        )
        yield ChunkEvent(content=assistant_text)
        yield DoneEvent()

    chat_service.process_message = mock_process

    handler = ChatHandler(
        chat_service=chat_service,
        rate_limiter=rate_limiter,
        storage=storage,
    )

    update = _make_update(text="User question", chat_id=chat_id)
    context = MagicMock()

    await handler.handle(update, context)

    # Verify that every linked conversation received both user + assistant msgs
    for conv_id in ["conv-1", "conv-2", "conv-3"]:
        messages = await storage.get_messages(conv_id)
        assert len(messages) == 2, (
            f"Expected 2 messages in {conv_id}, got {len(messages)}"
        )
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "User question"
        assert messages[0]["source"] == "telegram"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == assistant_text
        assert messages[1]["source"] == "telegram"


# ---------------------------------------------------------------------------
# Test 2 - Linking a second conversation does not unlink the first
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_link_telegram_does_not_unlink_others(storage):
    """Linking conv-2 to chat_id 100 must NOT remove the link on conv-1."""

    chat_id = 100

    await storage.create_conversation(id="conv-1", title="First")
    await storage.link_telegram("conv-1", chat_id)

    await storage.create_conversation(id="conv-2", title="Second")
    await storage.link_telegram("conv-2", chat_id)

    # conv-1 must still be linked
    conv1 = await storage.get_conversation("conv-1")
    assert conv1 is not None
    assert conv1["telegram_chat_id"] == chat_id

    # conv-2 must also be linked
    conv2 = await storage.get_conversation("conv-2")
    assert conv2 is not None
    assert conv2["telegram_chat_id"] == chat_id

    # Both appear in the lookup list
    linked = await storage.get_conversations_by_telegram_chat_id(chat_id)
    assert len(linked) == 2
    assert {c["id"] for c in linked} == {"conv-1", "conv-2"}


# ---------------------------------------------------------------------------
# Test 3 - Primary conversation is the oldest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_primary_conversation_is_oldest(storage, chat_service, rate_limiter):
    """_get_or_create_primary must return the oldest (earliest created)
    conversation linked to the given chat_id."""

    chat_id = 200

    # Insert conversations in order; SQLite CURRENT_TIMESTAMP has 1-second
    # resolution, so we add a tiny manual delay to guarantee ordering.
    await storage.create_conversation(id="oldest", title="Oldest")
    await storage.link_telegram("oldest", chat_id)

    # Small sleep to ensure created_at differs
    await asyncio.sleep(0.05)

    await storage.create_conversation(id="middle", title="Middle")
    await storage.link_telegram("middle", chat_id)

    await asyncio.sleep(0.05)

    await storage.create_conversation(id="newest", title="Newest")
    await storage.link_telegram("newest", chat_id)

    handler = ChatHandler(
        chat_service=chat_service,
        rate_limiter=rate_limiter,
        storage=storage,
    )

    primary_id = await handler._get_or_create_primary(chat_id, "test message")
    assert primary_id == "oldest"
