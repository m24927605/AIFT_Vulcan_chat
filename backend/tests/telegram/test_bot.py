import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.telegram.bot import create_bot, start_command, help_command


@pytest.mark.asyncio
async def test_start_command_sends_welcome():
    update = AsyncMock()
    update.effective_user.first_name = "Alice"
    context = MagicMock()

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "Alice" in call_text


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
