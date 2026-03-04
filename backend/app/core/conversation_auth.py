"""
HMAC-based conversation token authentication.

Each conversation gets a token = HMAC-SHA256(conversation_id, API_SECRET_KEY).
Stateless verification — no DB changes needed.

When API_SECRET_KEY is empty (dev mode), verification is skipped.
"""

import hashlib
import hmac

from fastapi import Header, HTTPException

from app.core.config import settings


def generate_conversation_token(conversation_id: str) -> str:
    """Generate an HMAC token for a conversation ID."""
    if not settings.api_secret_key:
        return ""
    return hmac.new(
        settings.api_secret_key.encode(),
        conversation_id.encode(),
        hashlib.sha256,
    ).hexdigest()


async def require_conversation_token(
    conversation_id: str,
    x_conversation_token: str | None = Header(default=None, alias="X-Conversation-Token"),
) -> None:
    """FastAPI dependency: verify the conversation token matches."""
    if not settings.api_secret_key:
        if settings.frontend_url == "http://localhost:3000":
            return
        raise HTTPException(status_code=503, detail="Server auth misconfigured")
    expected = generate_conversation_token(conversation_id)
    if not hmac.compare_digest(x_conversation_token or "", expected):
        raise HTTPException(status_code=403, detail="Invalid or missing conversation token")
