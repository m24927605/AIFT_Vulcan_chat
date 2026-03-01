import json
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.models.schemas import ChatRequest
from app.core.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_chat_service() -> ChatService:
    return ChatService(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        tavily_api_key=settings.tavily_api_key,
    )


@router.post("/api/chat")
async def chat(request: ChatRequest):
    service = get_chat_service()
    history = [msg.model_dump() for msg in request.history]

    async def event_generator():
        try:
            async for event_type, data in service.chat_stream(
                message=request.message,
                history=history,
            ):
                yield {
                    "event": event_type,
                    "data": json.dumps(data, ensure_ascii=False),
                }
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }

    return EventSourceResponse(event_generator())
