# Telegram Bot Integration Design

## Overview

Add Telegram bot support to Vulcan, enabling users to interact with the web search chatbot via Telegram with full functionality (planner reasoning, search status, streaming answers, citations) plus scheduled digest notifications and API-triggered broadcasts.

## Requirements

- **Full chat experience** in Telegram: planner thinking, search status, streamed answer, citation links
- **Scheduled digests**: users subscribe via `/subscribe` command, bot sends periodic topic summaries
- **API-triggered notifications**: push messages to specific users or broadcast via REST API
- **Public access**: any Telegram user can interact; rate-limited at 20 messages/minute/user
- **Data persistence**: SQLite for subscription storage

## Architecture: Core + Gateway

Refactor the backend into three layers:

```
Frontend ──→ Web Gateway (FastAPI routes) ──→ Core (shared logic)
Telegram ──→ Bot Gateway (python-telegram-bot) ──→ Core (shared logic)
```

### Core Layer

Extracts shared business logic from the current backend. The key change is that `ChatService.process_message()` yields **structured Python event objects** instead of SSE-formatted strings, allowing each gateway to format output for its platform.

### Web Gateway

Wraps Core events into SSE format for the frontend. Preserves existing API behavior. Adds new `/api/notify` endpoints for push notifications.

### Telegram Gateway

Consumes Core events and renders them as Telegram messages. Manages bot commands, rate limiting, and scheduled digests.

## Directory Structure

```
backend/
├── app/
│   ├── core/                       # Shared core logic
│   │   ├── agents/
│   │   │   ├── planner.py          # PlannerAgent
│   │   │   └── executor.py         # ExecutorAgent
│   │   ├── services/
│   │   │   ├── chat_service.py     # ChatService (yields ChatEvent objects)
│   │   │   ├── openai_client.py    # OpenAI client
│   │   │   └── search_service.py   # Tavily search client
│   │   ├── models/
│   │   │   ├── schemas.py          # Shared Pydantic models
│   │   │   └── events.py           # ChatEvent dataclasses
│   │   ├── config.py               # Shared configuration
│   │   └── exceptions.py           # Shared exceptions
│   │
│   ├── web/                        # Web Gateway
│   │   ├── main.py                 # FastAPI app factory
│   │   └── routes/
│   │       ├── chat.py             # POST /api/chat (SSE)
│   │       ├── health.py           # GET /api/health
│   │       └── notify.py           # POST /api/notify, POST /api/notify/broadcast
│   │
│   ├── telegram/                   # Telegram Gateway
│   │   ├── bot.py                  # Bot init + command registration
│   │   ├── handlers/
│   │   │   ├── chat.py             # Message handler (calls core ChatService)
│   │   │   ├── subscribe.py        # /subscribe, /unsubscribe, /list commands
│   │   │   └── admin.py            # /stats (admin only)
│   │   ├── formatter.py            # Core events → Telegram MarkdownV2
│   │   ├── rate_limiter.py         # Sliding window rate limiter
│   │   └── scheduler.py            # APScheduler for digest delivery
│   │
│   └── entrypoint.py               # Unified entrypoint (MODE=web|telegram|all)
│
├── tests/
│   ├── core/                       # Core logic tests (migrated)
│   ├── web/                        # Web API tests
│   └── telegram/                   # Telegram bot tests
│
├── pyproject.toml
└── Dockerfile
```

## Core Event Model

```python
@dataclass
class PlannerEvent:
    needs_search: bool
    reasoning: str
    search_queries: list[str]
    query_type: str

@dataclass
class SearchingEvent:
    query: str
    status: str  # "searching" | "done"
    results_count: int | None = None

@dataclass
class ChunkEvent:
    content: str

@dataclass
class CitationsEvent:
    citations: list[dict]

@dataclass
class DoneEvent:
    pass

ChatEvent = PlannerEvent | SearchingEvent | ChunkEvent | CitationsEvent | DoneEvent
```

`ChatService.process_message()` yields `ChatEvent` objects. Each gateway converts them to its platform format.

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + usage guide |
| `/help` | List available commands |
| `/subscribe <topic> <frequency> <time>` | Subscribe to digest (e.g., `/subscribe 科技新聞 daily 09:00`) |
| `/unsubscribe <topic>` | Unsubscribe from a topic |
| `/list` | List current subscriptions |
| `/stats` | (Admin) View bot usage statistics |

Any non-command message enters chat mode automatically.

## Telegram Chat Flow

1. User sends a message
2. Bot replies with a status message ("Thinking...")
3. Planner decides → update status ("Needs search: ...")
4. Search in progress → update status ("Searching: query...")
5. Streaming completes → replace status message with final formatted answer
6. If citations exist, append clickable source links below the answer

**Message update strategy:**
- Use `edit_message_text` to update a single message (avoids flooding)
- Buffer streaming text: update every **30 characters or 2 seconds**
- Final answer formatted in Telegram MarkdownV2

## Rate Limiting

- **20 messages per minute** per user
- Sliding window algorithm, in-memory dict
- Exceeding limit returns a cooldown notice
- No Redis needed at current scale

## Subscription & Scheduled Digests

### Storage: SQLite + aiosqlite

```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id BIGINT NOT NULL,
    topic TEXT NOT NULL,
    frequency TEXT NOT NULL,  -- "daily" | "weekly"
    time TEXT NOT NULL,       -- "09:00"
    timezone TEXT NOT NULL DEFAULT 'Asia/Taipei',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, topic)
);
```

### Scheduler

Uses APScheduler (`AsyncIOScheduler`) to run subscription jobs. On trigger:

1. Build a prompt: "Search and summarize today's key news about {topic}"
2. Run through `ChatService.process_message()`
3. Collect full response
4. Send formatted message to subscriber's `chat_id`

## Notification API (Web Gateway)

### Push to specific user

```
POST /api/notify
{
    "chat_id": 123456789,
    "message": "Your report is ready",
    "parse_mode": "MarkdownV2"   // optional
}
```

### Broadcast

```
POST /api/notify/broadcast
{
    "message": "System maintenance notice...",
    "target": "all" | "subscribers"
}
```

## Deployment

### Dockerfile

Single Dockerfile, mode selected by `MODE` environment variable:

- `MODE=web` — Start FastAPI server (default)
- `MODE=telegram` — Start Telegram bot polling
- `MODE=all` — Run both in the same process/event loop

### New Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes (for telegram mode) | Token from @BotFather |
| `TELEGRAM_ADMIN_IDS` | No | Comma-separated admin chat IDs |
| `MODE` | No | Startup mode: `web`, `telegram`, or `all` (default: `web`) |

### Makefile additions

```makefile
run-telegram:    # Start Telegram bot locally
run-all:         # Start web + telegram locally
test-telegram:   # Run telegram tests
```

## Dependencies (new)

- `python-telegram-bot[ext]` — Telegram Bot API wrapper with async support
- `apscheduler` — Async job scheduling for digests
- `aiosqlite` — Async SQLite driver for subscription persistence

## Testing Strategy

- **Core tests**: Migrate existing tests, verify behavior unchanged after refactor
- **Telegram handler tests**: Mock `Update`/`Context` using python-telegram-bot test utilities
- **Integration tests**: Verify Core → Telegram formatter full pipeline
- All external APIs (OpenAI, Tavily, Telegram) fully mocked
