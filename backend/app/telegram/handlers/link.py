from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.core.storage import ConversationStorage
from app.telegram.rate_limiter import RateLimiter

_CODE_LENGTH = 8


def _build_numpad() -> InlineKeyboardMarkup:
    """Build a 3×4 inline numpad keyboard."""
    rows = [
        [InlineKeyboardButton(str(d), callback_data=f"link:d:{d}") for d in (1, 2, 3)],
        [InlineKeyboardButton(str(d), callback_data=f"link:d:{d}") for d in (4, 5, 6)],
        [InlineKeyboardButton(str(d), callback_data=f"link:d:{d}") for d in (7, 8, 9)],
        [
            InlineKeyboardButton("←", callback_data="link:bs"),
            InlineKeyboardButton("0", callback_data="link:d:0"),
            InlineKeyboardButton("✓", callback_data="link:ok"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def _build_display_text(digits: str) -> str:
    """Build the display text showing entered digits and remaining blanks."""
    filled = digits + "_" * (_CODE_LENGTH - len(digits))
    return f"📱 Enter the 8-digit link code\n\nCode: {filled}"


class LinkHandler:
    def __init__(
        self,
        storage: ConversationStorage,
        rate_limiter: RateLimiter | None = None,
    ):
        self._storage = storage
        # Dedicated limiter for /link brute-force protection.
        self._rate_limiter = rate_limiter or RateLimiter(max_requests=5, window_seconds=300)

    async def link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if not self._rate_limiter.is_allowed(chat_id):
            await update.message.reply_text("嘗試次數過多，請稍後再試。")
            return

        args = context.args
        if not args:
            # No code provided — show numpad keyboard
            context.user_data["link_digits"] = ""
            msg = await update.message.reply_text(
                _build_display_text(""),
                reply_markup=_build_numpad(),
            )
            context.user_data["link_message_id"] = msg.message_id
            return

        code = args[0].strip()
        if not (len(code) == 8 and code.isdigit()):
            await update.message.reply_text("驗證碼格式錯誤，請輸入 8 位數字。")
            return

        conv = await self._storage.consume_telegram_link_code(code, chat_id)
        if not conv:
            await update.message.reply_text("驗證碼無效、已過期或已使用。")
            return

        await update.message.reply_text(
            f"已成功綁定對話：{conv['title']} ({conv['id']})"
        )

    async def link_from_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle one-tap menu button and reuse /link no-args flow."""
        context.args = []
        await self.link(update, context)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        data = query.data
        digits = context.user_data.get("link_digits", "")

        if data == "link:start":
            context.user_data["link_digits"] = ""
            await query.answer()
            await query.edit_message_text(
                _build_display_text(""),
                reply_markup=_build_numpad(),
            )

        elif data.startswith("link:d:"):
            if len(digits) >= _CODE_LENGTH:
                await query.answer()
                return
            digit = data.split(":")[-1]
            digits += digit
            context.user_data["link_digits"] = digits
            await query.answer()
            await query.edit_message_text(
                _build_display_text(digits),
                reply_markup=_build_numpad(),
            )

        elif data == "link:bs":
            if not digits:
                await query.answer()
                return
            digits = digits[:-1]
            context.user_data["link_digits"] = digits
            await query.answer()
            await query.edit_message_text(
                _build_display_text(digits),
                reply_markup=_build_numpad(),
            )

        elif data == "link:ok":
            if len(digits) < _CODE_LENGTH:
                await query.answer(f"請輸入完整 {_CODE_LENGTH} 位數字")
                return
            await self._submit_code(query, context)

    async def _submit_code(self, query, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = query.message.chat_id
        digits = context.user_data.get("link_digits", "")

        if not self._rate_limiter.is_allowed(chat_id):
            await query.answer("嘗試次數過多，請稍後再試。")
            return

        conv = await self._storage.consume_telegram_link_code(digits, chat_id)
        if not conv:
            context.user_data["link_digits"] = ""
            await query.answer()
            await query.edit_message_text(
                f"❌ 驗證碼無效、已過期或已使用。\n\n{_build_display_text('')}",
                reply_markup=_build_numpad(),
            )
            return

        context.user_data.pop("link_digits", None)
        context.user_data.pop("link_message_id", None)
        await query.answer()
        await query.edit_message_text(
            f"✅ 已成功綁定對話：{conv['title']} ({conv['id']})"
        )
