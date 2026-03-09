import hashlib
import hmac
import secrets
import time
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response

from app.core.storage import ConversationStorage
from app.core.config import settings

SESSION_COOKIE_NAME = "vulcan_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
SESSION_ROTATE_SECONDS = 60 * 60 * 24
CSRF_COOKIE_NAME = "csrf_token"


def _ua_hash(request: Request) -> str:
    ua = request.headers.get("user-agent", "")
    return hashlib.sha256(ua.encode()).hexdigest()


def _ip_prefix(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return ".".join(parts[:3])
    return host


def _is_secure(request: Request) -> bool:
    # Trust X-Forwarded-Proto set by Railway's reverse proxy.
    # Railway terminates TLS and overwrites this header before forwarding.
    proto = request.headers.get("x-forwarded-proto", "").lower().strip()
    if proto:
        return proto == "https"
    return request.url.scheme == "https"


def _cookie_samesite(request: Request) -> str:
    origin = request.headers.get("origin")
    if not origin:
        return "lax"
    origin_host = urlparse(origin).hostname
    request_host = request.url.hostname
    if origin_host and request_host and origin_host != request_host:
        return "none"
    return "lax"


def _normalized_origin(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    default_port = 443 if scheme == "https" else 80
    if port and port != default_port:
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def _set_csrf_cookie(
    request: Request, response: Response, *, force: bool = False,
) -> None:
    existing = request.cookies.get(CSRF_COOKIE_NAME)
    if existing and not force:
        return
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=existing or secrets.token_urlsafe(32),
        httponly=False,
        secure=_is_secure(request),
        samesite=_cookie_samesite(request),
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )


def _set_cookie(request: Request, response: Response, session_id: str) -> None:
    samesite = _cookie_samesite(request)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=_is_secure(request),
        samesite=samesite,
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    _set_csrf_cookie(request, response, force=True)


async def verify_csrf(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and _normalized_origin(origin) != _normalized_origin(settings.frontend_url):
        raise HTTPException(status_code=403, detail="Origin not allowed")

    header_token = request.headers.get("x-csrf-token", "")
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    if not header_token or not cookie_token:
        raise HTTPException(status_code=403, detail="CSRF token missing")
    if not hmac.compare_digest(header_token, cookie_token):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


async def ensure_web_session(
    request: Request,
    response: Response,
    storage: ConversationStorage,
) -> str:
    now = int(time.time())
    ua_hash = _ua_hash(request)
    ip_prefix = _ip_prefix(request)
    existing = request.cookies.get(SESSION_COOKIE_NAME)

    if existing:
        record = await storage.get_web_session(existing)
        if (
            record
            and record["revoked_at"] is None
            and record["expires_at"] >= now
            and record["ua_hash"] == ua_hash
            and record["ip_prefix"] == ip_prefix
        ):
            session_age = now - record["created_at"]
            if session_age >= SESSION_ROTATE_SECONDS:
                new_session = secrets.token_urlsafe(32)
                await storage.rotate_web_session(
                    old_session_id=existing,
                    new_session_id=new_session,
                    ua_hash=ua_hash,
                    ip_prefix=ip_prefix,
                    expires_at=now + SESSION_TTL_SECONDS,
                )
                _set_cookie(request, response, new_session)
                return new_session
            await storage.touch_web_session(existing)
            _set_csrf_cookie(request, response)
            return existing

    session_id = secrets.token_urlsafe(32)
    await storage.create_web_session(
        session_id=session_id,
        ua_hash=ua_hash,
        ip_prefix=ip_prefix,
        expires_at=now + SESSION_TTL_SECONDS,
    )
    _set_cookie(request, response, session_id)
    return session_id
