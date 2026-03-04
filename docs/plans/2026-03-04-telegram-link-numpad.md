# Telegram Link Numpad Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a 3×4 inline numpad keyboard to the Telegram `/link` command so users can tap digits instead of typing an 8-digit code.

**Architecture:** When `/link` is called without arguments, the bot sends a message with an InlineKeyboardMarkup (3×4 grid). Each button press triggers a CallbackQuery that edits the same message to show progress. On submit, the existing `consume_telegram_link_code()` is called. The old `/link 12345678` text flow remains unchanged.

**Tech Stack:** python-telegram-bot (already installed), InlineKeyboardButton/Markup, CallbackQueryHandler

---

### Task 1: Numpad keyboard builder + display text helper

**Files:**
- Modify: `backend/app/telegram/handlers/link.py`
- Test: `backend/tests/telegram/test_link_handler.py`

**Step 1: Write failing tests for the two helpers**

Add to `backend/tests/telegram/test_link_handler.py`:

```python
from app.telegram.handlers.link import _build_numpad, _build_display_text


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
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py::TestBuildNumpad -v && python -m pytest tests/telegram/test_link_handler.py::TestBuildDisplayText -v`
Expected: FAIL with ImportError (`cannot import name '_build_numpad'`)

**Step 3: Implement the helpers**

Add to the top of `backend/app/telegram/handlers/link.py` (after existing imports):

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py::TestBuildNumpad tests/telegram/test_link_handler.py::TestBuildDisplayText -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/handlers/link.py backend/tests/telegram/test_link_handler.py
git commit -m "feat(telegram): add numpad keyboard builder and display text helper"
```

---

### Task 2: `/link` without args shows numpad

**Files:**
- Modify: `backend/app/telegram/handlers/link.py` (the `link()` method)
- Test: `backend/tests/telegram/test_link_handler.py`

**Step 1: Write failing test**

Add to `backend/tests/telegram/test_link_handler.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py::test_link_no_args_shows_numpad -v`
Expected: FAIL — current code replies with plain text "格式: /link <8位數驗證碼>" and no `reply_markup`

**Step 3: Modify the `link()` method**

In `backend/app/telegram/handlers/link.py`, replace the `if not args:` block inside `link()`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py -v`
Expected: All PASS (both old and new tests)

**Step 5: Commit**

```bash
git add backend/app/telegram/handlers/link.py backend/tests/telegram/test_link_handler.py
git commit -m "feat(telegram): show numpad when /link called without args"
```

---

### Task 3: Callback handler for numpad button presses

**Files:**
- Modify: `backend/app/telegram/handlers/link.py`
- Test: `backend/tests/telegram/test_link_handler.py`

**Step 1: Write failing tests for digit, backspace, and edge cases**

Add to `backend/tests/telegram/test_link_handler.py`:

```python
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
        # Display should show "125_____"
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
        assert "8" in query.answer.call_args[0][0]  # hint about 8 digits
        query.edit_message_text.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py::TestHandleCallback -v`
Expected: FAIL — `LinkHandler` has no `handle_callback` method

**Step 3: Implement `handle_callback()`**

Add to `LinkHandler` class in `backend/app/telegram/handlers/link.py`:

```python
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        data = query.data  # e.g. "link:d:5", "link:bs", "link:ok"
        digits = context.user_data.get("link_digits", "")

        if data.startswith("link:d:"):
            # Append digit
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
            # Backspace
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
            # Submit
            if len(digits) < _CODE_LENGTH:
                await query.answer(f"請輸入完整 {_CODE_LENGTH} 位數字")
                return
            await self._submit_code(query, context)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py::TestHandleCallback -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/handlers/link.py backend/tests/telegram/test_link_handler.py
git commit -m "feat(telegram): handle numpad digit/backspace/submit callbacks"
```

---

### Task 4: Submit logic — verify code and show result

**Files:**
- Modify: `backend/app/telegram/handlers/link.py`
- Test: `backend/tests/telegram/test_link_handler.py`

**Step 1: Write failing tests for submit success and failure**

Add to `backend/tests/telegram/test_link_handler.py`:

```python
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
        # Keyboard should be removed (reply_markup not set, or set to None)
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

        # Digits should be reset
        assert context.user_data["link_digits"] == ""
        query.edit_message_text.assert_called_once()
        edit_call = query.edit_message_text.call_args
        # Should show error + blank code + keep keyboard
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
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py::TestSubmitCode -v`
Expected: FAIL — `_submit_code` method doesn't exist yet

**Step 3: Implement `_submit_code()`**

Add to `LinkHandler` class in `backend/app/telegram/handlers/link.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py::TestSubmitCode -v`
Expected: All PASS

**Step 5: Run ALL link handler tests**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py -v`
Expected: All PASS (old text-flow tests + all new numpad tests)

**Step 6: Commit**

```bash
git add backend/app/telegram/handlers/link.py backend/tests/telegram/test_link_handler.py
git commit -m "feat(telegram): implement numpad submit with success/failure/rate-limit"
```

---

### Task 5: Register CallbackQueryHandler in bot and entrypoint

**Files:**
- Modify: `backend/app/telegram/bot.py`
- Modify: `backend/app/entrypoint.py`

**Step 1: Write failing test**

Add to `backend/tests/telegram/test_link_handler.py`:

```python
from app.telegram.bot import create_bot


def test_bot_registers_link_callback_handler():
    """CallbackQueryHandler for 'link:' pattern should be registered."""
    bot_app = create_bot(
        token="fake-token",
        link_handler=MagicMock(),
        link_callback_handler=MagicMock(),
    )
    handler_types = [type(h).__name__ for h in bot_app.handlers[0]]
    assert "CallbackQueryHandler" in handler_types
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py::test_bot_registers_link_callback_handler -v`
Expected: FAIL — `create_bot` doesn't accept `link_callback_handler` param

**Step 3: Update `bot.py`**

In `backend/app/telegram/bot.py`:

1. Add `CallbackQueryHandler` to the imports.
2. Add `link_callback_handler` parameter to `create_bot()`.
3. Register it with a `pattern` filter.

Replace the import block:

```python
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
```

Update the `/link` help text:

```python
HELP_MESSAGE = """📖 Available commands:

/start - Welcome message
/help - Show this help
/subscribe <topic> <daily|weekly> <HH:MM> - Subscribe to digests
/unsubscribe <topic> - Unsubscribe from a topic
/list - List your subscriptions
/link - Link this Telegram chat to a web conversation
/link <code> - Link with code directly

Or just send me a message to chat!"""
```

Add parameter and registration in `create_bot()`:

```python
def create_bot(
    token: str,
    chat_handler=None,
    subscribe_handler=None,
    unsubscribe_handler=None,
    list_handler=None,
    stats_handler=None,
    link_handler=None,
    link_callback_handler=None,
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
    if chat_handler:
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    return app
```

**Step 4: Update `entrypoint.py`**

In `backend/app/entrypoint.py`, pass the callback handler to `create_bot()`. Change the `create_bot(...)` call:

```python
    app = create_bot(
        token=settings.telegram_bot_token,
        chat_handler=chat_handler.handle,
        subscribe_handler=subscribe_handler.subscribe,
        unsubscribe_handler=subscribe_handler.unsubscribe,
        list_handler=subscribe_handler.list_subscriptions,
        stats_handler=admin_handler.stats,
        link_handler=link_handler.link,
        link_callback_handler=link_handler.handle_callback,
    )
```

**Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/telegram/test_link_handler.py::test_bot_registers_link_callback_handler -v`
Expected: PASS

**Step 6: Run full test suite**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: All PASS

**Step 7: Commit**

```bash
git add backend/app/telegram/bot.py backend/app/entrypoint.py backend/tests/telegram/test_link_handler.py
git commit -m "feat(telegram): register numpad callback handler in bot"
```

---

### Task 6: Final verification — full test suite

**Step 1: Run all backend tests**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: All PASS, no regressions

**Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: All PASS

**Step 3: Commit (if any cleanup needed)**

Only if adjustments were needed. Otherwise skip.
