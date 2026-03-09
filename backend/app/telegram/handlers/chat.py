import logging
import asyncio
from uuid import uuid4

from telegram import Update
from telegram.ext import ContextTypes

from app.core.services.chat_service import ChatService
from app.core.storage import ConversationStorage
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)
from app.telegram.formatter import TelegramFormatter
from app.telegram.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_EDIT_INTERVAL = 2.0
_EDIT_CHAR_THRESHOLD = 30


class ChatHandler:
    def __init__(
        self,
        chat_service: ChatService,
        rate_limiter: RateLimiter,
        storage: ConversationStorage,
    ):
        self._chat_service = chat_service
        self._rate_limiter = rate_limiter
        self._storage = storage

    async def _get_or_create_primary(self, chat_id: int, message_text: str) -> str:
        """Get the primary (oldest) conversation for this Telegram chat, or create one."""
        convs = await self._storage.get_conversations_by_telegram_chat_id(chat_id)
        if convs:
            return convs[0]["id"]
        conv_id = str(uuid4())
        title = message_text[:30] + "..." if len(message_text) > 30 else message_text
        await self._storage.create_conversation(
            id=conv_id,
            title=title,
            telegram_chat_id=chat_id,
        )
        return conv_id

    async def _get_linked_ids(self, chat_id: int) -> list[str]:
        """Get all conversation IDs linked to this Telegram chat."""
        convs = await self._storage.get_conversations_by_telegram_chat_id(chat_id)
        return [c["id"] for c in convs]

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        message_text = update.message.text

        if not self._rate_limiter.is_allowed(chat_id):
            await update.message.reply_text("⏳ 訊息太快了，請稍後再試。")
            return

        status_msg = await update.message.reply_text("🤔 思考中...")

        # Get primary conversation for AI history, and all linked conversations for sync
        primary_id = await self._get_or_create_primary(chat_id, message_text)
        linked_ids = await self._get_linked_ids(chat_id)

        # Persist user message to all linked conversations
        for conv_id in linked_ids:
            await self._storage.add_message(
                conversation_id=conv_id,
                role="user",
                content=message_text,
                source="telegram",
            )

        # Load history from primary conversation for AI context
        db_messages = await self._storage.get_messages(primary_id)
        # Exclude the message we just added (last one) to form history for the AI
        history = [{"role": m["role"], "content": m["content"]} for m in db_messages[:-1]]

        full_text = ""
        citations_event = None
        needs_search = None
        last_edit_time = 0.0
        last_edit_len = 0

        try:
            async for event in self._chat_service.process_message(
                message=message_text,
                history=history,
            ):
                match event:
                    case PlannerEvent():
                        needs_search = event.needs_search
                        status_text = TelegramFormatter.format_planner(event)
                        await status_msg.edit_text(status_text)

                    case SearchingEvent():
                        status_text = TelegramFormatter.format_searching(event)
                        await status_msg.edit_text(status_text)

                    case ChunkEvent():
                        full_text += event.content
                        now = asyncio.get_event_loop().time()
                        chars_since_edit = len(full_text) - last_edit_len
                        time_since_edit = now - last_edit_time

                        if chars_since_edit >= _EDIT_CHAR_THRESHOLD or time_since_edit >= _EDIT_INTERVAL:
                            try:
                                await status_msg.edit_text(full_text)
                                last_edit_time = now
                                last_edit_len = len(full_text)
                            except Exception:
                                pass

                    case CitationsEvent():
                        citations_event = event

                    case DoneEvent():
                        pass

            final_text = TelegramFormatter.format_final_message(full_text, citations_event, needs_search)
            try:
                await status_msg.edit_text(final_text)
            except Exception:
                pass

            # Persist assistant message to all linked conversations
            if full_text:
                citations_data = citations_event.citations if citations_event else None
                for conv_id in linked_ids:
                    await self._storage.add_message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=full_text,
                        source="telegram",
                        search_used=needs_search,
                        citations=citations_data,
                    )

        except Exception as e:
            logger.error("Chat handler error (%s)", type(e).__name__)
            await status_msg.edit_text("❌ 發生錯誤，請稍後再試。")
