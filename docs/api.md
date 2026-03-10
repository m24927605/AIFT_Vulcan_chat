# API Reference

## POST /api/chat

Send a chat message and receive a streaming SSE response.

**Request:**
```json
{
  "message": "What is TSMC stock price today?",
  "conversation_id": "optional-uuid",
  "history": []
}
```

**SSE Events:**

| Event | Description |
|-------|-----------|
| `planner` | Planner Agent's decision (search/no-search, reasoning) |
| `searching` | Search progress for each query |
| `chunk` | Answer text chunk (streaming) |
| `verification` | Verifier Agent's consistency check result |
| `citations` | Source references |
| `search_failed` | Warning when search was needed but returned empty |
| `done` | Stream complete |

## Conversations

Conversation endpoints use a server-managed `HttpOnly` session cookie (`vulcan_session`).
No per-conversation token is exposed to the frontend.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/conversations?ids=a,b` | Session cookie | List current session's conversations (all when `ids` omitted, filtered when provided) |
| POST | `/api/conversations` | Session cookie + CSRF | Create a conversation owned by current session |
| GET | `/api/conversations/:id` | Session cookie | Get conversation details (owner-only) |
| DELETE | `/api/conversations/:id` | Session cookie + CSRF | Delete conversation (owner-only) |
| GET | `/api/conversations/:id/messages` | Session cookie | Get messages (owner-only) |
| POST | `/api/conversations/:id/telegram-link/request` | Session cookie + CSRF | Generate one-time link code for Telegram bot numeric keypad flow (`/start` -> `Start Linking`) or `/link <code>` |
| POST | `/api/conversations/:id/unlink-telegram` | Session cookie + CSRF | Unlink Telegram chat ID (owner-only) |

## Deep Analysis

Asynchronous multi-round analysis powered by Celery task queue. The worker iterates a Planner → Search → Refine loop (up to 5 rounds), then synthesizes a comprehensive answer from all accumulated search results. Tasks are session-owned: only the session that submitted a task can query its result.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/analysis` | Session cookie + CSRF | Submit a deep analysis task (returns `task_id`, HTTP 202) |
| GET | `/api/analysis/:task_id` | Session cookie | Poll task status (owner-only; unknown/unowned tasks return 403) |

**POST Request:**
```json
{
  "query": "Analyze TSMC revenue trends for 2025",
  "max_rounds": 3
}
```

**POST Response (202):**
```json
{
  "task_id": "abc-123",
  "status": "pending"
}
```

**GET Response (success):**
```json
{
  "task_id": "abc-123",
  "status": "SUCCESS",
  "result": {
    "answer": "...",
    "rounds": 3,
    "verification": {
      "is_consistent": true,
      "confidence": 0.95,
      "issues": [],
      "suggestion": null
    }
  }
}
```

**GET Response (refused — search required but returned empty):**
```json
{
  "task_id": "abc-123",
  "status": "SUCCESS",
  "result": {
    "status": "refused",
    "answer": "目前無法取得經過驗證的最新資訊，請稍後再試。",
    "rounds": 2
  }
}
```

Task ownership is persisted in SQLite, so it survives process restarts and is consistent across instances sharing the same database. Session rotation automatically migrates task ownership.

## Notifications

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/notify` | `X-API-Key` | Send notification via Telegram |
| POST | `/api/notify/broadcast` | `X-API-Key` | Broadcast to subscribers (target must be `subscribers`) |

## GET /api/health

Health check endpoint with dependency status.

**Response:**
```json
{
  "status": "ok",
  "checks": { "database": "ok" },
  "uptime_seconds": 3600
}
```
