import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.telegram.storage import SubscriptionStorage

logger = logging.getLogger(__name__)


class AdminHandler:
    def __init__(self, storage: SubscriptionStorage, admin_ids: list[int]):
        self._storage = storage
        self._admin_ids = admin_ids

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id

        if chat_id not in self._admin_ids:
            await update.message.reply_text("🚫 你沒有權限使用此指令。")
            return

        subs = await self._storage.list_all()
        unique_users = len(set(s["chat_id"] for s in subs))

        await update.message.reply_text(
            f"📊 Bot 統計\n\n"
            f"📝 總訂閱數: {len(subs)}\n"
            f"👥 訂閱用戶數: {unique_users}"
        )
