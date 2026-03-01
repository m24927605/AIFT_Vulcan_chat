import asyncio
import logging
import os

import uvicorn

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_mode() -> str:
    return os.environ.get("MODE", settings.mode)


async def start_telegram():
    from app.core.services.chat_service import ChatService
    from app.telegram.bot import create_bot
    from app.telegram.handlers.chat import ChatHandler
    from app.telegram.handlers.subscribe import SubscribeHandler
    from app.telegram.handlers.admin import AdminHandler
    from app.telegram.rate_limiter import RateLimiter
    from app.telegram.storage import SubscriptionStorage
    from app.telegram.scheduler import DigestScheduler

    chat_service = ChatService(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        tavily_api_key=settings.tavily_api_key,
    )

    storage = SubscriptionStorage()
    await storage.initialize()

    rate_limiter = RateLimiter(max_requests=20, window_seconds=60)
    chat_handler = ChatHandler(chat_service=chat_service, rate_limiter=rate_limiter)
    subscribe_handler = SubscribeHandler(storage=storage)
    admin_handler = AdminHandler(storage=storage, admin_ids=settings.telegram_admin_ids)

    app = create_bot(
        token=settings.telegram_bot_token,
        chat_handler=chat_handler.handle,
        subscribe_handler=subscribe_handler.subscribe,
        unsubscribe_handler=subscribe_handler.unsubscribe,
        list_handler=subscribe_handler.list_subscriptions,
        stats_handler=admin_handler.stats,
    )

    scheduler = DigestScheduler(
        chat_service=chat_service,
        storage=storage,
        bot=app.bot,
    )
    await scheduler.start()

    logger.info("Starting Telegram bot...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.stop()
        await storage.close()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def start_web():
    uvicorn.run(
        "app.web.main:app",
        host="0.0.0.0",
        port=8000,
    )


async def start_all():
    loop = asyncio.get_event_loop()
    web_task = loop.run_in_executor(None, start_web)
    telegram_task = asyncio.create_task(start_telegram())
    await asyncio.gather(web_task, telegram_task)


def main():
    logging.basicConfig(level=logging.INFO)
    mode = get_mode()
    logger.info(f"Starting in {mode} mode")

    if mode == "web":
        start_web()
    elif mode == "telegram":
        asyncio.run(start_telegram())
    elif mode == "all":
        asyncio.run(start_all())
    else:
        raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
