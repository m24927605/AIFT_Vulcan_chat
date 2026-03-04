from fastapi import HTTPException, Request

from app.core.storage import ConversationStorage


def get_storage(request: Request) -> ConversationStorage:
    return request.app.state.conversation_storage


async def get_authorized_conversation(
    storage: ConversationStorage,
    conversation_id: str,
    session_id: str,
) -> dict:
    conv = await storage.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    owner = conv.get("web_owner_session_id")
    if owner is None:
        claimed = await storage.claim_conversation_owner_if_unset(
            conversation_id, session_id
        )
        if claimed:
            conv["web_owner_session_id"] = session_id
    if conv.get("web_owner_session_id") != session_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return conv
