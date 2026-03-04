"""Tests for Telegram push retry with exponential backoff."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.web.routes.chat import _push_to_telegram


class TestTelegramRetry:
    async def test_success_on_first_attempt(self):
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        with patch("app.web.routes.chat.Bot", return_value=mock_bot), \
             patch("app.web.routes.chat.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test-token"
            await _push_to_telegram(123, "Hello", "World")

        mock_bot.send_message.assert_called_once()

    async def test_retries_on_failure(self):
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(
            side_effect=[Exception("Network error"), Exception("Timeout"), None]
        )

        with patch("app.web.routes.chat.Bot", return_value=mock_bot), \
             patch("app.web.routes.chat.settings") as mock_settings, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_settings.telegram_bot_token = "test-token"
            await _push_to_telegram(123, "Hello", "World")

        assert mock_bot.send_message.call_count == 3
        assert mock_sleep.call_count == 2
        # Exponential backoff: 1s, 2s
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    async def test_gives_up_after_max_retries(self):
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=Exception("Permanent failure"))

        with patch("app.web.routes.chat.Bot", return_value=mock_bot), \
             patch("app.web.routes.chat.settings") as mock_settings, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_settings.telegram_bot_token = "test-token"
            # Should not raise — just logs
            await _push_to_telegram(123, "Hello", "World")

        assert mock_bot.send_message.call_count == 3

    async def test_skips_when_no_token(self):
        with patch("app.web.routes.chat.settings") as mock_settings:
            mock_settings.telegram_bot_token = ""
            await _push_to_telegram(123, "Hello", "World")
            # No exception, no Bot created
