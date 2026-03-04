import asyncio
import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sse_starlette.sse import EventSourceResponse
from telegram import Bot

from app.core.config import settings
from app.core.models.schemas import ChatRequest
from app.core.services.chat_service import ChatService
from app.core.services.llm_factory import create_llm_client
from app.core.web_session import ensure_web_session, verify_csrf
from app.web.deps import get_storage, get_authorized_conversation
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    SearchFailedEvent,
    DoneEvent,
)
from app.telegram.formatter import TelegramFormatter

logger = logging.getLogger(__name__)

router = APIRouter()


def get_chat_service() -> ChatService:
    return ChatService(
        llm=create_llm_client(settings),
        tavily_api_key=settings.tavily_api_key,
        fugle_api_key=settings.fugle_api_key,
        finnhub_api_key=settings.finnhub_api_key,
    )


def _event_to_sse(event) -> dict:
    match event:
        case PlannerEvent():
            return {"event": "planner", "data": asdict(event)}
        case SearchingEvent():
            return {"event": "searching", "data": asdict(event)}
        case ChunkEvent():
            return {"event": "chunk", "data": {"content": event.content}}
        case CitationsEvent():
            return {"event": "citations", "data": {"citations": event.citations}}
        case SearchFailedEvent():
            return {"event": "search_failed", "data": {"message": event.message}}
        case DoneEvent():
            return {"event": "done", "data": {}}


_TELEGRAM_MAX_RETRIES = 3
_TELEGRAM_BACKOFF_BASE = 1.0  # seconds


async def _push_to_telegram(
    chat_id: int,
    user_msg: str,
    ai_response: str,
    citations: list | None = None,
    search_used: bool | None = None,
) -> None:
    if not settings.telegram_bot_token:
        return

    bot = Bot(token=settings.telegram_bot_token)
    citations_event = CitationsEvent(citations=citations) if citations else None
    body = TelegramFormatter.format_final_message(
        ai_response, citations_event, search_used
    )
    text = f"[Web]\n\nQ: {user_msg}\n\nA: {body}"
    if len(text) > 4096:
        text = text[:4093] + "..."

    for attempt in range(1, _TELEGRAM_MAX_RETRIES + 1):
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            logger.info("Telegram push OK (chat=%d, attempt=%d)", chat_id, attempt)
            return
        except Exception as e:
            if attempt < _TELEGRAM_MAX_RETRIES:
                delay = _TELEGRAM_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "Telegram push attempt %d/%d failed (chat=%d): %s – retrying in %.1fs",
                    attempt, _TELEGRAM_MAX_RETRIES, chat_id, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Telegram push failed after %d attempts (chat=%d): %s",
                    _TELEGRAM_MAX_RETRIES, chat_id, e,
                )


@router.post("/api/chat")
async def chat(
    request: ChatRequest,
    raw_request: Request,
    response: Response,
    _csrf: None = Depends(verify_csrf),
):
    service = get_chat_service()
    storage = get_storage(raw_request)
    session_id = await ensure_web_session(raw_request, response, storage)
    conversation_id = request.conversation_id

    conv = None
    if conversation_id:
        conv = await get_authorized_conversation(storage, conversation_id, session_id)

    # If conversation_id provided, load history from DB
    if conversation_id:
        db_messages = await storage.get_messages(conversation_id)
        history = [{"role": m["role"], "content": m["content"]} for m in db_messages]
        await storage.add_message(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            source="web",
        )
    else:
        history = [msg.model_dump() for msg in request.history]

    async def event_generator():
        full_content = ""
        final_citations = None
        search_used = None

        try:
            async for event in service.process_message(
                message=request.message,
                history=history,
            ):
                match event:
                    case PlannerEvent():
                        search_used = event.needs_search
                    case CitationsEvent():
                        final_citations = event.citations

                sse = _event_to_sse(event)
                yield {
                    "event": sse["event"],
                    "data": json.dumps(sse["data"], ensure_ascii=False),
                }

                if isinstance(event, ChunkEvent):
                    full_content += event.content

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }
            return

        # After stream completes, save assistant message if persisted
        if conversation_id and full_content:
            await storage.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_content,
                source="web",
                search_used=search_used,
                citations=final_citations,
            )

            # Push to Telegram if linked
            if conv and conv.get("telegram_chat_id"):
                asyncio.create_task(
                    _push_to_telegram(
                        conv["telegram_chat_id"],
                        request.message,
                        full_content,
                        citations=final_citations,
                        search_used=search_used,
                    )
                )

    return EventSourceResponse(event_generator())
