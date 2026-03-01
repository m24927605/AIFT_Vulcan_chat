import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from app.telegram.storage import SubscriptionStorage

logger = logging.getLogger(__name__)

VALID_FREQUENCIES = {"daily", "weekly"}
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


class SubscribeHandler:
    def __init__(self, storage: SubscriptionStorage):
        self._storage = storage

    async def subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        args = context.args

        if len(args) < 3:
            await update.message.reply_text(
                "📝 格式: /subscribe <主題> <daily|weekly> <HH:MM>\n"
                "例如: /subscribe 科技新聞 daily 09:00"
            )
            return

        topic = args[0]
        frequency = args[1].lower()
        time_str = args[2]

        if frequency not in VALID_FREQUENCIES:
            await update.message.reply_text(
                f"❌ 頻率必須是 daily 或 weekly，收到: {frequency}"
            )
            return

        if not TIME_PATTERN.match(time_str):
            await update.message.reply_text(
                "❌ 時間格式錯誤，請使用 HH:MM 格式，例如 09:00"
            )
            return

        try:
            await self._storage.add(
                chat_id=chat_id,
                topic=topic,
                frequency=frequency,
                time=time_str,
            )
            await update.message.reply_text(
                f"✅ 已訂閱「{topic}」\n"
                f"📅 {frequency}，每天 {time_str} 推送"
            )
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}")

    async def unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        args = context.args

        if not args:
            await update.message.reply_text("📝 格式: /unsubscribe <主題>")
            return

        topic = args[0]
        removed = await self._storage.remove(chat_id=chat_id, topic=topic)

        if removed:
            await update.message.reply_text(f"✅ 已取消訂閱「{topic}」")
        else:
            await update.message.reply_text(f"❌ 找不到訂閱「{topic}」")

    async def list_subscriptions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        subs = await self._storage.list(chat_id=chat_id)

        if not subs:
            await update.message.reply_text("📭 目前沒有任何訂閱。")
            return

        lines = ["📋 你的訂閱:"]
        for s in subs:
            lines.append(f"  • {s['topic']} — {s['frequency']} {s['time']} ({s['timezone']})")
        await update.message.reply_text("\n".join(lines))
