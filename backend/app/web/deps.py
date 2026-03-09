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
        # Only auto-claim if the session's linked Telegram chat matches
        # the conversation's telegram_chat_id (i.e. the user owns it via
        # Telegram linking).  Prevents strangers from claiming orphan
        # conversations by guessing UUIDs.
        session = await storage.get_web_session(session_id)
        session_tg = session.get("telegram_chat_id") if session else None
        conv_tg = conv.get("telegram_chat_id")
        if session_tg and conv_tg and session_tg == conv_tg:
            claimed = await storage.claim_conversation_owner_if_unset(
                conversation_id, session_id
            )
            if claimed:
                conv["web_owner_session_id"] = session_id
    if conv.get("web_owner_session_id") != session_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return conv
