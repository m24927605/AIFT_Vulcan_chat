from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import ChatError, chat_error_handler
from app.web.routes import chat, health


def create_app() -> FastAPI:
    app = FastAPI(title="Vulcan Web Search Chatbot", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ChatError, chat_error_handler)

    app.include_router(health.router)
    app.include_router(chat.router)

    return app


app = create_app()
