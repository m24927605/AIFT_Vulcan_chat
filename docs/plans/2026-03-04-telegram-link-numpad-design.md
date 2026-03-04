# Telegram Link Numpad — Design

## Problem

Users must manually type `/link 12345678` in Telegram to link a conversation.
This is error-prone (typos in 8-digit codes) and unfamiliar to non-technical users.

## Solution

Add a 3×4 inline numpad keyboard to the Telegram `/link` command.
Bot edits the same message on each keypress to show progress.

## User Flow

```
User: /link                          (no arguments)
Bot:  📱 Enter the 8-digit link code
      Code: ________
      [1] [2] [3]
      [4] [5] [6]
      [7] [8] [9]
      [←] [0] [✓]

User taps digits → Bot edits message in-place:
      Code: 1234____

User taps [✓] after 8 digits → Bot verifies code:
  ✅ Success → "Linked to 'My Chat' (conv-abc)" (keyboard removed)
  ❌ Failure → "Invalid or expired code" + reset to empty, keep keyboard
```

## Backward Compatibility

- `/link 12345678` (with argument) → existing text-based flow, unchanged
- `/link` (no argument) → new numpad keyboard flow

## Keyboard Layout (3×4)

```
[1] [2] [3]
[4] [5] [6]
[7] [8] [9]
[←] [0] [✓]
```

- `←` — delete last digit (no-op when empty)
- `✓` — submit code (no-op when < 8 digits; shows hint)
- Digit buttons — no-op when already 8 digits

## State Management

- `context.user_data["link_digits"]` — string of entered digits
- `context.user_data["link_message_id"]` — message ID to edit
- No database needed; pure in-memory state per user

## Callback Data Format

| Callback data | Action |
|---------------|--------|
| `link:d:0`–`link:d:9` | Append digit |
| `link:bs` | Backspace (delete last) |
| `link:ok` | Submit code |

## Edge Cases

- ← when empty → ignore (answer callback silently)
- ✓ when < 8 digits → answer callback with "Please enter all 8 digits"
- Digit when already 8 digits → ignore
- Multiple `/link` calls → latest overwrites user_data
- Verification failure → clear digits, keep keyboard for retry
- Rate limiting → reuse existing LinkHandler rate limiter

## Files Changed

| File | Change |
|------|--------|
| `backend/app/telegram/handlers/link.py` | Split `/link` with/without args; add `handle_callback()` for numpad |
| `backend/app/entrypoint.py` | Register `CallbackQueryHandler(pattern="^link:")` |
| `backend/tests/telegram/test_link_handler.py` | Add tests for numpad flow |

## Not Changed

- `backend/app/core/storage.py` — code generation/verification unchanged
- `backend/app/web/routes/` — web API unchanged
- `frontend/` — no frontend changes
- Rate limiter — callbacks share existing rate limit
