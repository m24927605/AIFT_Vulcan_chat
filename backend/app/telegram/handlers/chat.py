import logging
import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from app.core.services.chat_service import ChatService
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
    def __init__(self, chat_service: ChatService, rate_limiter: RateLimiter):
        self._chat_service = chat_service
        self._rate_limiter = rate_limiter

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        message_text = update.message.text

        if not self._rate_limiter.is_allowed(chat_id):
            await update.message.reply_text("⏳ 訊息太快了，請稍後再試。")
            return

        status_msg = await update.message.reply_text("🤔 思考中...")

        full_text = ""
        citations_event = None
        needs_search = None
        last_edit_time = 0.0
        last_edit_len = 0

        try:
            async for event in self._chat_service.process_message(message=message_text):
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

        except Exception as e:
            logger.error(f"Chat handler error: {e}")
            await status_msg.edit_text(f"❌ 發生錯誤: {str(e)}")
