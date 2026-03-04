from unittest.mock import AsyncMock, MagicMock

import pytest

from app.telegram.bot import create_bot
from app.telegram.handlers.link import LinkHandler, _build_numpad, _build_display_text


def _make_update(chat_id: int = 123):
    update = AsyncMock()
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


def test_bot_registers_link_callback_handler():
    """CallbackQueryHandler for 'link:' pattern should be registered."""
    bot_app = create_bot(
        token="fake-token",
        link_handler=MagicMock(),
        link_callback_handler=MagicMock(),
    )
    handler_types = [type(h).__name__ for h in bot_app.handlers[0]]
    assert "CallbackQueryHandler" in handler_types


@pytest.mark.asyncio
async def test_link_handler_rejects_when_rate_limited():
    storage = AsyncMock()
    limiter = MagicMock()
    limiter.is_allowed.return_value = False
    handler = LinkHandler(storage=storage, rate_limiter=limiter)
    update = _make_update()
    context = MagicMock()
    context.args = ["12345678"]

    await handler.link(update, context)

    update.message.reply_text.assert_called_once()
    assert "太多" in update.message.reply_text.call_args[0][0] or "稍後" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_link_handler_consumes_code_when_allowed():
    storage = AsyncMock()
    storage.consume_telegram_link_code.return_value = {"id": "conv-1", "title": "Test"}
    limiter = MagicMock()
    limiter.is_allowed.return_value = True
    handler = LinkHandler(storage=storage, rate_limiter=limiter)
    update = _make_update(chat_id=456)
    context = MagicMock()
    context.args = ["12345678"]

    await handler.link(update, context)

    storage.consume_telegram_link_code.assert_awaited_once_with("12345678", 456)
    assert "成功" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_link_no_args_shows_numpad():
    """``/link`` (no code) should reply with numpad keyboard."""
    storage = AsyncMock()
    handler = LinkHandler(storage=storage)
    update = _make_update(chat_id=789)
    context = MagicMock()
    context.args = []
    context.user_data = {}

    await handler.link(update, context)

    update.message.reply_text.assert_called_once()
    call_kwargs = update.message.reply_text.call_args
    # Should include the numpad keyboard
    assert call_kwargs.kwargs.get("reply_markup") is not None
    # Should store digits state
    assert context.user_data["link_digits"] == ""


def _make_callback_query(chat_id: int, data: str, message_id: int = 100):
    query = AsyncMock()
    query.data = data
    query.message.chat_id = chat_id
    query.message.message_id = message_id
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    update = AsyncMock()
    update.callback_query = query
    update.effective_chat.id = chat_id
    return update, query


class TestHandleCallback:
    @pytest.mark.asyncio
    async def test_start_resets_and_shows_numpad(self):
        storage = AsyncMock()
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(111, "link:start")
        context = MagicMock()
        context.user_data = {"link_digits": "1234"}

        await handler.handle_callback(update, context)

        assert context.user_data["link_digits"] == ""
        query.answer.assert_called_once()
        query.edit_message_text.assert_called_once()
        assert query.edit_message_text.call_args.kwargs.get("reply_markup") is not None

    @pytest.mark.asyncio
    async def test_digit_appends(self):
        storage = AsyncMock()
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(111, "link:d:5")
        context = MagicMock()
        context.user_data = {"link_digits": "12", "link_message_id": 100}

        await handler.handle_callback(update, context)

        query.answer.assert_called_once()
        query.edit_message_text.assert_called_once()
        assert context.user_data["link_digits"] == "125"
        edit_text = query.edit_message_text.call_args[0][0]
        assert "125_____" in edit_text

    @pytest.mark.asyncio
    async def test_digit_ignored_when_full(self):
        storage = AsyncMock()
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(111, "link:d:9")
        context = MagicMock()
        context.user_data = {"link_digits": "12345678", "link_message_id": 100}

        await handler.handle_callback(update, context)

        query.answer.assert_called_once()
        query.edit_message_text.assert_not_called()
        assert context.user_data["link_digits"] == "12345678"

    @pytest.mark.asyncio
    async def test_backspace_removes_last(self):
        storage = AsyncMock()
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(111, "link:bs")
        context = MagicMock()
        context.user_data = {"link_digits": "123", "link_message_id": 100}

        await handler.handle_callback(update, context)

        assert context.user_data["link_digits"] == "12"
        query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_backspace_ignored_when_empty(self):
        storage = AsyncMock()
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(111, "link:bs")
        context = MagicMock()
        context.user_data = {"link_digits": "", "link_message_id": 100}

        await handler.handle_callback(update, context)

        assert context.user_data["link_digits"] == ""
        query.answer.assert_called_once()
        query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_rejected_when_incomplete(self):
        storage = AsyncMock()
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(111, "link:ok")
        context = MagicMock()
        context.user_data = {"link_digits": "123", "link_message_id": 100}

        await handler.handle_callback(update, context)

        query.answer.assert_called_once()
        assert "8" in query.answer.call_args[0][0]
        query.edit_message_text.assert_not_called()


class TestSubmitCode:
    @pytest.mark.asyncio
    async def test_submit_success_removes_keyboard(self):
        storage = AsyncMock()
        storage.consume_telegram_link_code.return_value = {"id": "conv-1", "title": "My Chat"}
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(222, "link:ok")
        context = MagicMock()
        context.user_data = {"link_digits": "12345678", "link_message_id": 100}

        await handler.handle_callback(update, context)

        storage.consume_telegram_link_code.assert_awaited_once_with("12345678", 222)
        query.answer.assert_called_once()
        query.edit_message_text.assert_called_once()
        edit_call = query.edit_message_text.call_args
        assert "My Chat" in edit_call[0][0]
        assert edit_call.kwargs.get("reply_markup") is None

    @pytest.mark.asyncio
    async def test_submit_failure_resets_digits(self):
        storage = AsyncMock()
        storage.consume_telegram_link_code.return_value = None
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(222, "link:ok")
        context = MagicMock()
        context.user_data = {"link_digits": "99999999", "link_message_id": 100}

        await handler.handle_callback(update, context)

        assert context.user_data["link_digits"] == ""
        query.edit_message_text.assert_called_once()
        edit_call = query.edit_message_text.call_args
        assert "無效" in edit_call[0][0] or "Invalid" in edit_call[0][0]
        assert edit_call.kwargs.get("reply_markup") is not None

    @pytest.mark.asyncio
    async def test_submit_rate_limited(self):
        storage = AsyncMock()
        limiter = MagicMock()
        limiter.is_allowed.return_value = False
        handler = LinkHandler(storage=storage, rate_limiter=limiter)
        update, query = _make_callback_query(222, "link:ok")
        context = MagicMock()
        context.user_data = {"link_digits": "12345678", "link_message_id": 100}

        await handler.handle_callback(update, context)

        storage.consume_telegram_link_code.assert_not_awaited()
        query.answer.assert_called_once()


class TestLinkTextFlow:
    """Tests for the original /link <code> text-based flow."""

    @pytest.mark.asyncio
    async def test_invalid_code_format_rejected(self):
        storage = AsyncMock()
        handler = LinkHandler(storage=storage)
        update = _make_update()
        context = MagicMock()
        context.args = ["abc"]

        await handler.link(update, context)

        storage.consume_telegram_link_code.assert_not_awaited()
        assert "格式" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_expired_code_rejected(self):
        storage = AsyncMock()
        storage.consume_telegram_link_code.return_value = None
        handler = LinkHandler(storage=storage)
        update = _make_update(chat_id=456)
        context = MagicMock()
        context.args = ["99999999"]

        await handler.link(update, context)

        storage.consume_telegram_link_code.assert_awaited_once_with("99999999", 456)
        assert "無效" in update.message.reply_text.call_args[0][0]


class TestNumpadNoState:
    """Tests for callback when user_data has no prior /link state."""

    @pytest.mark.asyncio
    async def test_digit_with_no_prior_state(self):
        """Callback arrives but user never called /link — treat as empty."""
        storage = AsyncMock()
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(111, "link:d:3")
        context = MagicMock()
        context.user_data = {}  # no link_digits

        await handler.handle_callback(update, context)

        # Should treat as starting from empty and append
        assert context.user_data["link_digits"] == "3"
        query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_with_no_prior_state(self):
        """Submit with no digits — should reject with hint."""
        storage = AsyncMock()
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(111, "link:ok")
        context = MagicMock()
        context.user_data = {}

        await handler.handle_callback(update, context)

        query.answer.assert_called_once()
        assert "8" in query.answer.call_args[0][0]
        storage.consume_telegram_link_code.assert_not_awaited()


class TestSubmitClearsState:
    """Verify success clears all link-related user_data keys."""

    @pytest.mark.asyncio
    async def test_success_clears_user_data(self):
        storage = AsyncMock()
        storage.consume_telegram_link_code.return_value = {"id": "c-1", "title": "T"}
        handler = LinkHandler(storage=storage)
        update, query = _make_callback_query(333, "link:ok")
        context = MagicMock()
        context.user_data = {"link_digits": "12345678", "link_message_id": 100, "other_key": "keep"}

        await handler.handle_callback(update, context)

        assert "link_digits" not in context.user_data
        assert "link_message_id" not in context.user_data
        assert context.user_data["other_key"] == "keep"


class TestBotRegistration:
    """Tests for bot handler registration."""

    def test_bot_works_without_link_callback(self):
        """Bot should work when link_callback_handler is not provided."""
        bot_app = create_bot(token="fake-token", link_handler=MagicMock())
        handler_types = [type(h).__name__ for h in bot_app.handlers[0]]
        assert "CallbackQueryHandler" not in handler_types
        assert "CommandHandler" in handler_types


class TestBuildNumpad:
    def test_numpad_has_4_rows(self):
        kb = _build_numpad()
        assert len(kb.inline_keyboard) == 4

    def test_numpad_row_widths(self):
        kb = _build_numpad()
        assert len(kb.inline_keyboard[0]) == 3  # 1 2 3
        assert len(kb.inline_keyboard[1]) == 3  # 4 5 6
        assert len(kb.inline_keyboard[2]) == 3  # 7 8 9
        assert len(kb.inline_keyboard[3]) == 3  # ← 0 ✓

    def test_digit_callback_data_format(self):
        kb = _build_numpad()
        btn = kb.inline_keyboard[0][0]  # "1"
        assert btn.callback_data == "link:d:1"

    def test_backspace_callback_data(self):
        kb = _build_numpad()
        btn = kb.inline_keyboard[3][0]  # "←"
        assert btn.callback_data == "link:bs"

    def test_submit_callback_data(self):
        kb = _build_numpad()
        btn = kb.inline_keyboard[3][2]  # "✓"
        assert btn.callback_data == "link:ok"


class TestBuildDisplayText:
    def test_empty(self):
        text = _build_display_text("")
        assert "________" in text

    def test_partial(self):
        text = _build_display_text("123")
        assert "123_____" in text

    def test_full(self):
        text = _build_display_text("12345678")
        assert "12345678" in text
        assert "_" not in text
