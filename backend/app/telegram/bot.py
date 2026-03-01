import logging

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """👋 Hi {name}! I'm Vulcan, your AI search assistant.

Send me any question and I'll search the web to find the answer!

Type /help to see all available commands."""

HELP_MESSAGE = """📖 Available commands:

/start - Welcome message
/help - Show this help
/subscribe <topic> <daily|weekly> <HH:MM> - Subscribe to digests
/unsubscribe <topic> - Unsubscribe from a topic
/list - List your subscriptions

Or just send me a message to chat!"""


async def start_command(update: Update, context) -> None:
    name = update.effective_user.first_name
    await update.message.reply_text(WELCOME_MESSAGE.format(name=name))


async def help_command(update: Update, context) -> None:
    await update.message.reply_text(HELP_MESSAGE)


def create_bot(
    token: str,
    chat_handler=None,
    subscribe_handler=None,
    unsubscribe_handler=None,
    list_handler=None,
    stats_handler=None,
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
    if chat_handler:
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    return app
