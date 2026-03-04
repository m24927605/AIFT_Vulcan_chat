"""
Simple API key authentication for admin endpoints.

Protected endpoints require an X-API-Key header matching the configured
API_SECRET_KEY. If no key is configured, the endpoints are unprotected
(development mode).
"""

import hmac

from fastapi import Header, HTTPException

from app.core.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI dependency: reject requests without a valid API key."""
    if not settings.api_secret_key:
        if settings.frontend_url == "http://localhost:3000":
            return
        raise HTTPException(status_code=503, detail="Server auth misconfigured")
    if not hmac.compare_digest(x_api_key or "", settings.api_secret_key):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
