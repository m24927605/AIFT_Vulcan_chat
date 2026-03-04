from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Query, Response

from app.core.models.schemas import CreateConversationRequest
from app.core.web_session import ensure_web_session, verify_csrf
from app.web.deps import get_storage, get_authorized_conversation

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    request: Request,
    response: Response,
    ids: str | None = Query(None, description="Comma-separated conversation IDs to filter"),
):
    storage = get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    session = await storage.get_web_session(session_id)
    session_tg = session.get("telegram_chat_id") if session else None
    all_convs = await storage.list_conversations_by_web_owner(session_id)
    if ids:
        id_set = {i.strip() for i in ids.split(",") if i.strip()}
        matched = [c for c in all_convs if c["id"] in id_set]
    else:
        matched = all_convs
    return {
        "session_telegram_chat_id": session_tg,
        "conversations": [
            {
                "id": c["id"],
                "title": c["title"],
                "telegram_chat_id": c["telegram_chat_id"],
                "created_at": c["created_at"],
            }
            for c in matched
        ],
    }


@router.post("")
async def create_conversation(request: Request, response: Response, body: CreateConversationRequest, _csrf: None = Depends(verify_csrf)):
    storage = get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    session = await storage.get_web_session(session_id)
    session_tg = session.get("telegram_chat_id") if session else None
    conv_id = body.id or str(uuid4())
    conv = await storage.create_conversation(
        id=conv_id,
        title=body.title,
        web_owner_session_id=session_id,
        telegram_chat_id=session_tg,
    )
    return {
        "id": conv["id"],
        "title": conv["title"],
        "telegram_chat_id": conv["telegram_chat_id"],
    }


@router.get("/{conversation_id}")
async def get_conversation(
    request: Request,
    response: Response,
    conversation_id: str,
):
    storage = get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    conv = await get_authorized_conversation(storage, conversation_id, session_id)
    return {
        "id": conv["id"],
        "telegram_chat_id": conv["telegram_chat_id"],
        "title": conv["title"],
        "created_at": conv["created_at"],
    }


@router.delete("/{conversation_id}")
async def delete_conversation(
    request: Request,
    response: Response,
    conversation_id: str,
    _csrf: None = Depends(verify_csrf),
):
    storage = get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    await get_authorized_conversation(storage, conversation_id, session_id)
    deleted = await storage.delete_conversation(conversation_id)
    if not deleted:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@router.get("/{conversation_id}/messages")
async def get_messages(
    request: Request,
    response: Response,
    conversation_id: str,
    after_id: int | None = Query(None),
):
    storage = get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    await get_authorized_conversation(storage, conversation_id, session_id)
    return await storage.get_messages(conversation_id, after_id=after_id)


@router.post("/{conversation_id}/telegram-link/request")
async def request_telegram_link_code(
    request: Request,
    response: Response,
    conversation_id: str,
    _csrf: None = Depends(verify_csrf),
):
    storage = get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    await get_authorized_conversation(storage, conversation_id, session_id)
    code = await storage.create_telegram_link_code(
        conversation_id=conversation_id,
        web_owner_session_id=session_id,
    )
    return {
        "status": "pending",
        "code": code,
        "expires_in_seconds": 600,
    }


@router.post("/{conversation_id}/unlink-telegram")
async def unlink_telegram(
    request: Request,
    response: Response,
    conversation_id: str,
    _csrf: None = Depends(verify_csrf),
):
    storage = get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    await get_authorized_conversation(storage, conversation_id, session_id)
    await storage.unlink_telegram_session(session_id)
    return {"status": "unlinked"}
