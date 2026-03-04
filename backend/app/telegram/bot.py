import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """👋 Hi {name}! I'm Vulcan, your AI search assistant.

Send me any question and I'll search the web to find the answer!

Tap the button below to link a web conversation with numeric keypad.
Type /help to see all available commands."""

HELP_MESSAGE = """📖 Available commands:

/start - Welcome message
/help - Show this help
/subscribe <topic> <daily|weekly> <HH:MM> - Subscribe to digests
/unsubscribe <topic> - Unsubscribe from a topic
/list - List your subscriptions
/link - Link this Telegram chat to a web conversation
/link <code> - Link with code directly

Or just send me a message to chat!"""

LINK_MENU_TEXT = "🔗 Start Linking"


def _menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(LINK_MENU_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


async def start_command(update: Update, context) -> None:
    if context.args and context.args[0].lower() == "link":
        context.user_data["link_digits"] = ""
        await update.message.reply_text(
            "📱 Enter the 8-digit link code\n\nCode: ________",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(str(d), callback_data=f"link:d:{d}") for d in (1, 2, 3)],
                    [InlineKeyboardButton(str(d), callback_data=f"link:d:{d}") for d in (4, 5, 6)],
                    [InlineKeyboardButton(str(d), callback_data=f"link:d:{d}") for d in (7, 8, 9)],
                    [
                        InlineKeyboardButton("←", callback_data="link:bs"),
                        InlineKeyboardButton("0", callback_data="link:d:0"),
                        InlineKeyboardButton("✓", callback_data="link:ok"),
                    ],
                ]
            ),
        )
        return

    name = update.effective_user.first_name
    await update.message.reply_text(
        WELCOME_MESSAGE.format(name=name),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 Start Linking", callback_data="link:start")]]
        ),
    )
    await update.message.reply_text("Use the menu button below to start linking anytime.", reply_markup=_menu_keyboard())


async def help_command(update: Update, context) -> None:
    await update.message.reply_text(HELP_MESSAGE)


def create_bot(
    token: str,
    chat_handler=None,
    subscribe_handler=None,
    unsubscribe_handler=None,
    list_handler=None,
    stats_handler=None,
    link_handler=None,
    link_callback_handler=None,
    link_menu_handler=None,
) -> Application:
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    if subscribe_handler:
        app.add_handler(CommandHandler("subscribe", subscribe_handler))
    if unsubscribe_handler:
        app.add_handler(CommandHandler("unsubscribe", unsubscribe_handler))
    if list_handler:
        app.add_handler(CommandHandler("list", list_handler))
    if stats_handler:
        app.add_handler(CommandHandler("stats", stats_handler))
    if link_handler:
        app.add_handler(CommandHandler("link", link_handler))
    if link_callback_handler:
        app.add_handler(CallbackQueryHandler(link_callback_handler, pattern=r"^link:"))
    if link_menu_handler:
        app.add_handler(
            MessageHandler(
                filters.Regex(r"^🔗 (Start Linking|開始綁定)$") & ~filters.COMMAND,
                link_menu_handler,
            )
        )
    if chat_handler:
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    return app
