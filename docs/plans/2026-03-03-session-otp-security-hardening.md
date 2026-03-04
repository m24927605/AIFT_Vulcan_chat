# Session + Telegram OTP Security Hardening

Date: 2026-03-03
Owner: Codex
Status: Implemented

## Background

The project previously used conversation tokens exposed to frontend JavaScript and direct Telegram chat-id linking. This introduced avoidable security risks:

1. Browser-readable auth material (`localStorage` token exposure under XSS)
2. Weak ownership model for conversation access
3. Direct `link-telegram` by chat-id without possession proof

## Goals

1. Replace browser token auth with server-managed HttpOnly session cookie
2. Enforce owner-based access control on conversation APIs
3. Preserve existing Web ↔ Telegram message sync behavior
4. Add Telegram linking possession proof via one-time code
5. Keep backward compatibility where reasonable, and update tests/docs

## Scope

### In scope

- Backend session model with persistence, UA/IP binding, and rotation
- Conversation ownership checks by session
- Telegram link-code generation + `/link <code>` confirmation
- Frontend API usage switched to cookie credentials
- Regression test updates
- User-facing docs update

### Out of scope

- Full account system (login/signup/JWT)
- Cross-device identity merge UX
- Bot-side unlink confirmation flow

## Design Decisions

### 1. Session model (anonymous owner)

- Cookie name: `vulcan_session`
- Cookie flags: `HttpOnly`, `SameSite=Lax`, `Secure` when request scheme is `https`
- Server persistence table: `web_sessions`
- Validation factors:
  - `session_id`
  - `ua_hash` (SHA-256 of user agent)
  - `ip_prefix` (IPv4 `/24`-style prefix, fallback raw host for non-IPv4)
  - expiry and revocation state
- Rotation:
  - Rotate every 24h (`SESSION_ROTATE_SECONDS`)
  - New cookie issued, old session revoked with `rotated_to`

### 2. Conversation ownership

- `conversations` table gains `web_owner_session_id`
- All web conversation endpoints enforce owner check
- Telegram sync field `telegram_chat_id` remains unchanged to preserve bot sync behavior

### 3. Telegram linking via one-time code

- New table: `telegram_link_codes`
- Web endpoint creates OTP code (6 digits, 10 min TTL)
- Telegram user confirms with `/link <code>`
- On success, backend binds `conversation.telegram_chat_id` to command sender chat

## Schema Changes

### conversations

- Add column: `web_owner_session_id TEXT`
- Add index: `idx_conversations_web_owner_session_id`

### web_sessions (new)

- `session_id TEXT PRIMARY KEY`
- `ua_hash TEXT`
- `ip_prefix TEXT`
- `created_at INTEGER`
- `last_seen_at INTEGER`
- `expires_at INTEGER`
- `rotated_to TEXT`
- `revoked_at INTEGER`

### telegram_link_codes (new)

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE`
- `web_owner_session_id TEXT`
- `code_hash TEXT`
- `expires_at INTEGER`
- `used_at INTEGER`
- `attempts INTEGER`
- `created_at INTEGER`

## API Contract Changes

### Conversations

- Auth changed from header token to cookie session
- `GET /api/conversations` now returns current session-owned conversations (all by default; optional `ids` filter)
- `POST /api/conversations` no longer returns conversation token

### Telegram link

- Added: `POST /api/conversations/{id}/telegram-link/request`
  - Response: `{ status, code, expires_in_seconds }`
- Removed direct link-by-chat-id flow from web
- Keep: `POST /api/conversations/{id}/unlink-telegram`

## Telegram Bot Changes

- New command: `/link <code>`
- New handler validates and consumes OTP
- On success, links Telegram chat to target conversation

## Frontend Changes

- All API calls include `credentials: "include"`
- Removed conversation token header plumbing
- Link flow changed to OTP request + instruction message for `/link <code>`

## Test Impact

Updated tests to new auth and linking model:

- Backend conversation route tests
- E2E lifecycle expectations
- Frontend hook integration tests for updated function signatures

Observed run after implementation:

- Backend focused suite: passed
- Frontend focused suite: passed

## Security Outcomes

Improved:

1. No browser-readable conversation auth token
2. Owner checks enforced server-side by session
3. OTP possession proof for Telegram linking
4. Session theft replay resistance improved (UA/IP bind + rotation)

Residual risks:

1. Anonymous session model is still not user-account identity
2. IP prefix binding may need tuning for highly mobile networks
3. OTP delivery is UI-driven (social engineering still possible if user shares code)

## Rollback Plan

1. Re-enable old token-based flow only if severe production breakage occurs
2. Keep DB migration additive; rollback can ignore new columns/tables without destructive change
3. Preserve unlink and Telegram message sync paths during rollback window

## Follow-ups

1. Add explicit retry/lockout policy for OTP attempts
2. Add admin observability endpoint for active session/link code metrics
3. Add optional device/session management UI
