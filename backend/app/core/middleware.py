"""
Request middleware: logging, request ID tracing, rate limiting.
"""

import logging
import re
import sys
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# ── Request ID context ──────────────────────────────────────────────

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_SECRET_LOG_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\b\d{8,10}:[A-Za-z0-9_-]{20,}\b",  # Telegram bot token
        r"sk-[A-Za-z0-9_-]{20,}",
        r"sess-[A-Za-z0-9_-]{16,}",
        r"authorization\s*:\s*bearer\s+\S+",
        r"api[_ -]?key\s*[:=]\s*\S+",
    ]
]
_LOG_REDACTION = "[REDACTED]"


class RequestIDFilter(logging.Filter):
    """Inject request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


class SecretRedactionFilter(logging.Filter):
    """Redact common secret patterns from log messages and args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact_arg(v) for k, v in record.args.items()}
            else:
                record.args = tuple(_redact_arg(arg) for arg in record.args)
        return True


def _redact_secrets(value: str) -> str:
    redacted = value
    for pattern in _SECRET_LOG_PATTERNS:
        redacted = pattern.sub(_LOG_REDACTION, redacted)
    return redacted


def _redact_arg(value):
    if isinstance(value, str):
        return _redact_secrets(value)
    return value


def setup_logging() -> None:
    """Configure structured logging with request ID."""
    fmt = "%(asctime)s %(levelname)-5s [%(request_id)s] %(name)s – %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    handler.addFilter(RequestIDFilter())
    handler.addFilter(SecretRedactionFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Redirect uvicorn loggers to stdout (default stderr → Railway marks as error)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.addHandler(handler)

    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


# ── Request ID + Logging middleware ─────────────────────────────────

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assign a request ID, log request/response timing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request_id_var.set(rid)

        start = time.monotonic()
        method = request.method
        path = request.url.path

        logger.info("%s %s", method, path)
        response = await call_next(request)
        elapsed_ms = (time.monotonic() - start) * 1000

        logger.info(
            "%s %s → %d (%.0fms)", method, path, response.status_code, elapsed_ms
        )
        response.headers["X-Request-ID"] = rid
        return response


# ── Rate limiting middleware ────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window IP-based rate limiter for /api/chat."""

    def __init__(self, app, max_requests: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        # Use direct connection IP only — X-Forwarded-For is user-controlled
        # and can be spoofed to bypass rate limiting.
        return request.client.host if request.client else "unknown"

    def _cleanup_stale(self) -> None:
        """Remove IPs with no recent hits to prevent memory growth."""
        now = time.monotonic()
        cutoff = now - self._window
        stale = [ip for ip, hits in self._hits.items() if not hits or hits[-1] < cutoff]
        for ip in stale:
            del self._hits[ip]

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path != "/api/chat":
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.monotonic()
        storage = getattr(request.app.state, "conversation_storage", None)
        check_rate_limit = getattr(storage, "check_rate_limit", None)
        if storage is not None and callable(check_rate_limit):
            result = await check_rate_limit(
                bucket="chat",
                key=ip,
                now=now,
                window_seconds=self._window,
                max_requests=self._max,
            )
            if isinstance(result, tuple) and len(result) == 2:
                allowed, _count = result
                if not allowed:
                    logger.warning("Rate limit exceeded for %s", ip)
                    return JSONResponse(
                        status_code=429,
                        content={"error": "Too many requests. Please try again later."},
                        headers={"Retry-After": str(self._window)},
                    )
                return await call_next(request)

        # Fallback for tests or apps without initialized storage.
        if sum(len(v) for v in self._hits.values()) > 1000:
            self._cleanup_stale()

        cutoff = now - self._window
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]
        if len(self._hits[ip]) >= self._max:
            logger.warning("Rate limit exceeded for %s", ip)
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests. Please try again later."},
                headers={"Retry-After": str(self._window)},
            )
        self._hits[ip].append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline API/browser security headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
