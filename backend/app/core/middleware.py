"""
Request middleware: logging, request ID tracing, rate limiting.
"""

import logging
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


class RequestIDFilter(logging.Filter):
    """Inject request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


def setup_logging() -> None:
    """Configure structured logging with request ID."""
    fmt = "%(asctime)s %(levelname)-5s [%(request_id)s] %(name)s – %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    handler.addFilter(RequestIDFilter())

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

        # Periodic cleanup (every 100 requests)
        if sum(len(v) for v in self._hits.values()) > 1000:
            self._cleanup_stale()

        ip = self._client_ip(request)
        now = time.monotonic()
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
