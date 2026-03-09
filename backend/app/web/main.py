import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.core.exceptions import ChatError, chat_error_handler
from app.core.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    setup_logging,
)
from app.core.storage import ConversationStorage
from app.web.routes import chat, health, notify, conversations, analysis

setup_logging()


def _validate_web_settings() -> None:
    if not settings.api_secret_key:
        if settings.frontend_url != "http://localhost:3000":
            logger.critical(
                "API_SECRET_KEY is empty with FRONTEND_URL=%s — refusing to start.",
                settings.frontend_url,
            )
            raise SystemExit(1)
        logger.warning("API_SECRET_KEY is empty — auth disabled (dev mode).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_web_settings()
    app.state.started_at = time.time()
    storage = ConversationStorage()
    await storage.initialize()
    app.state.conversation_storage = storage
    yield
    await storage.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Vulcan Web Search Chatbot",
        version="0.1.7",
        lifespan=lifespan,
    )

    # Middleware order: outermost first
    origins = [settings.frontend_url]
    if not settings.api_secret_key:
        # Dev mode only — allow localhost for local frontend development
        origins.append("http://localhost:3000")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=30, window_seconds=60)

    app.add_exception_handler(ChatError, chat_error_handler)

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(notify.router)
    app.include_router(conversations.router)
    app.include_router(analysis.router)

    return app


app = create_app()
