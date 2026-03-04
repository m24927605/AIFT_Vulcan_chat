import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.telegram.bot import create_bot, start_command, help_command


@pytest.mark.asyncio
async def test_start_command_sends_welcome():
    update = AsyncMock()
    update.effective_user.first_name = "Alice"
    context = MagicMock()
    context.args = []
    context.user_data = {}

    await start_command(update, context)

    assert update.message.reply_text.call_count == 2
    first_call = update.message.reply_text.call_args_list[0]
    call_text = first_call[0][0]
    assert "Alice" in call_text
    reply_markup = first_call.kwargs.get("reply_markup")
    assert reply_markup is not None
    assert reply_markup.inline_keyboard[0][0].callback_data == "link:start"


@pytest.mark.asyncio
async def test_start_command_with_link_payload_shows_numpad():
    update = AsyncMock()
    update.effective_user.first_name = "Alice"
    context = MagicMock()
    context.args = ["link"]
    context.user_data = {}

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args
    assert "8-digit" in call_args[0][0]
    assert call_args.kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_help_command_lists_commands():
    update = AsyncMock()
    context = MagicMock()

    await help_command(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "/start" in call_text
    assert "/help" in call_text
    assert "/subscribe" in call_text


def test_create_bot_returns_application():
    with patch("app.telegram.bot.ApplicationBuilder") as mock_builder:
        mock_app = MagicMock()
        mock_builder.return_value.token.return_value.build.return_value = mock_app
        app = create_bot(token="test-token")
        assert app is not None
