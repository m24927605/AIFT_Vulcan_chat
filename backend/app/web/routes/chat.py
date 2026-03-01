import json
import logging
from dataclasses import asdict

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.models.schemas import ChatRequest
from app.core.services.chat_service import ChatService
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_chat_service() -> ChatService:
    return ChatService(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        tavily_api_key=settings.tavily_api_key,
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
        case DoneEvent():
            return {"event": "done", "data": {}}


@router.post("/api/chat")
async def chat(request: ChatRequest):
    service = get_chat_service()
    history = [msg.model_dump() for msg in request.history]

    async def event_generator():
        try:
            async for event in service.process_message(
                message=request.message,
                history=history,
            ):
                sse = _event_to_sse(event)
                yield {
                    "event": sse["event"],
                    "data": json.dumps(sse["data"], ensure_ascii=False),
                }
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }

    return EventSourceResponse(event_generator())
