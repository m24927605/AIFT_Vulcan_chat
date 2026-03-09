import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.services.chat_service import ChatService
from app.core.models.events import ChunkEvent
from app.telegram.storage import SubscriptionStorage

logger = logging.getLogger(__name__)


class DigestScheduler:
    def __init__(self, chat_service: ChatService, storage: SubscriptionStorage, bot):
        self._chat_service = chat_service
        self._storage = storage
        self._bot = bot
        self._scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        subs = await self._storage.list_all()
        for sub in subs:
            self._add_job(sub)
        self._scheduler.start()
        logger.info(f"Scheduler started with {len(subs)} jobs")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    async def reload(self) -> None:
        self._scheduler.remove_all_jobs()
        subs = await self._storage.list_all()
        for sub in subs:
            self._add_job(sub)
        logger.info(f"Scheduler reloaded with {len(subs)} jobs")

    def _add_job(self, sub: dict) -> None:
        hour, minute = sub["time"].split(":")
        if sub["frequency"] == "daily":
            trigger = CronTrigger(hour=int(hour), minute=int(minute), timezone=sub["timezone"])
        else:
            trigger = CronTrigger(
                day_of_week="mon", hour=int(hour), minute=int(minute), timezone=sub["timezone"]
            )

        job_id = f"{sub['chat_id']}_{sub['topic']}"
        self._scheduler.add_job(
            self.execute_digest,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            kwargs={"chat_id": sub["chat_id"], "topic": sub["topic"]},
        )

    async def execute_digest(self, chat_id: int, topic: str) -> None:
        try:
            prompt = f"請搜尋並摘要今天關於「{topic}」的重點新聞，用繁體中文回答"
            full_text = ""
            async for event in self._chat_service.process_message(message=prompt):
                if isinstance(event, ChunkEvent):
                    full_text += event.content

            await self._bot.send_message(
                chat_id=chat_id,
                text=f"📰 {topic} 摘要\n\n{full_text}",
            )
        except Exception as e:
            logger.error(
                "Digest delivery failed for %s/%s (%s)",
                chat_id, topic, type(e).__name__,
            )
            await self._bot.send_message(
                chat_id=chat_id,
                text=f"❌ 「{topic}」摘要產生時發生錯誤，請稍後再試。",
            )
