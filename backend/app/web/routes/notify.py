import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from telegram import Bot

from app.core.auth import require_api_key
from app.core.config import settings
from app.telegram.storage import SubscriptionStorage

logger = logging.getLogger(__name__)

router = APIRouter()


class NotifyRequest(BaseModel):
    chat_id: int
    message: str = Field(..., min_length=1)
    parse_mode: str | None = None


class BroadcastRequest(BaseModel):
    message: str = Field(..., min_length=1)
    target: str = Field(..., pattern="^subscribers$")


def get_bot() -> Bot:
    return Bot(token=settings.telegram_bot_token)


@router.post("/api/notify", dependencies=[Depends(require_api_key)])
async def notify(request: NotifyRequest):
    bot = get_bot()
    await bot.send_message(
        chat_id=request.chat_id,
        text=request.message,
        parse_mode=request.parse_mode,
    )
    return {"status": "sent"}


@router.post("/api/notify/broadcast", dependencies=[Depends(require_api_key)])
async def broadcast(request: BroadcastRequest):
    bot = get_bot()
    storage = SubscriptionStorage()
    await storage.initialize()
    try:
        chat_ids = await storage.get_subscriber_chat_ids()

        sent_count = 0
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=request.message)
                sent_count += 1
            except Exception as e:
                logger.error("Broadcast failed for %s (%s)", chat_id, type(e).__name__)

        return {"sent_count": sent_count}
    finally:
        await storage.close()
