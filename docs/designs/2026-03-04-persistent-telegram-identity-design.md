# Persistent Telegram Identity Design

## Problem

Telegram link (`telegram_chat_id`) is stored on the `conversations` table. Deleting all conversations loses the link, requiring the user to re-link. This is poor UX.

## Solution

Move the Telegram identity to the `web_sessions` table. Conversations inherit `telegram_chat_id` from their owning session. Deleting conversations no longer affects the link.

## Schema Change

Add `telegram_chat_id INTEGER` column to `web_sessions`. Migration via `ALTER TABLE` in `storage.py:initialize()`.

## Flow Changes

### Linking
When a link code is consumed:
1. Set `web_sessions.telegram_chat_id` for the owning session
2. Set `conversations.telegram_chat_id` for ALL conversations owned by that session

### New Conversation
`create_conversation` with a `web_owner_session_id` auto-populates `telegram_chat_id` from the session.

### Unlinking
1. Clear `web_sessions.telegram_chat_id`
2. Clear `conversations.telegram_chat_id` for all conversations in that session

### Session Rotation
Copy `telegram_chat_id` from old session to new session (alongside existing ownership migration).

### Delete Conversation
No change needed. Link survives on the session.

## API Changes

- `GET /api/conversations` returns `session_telegram_chat_id` alongside conversation list
- Unlink endpoint operates on session, not individual conversation
- Link code consumption updates session + all conversations

## Frontend Changes

- Sidebar "Linked to Telegram" / "Get Link Code" based on session-level state
- Auto-link polling updates session state, not per-conversation state
- New conversations auto-show as linked when session is linked
