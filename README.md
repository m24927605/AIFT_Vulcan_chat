# Web Search Chatbot

> **Live Demo**: [https://vulcanchat.xyz](https://vulcanchat.xyz)

A web search chatbot powered by a 2-Agent AI architecture that intelligently searches the web and provides answers with cited sources. Supports both web UI and Telegram bot with bidirectional message sync.

## Architecture

```
User → Next.js Frontend → FastAPI Backend ←→ Telegram Bot
                              │
                        Chat Service (Orchestrator)
                              │
                ┌─────────────┼─────────────┐
                │             │             │
          Planner Agent  Data Sources   Executor Agent
               │       ┌─────┼──────────┐       │
               │   Search   Fugle    Finnhub   │
               │   Service  Service  Service   │
               │   (Tavily)                    │
               └──────── LLM Client ────────┘
                     (primary + fallback)
                  OpenAI GPT-4o ↔ Anthropic Claude
                │
        Deterministic Pre-check
        (temporal keyword safety net)
```

### 2-Agent Design

- **Planner Agent**: Analyzes user queries to decide if web search is needed. Classifies queries as temporal, factual, or conversational, and generates optimized search keywords.
- **Executor Agent**: Synthesizes answers from search results (when available) or model knowledge. Generates responses with citation markers `[1]`, `[2]` and streams them via SSE.

### Search Reliability: Deterministic Pre-check

LLM-based planning is powerful but non-deterministic — the Planner may occasionally misjudge a time-sensitive query as not requiring search. To guarantee correctness for the assignment's core requirement (answering temporal questions like stock prices, news, exchange rates), a **rule-based safety net** sits after the Planner:

```
User Query → Planner Agent (LLM) → Deterministic Pre-check → Search / Direct Answer
```

The pre-check uses regex pattern matching on temporal keywords (e.g., `股價`, `新聞`, `匯率`, `latest`, `stock price`, `today`). It only activates when the Planner **incorrectly decides not to search** — it never overrides a correct "search" decision. This hybrid approach preserves the flexibility of LLM reasoning while ensuring 100% coverage of must-search scenarios.

### Key Features

- Real-time streaming responses (SSE)
- Intelligent search decision making
- Source citations with clickable references
- Agent thinking process visualization
- Multi-conversation management with persistence
- Bidirectional Web ↔ Telegram message sync with retry (exponential backoff); multiple conversations can link to the same Telegram chat
- Citation sources included in Telegram messages
- Onboarding tour for first-time users
- Responsive mobile design
- i18n support (English, 繁體中文)
- Dark mode
- LLM fallback: auto-switches to Anthropic on OpenAI timeout/429/5xx
- Structured logging with request ID tracing
- Rate limiting (IP-based, /api/chat)
- Enhanced health check with dependency status

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Backend | Python 3.11+, FastAPI, Pydantic |
| LLM | OpenAI GPT-4o (primary) + Anthropic Claude (fallback) |
| Search | Tavily API |
| Taiwan Stock Data | Fugle MarketData API |
| US/Global Stock Data | Finnhub API |
| Streaming | Server-Sent Events (SSE) |
| Database | SQLite (aiosqlite) |
| Telegram | python-telegram-bot |
| Testing | pytest (backend), Vitest (frontend), Playwright (browser E2E) |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- OpenAI API key
- Tavily API key (free tier: https://tavily.com)
- Anthropic API key (optional, for LLM fallback)
- Fugle MarketData API key (optional, for Taiwan stock data: https://developer.fugle.tw)
- Finnhub API key (optional, for US/global stock + forex data: https://finnhub.io)

### Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Create .env file
cp .env.example .env
# Edit .env and add your API keys

# Run dev server (web only)
uvicorn app.web.main:app --reload --port 8000

# Or run all modes (web + telegram)
MODE=all python -m app.entrypoint
```

### Frontend Setup

```bash
cd frontend
npm install

# Create .env.local
cp .env.example .env.local

# Run dev server
npm run dev
```

Open http://localhost:3000

### Using Makefile

```bash
make setup-backend    # Create venv and install deps
make setup-frontend   # Install npm deps
make run-backend      # Start FastAPI dev server
make run-frontend     # Start Next.js dev server
make test-backend     # Run backend tests
make test-frontend    # Run frontend tests
```

## API

### POST /api/chat

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
| `citations` | Source references |
| `done` | Stream complete |

### Conversations

Conversation endpoints use a server-managed `HttpOnly` session cookie (`vulcan_session`).
No per-conversation token is exposed to the frontend.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/conversations?ids=a,b` | Session cookie | List current session's conversations (all when `ids` omitted, filtered when provided) |
| POST | `/api/conversations` | Session cookie | Create a conversation owned by current session |
| GET | `/api/conversations/:id` | Session cookie | Get conversation details (owner-only) |
| DELETE | `/api/conversations/:id` | Session cookie | Delete conversation (owner-only) |
| GET | `/api/conversations/:id/messages` | Session cookie | Get messages (owner-only) |
| POST | `/api/conversations/:id/telegram-link/request` | Session cookie | Generate one-time link code for Telegram bot numeric keypad flow (`/start` -> `Start Linking`) or `/link <code>` |
| POST | `/api/conversations/:id/unlink-telegram` | Session cookie | Unlink Telegram chat ID (owner-only) |

### Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/notify` | Send notification via Telegram |
| POST | `/api/notify/broadcast` | Broadcast to all subscribers |

### GET /api/health

Health check endpoint with dependency status.

**Response:**
```json
{
  "status": "ok",
  "checks": { "database": "ok" },
  "uptime_seconds": 3600
}
```

## Testing

```bash
# Backend tests (184 tests: unit + integration + E2E, all mocked, no API keys needed)
make test-backend

# Frontend tests (17 tests: unit + integration)
make test-frontend

# Browser E2E tests (Playwright, requires dev server)
cd frontend && npm run test:e2e
```

### CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs automatically:

```
Push to main ──┬── Backend Tests (pytest, ≥90 test gate) ──┬── E2E Tests ──┬── Deploy Backend (Railway)
               │                                           │               │
               └── Frontend Tests (tsc + vitest + build) ──┘               └── Deploy Frontend (Vercel)
```

- **PR**: CI only (test + build, no deploy)
- **Push to main**: CI + CD (deploy after all tests pass)

**Required GitHub Secrets** for CD:

| Secret | Purpose |
|--------|---------|
| `RAILWAY_TOKEN` | Railway deploy token (`railway tokens create`) |
| `VERCEL_TOKEN` | Vercel deploy token (vercel.com → Settings → Tokens) |
| `VERCEL_ORG_ID` | From `frontend/.vercel/project.json` |
| `VERCEL_PROJECT_ID` | From `frontend/.vercel/project.json` |

## Environment Variables

### Backend (.env)

| Variable | Description | Required |
|----------|-----------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `OPENAI_MODEL` | Model name (default: gpt-4o) | No |
| `ANTHROPIC_API_KEY` | Anthropic API key (for fallback) | No |
| `ANTHROPIC_MODEL` | Anthropic model (default: claude-sonnet-4-20250514) | No |
| `PRIMARY_LLM` | Primary LLM provider: `openai` or `anthropic` (default: openai) | No |
| `FALLBACK_LLM` | Fallback LLM provider: `openai`, `anthropic`, or `""` to disable (default: anthropic) | No |
| `TAVILY_API_KEY` | Tavily search API key | Yes |
| `FUGLE_API_KEY` | Fugle MarketData API key (for TW stock data) | No |
| `FINNHUB_API_KEY` | Finnhub API key (for US/global stock + forex data) | No |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | For Telegram |
| `TELEGRAM_ADMIN_IDS` | Admin chat IDs (JSON array) | For Telegram |
| `MODE` | Run mode: `web`, `telegram`, or `all` | No |
| `DATA_DIR` | Directory for SQLite databases | No |
| `FRONTEND_URL` | Frontend URL for CORS | No |
| `API_SECRET_KEY` | Protects `/api/notify` endpoints and Telegram link-code hashing | For production |

### Frontend (.env.local)

| Variable | Description | Required |
|----------|-----------|---------|
| `BACKEND_URL` | Backend API URL (server-side only, used by Next.js rewrites) | No (defaults to `http://localhost:8000`) |

## Non-goals

These are explicitly out of scope for this project:

- **User authentication** — No login/signup system; ownership is anonymous session-cookie based (not account-based auth)
- **Search result ranking/re-ranking** — Results are used as-is from Tavily; no custom relevance scoring
- **Offline mode** — Both web search and LLM require active internet connection

## Trade-off Decisions

| Decision | Alternative | Why We Chose This |
|----------|------------|-------------------|
| SSE streaming | WebSocket | Simpler for unidirectional server→client flow; no need for mid-response client messages |
| SQLite | PostgreSQL | Zero-config, embedded, sufficient for demo scope; storage abstraction allows migration |
| Tavily | Google Custom Search | Generous free tier, simpler API, built-in content extraction |
| Session cookie (`HttpOnly`) | `localStorage` tokens | Prevents JS access to auth material and reduces XSS token theft risk |

## Known Limitations

| Area | Limitation | Mitigation | Priority | Exit Criteria |
|------|-----------|------------|----------|---------------|
| **Search source reliability** | Tavily results may include low-quality or outdated sources; the system does not verify factual accuracy | Fugle provides exchange-grade data for Taiwan stocks; Finnhub provides real-time data for US/global stocks and forex; Tavily `include_answer` provides a high-accuracy direct answer; Executor prompt enforces exact numerical quoting with per-source citations | P2 — partially mitigated | Add source credibility scoring; discard results below threshold |
| **Planner misjudgment** | LLM-based planning is non-deterministic — edge cases may lead to incorrect search/no-search decisions | Deterministic pre-check overrides missed temporal queries; Planner defaults to search on parse failure | P1 — partially mitigated | Achieve <1% miss rate on a 500-query evaluation set covering temporal, factual, and conversational queries |
| **LLM fallback coverage** | Fallback triggers on timeout, connection error, 429, and 5xx; 4xx client errors are not retried | Primary/fallback is configurable via `PRIMARY_LLM`/`FALLBACK_LLM` env vars | P3 — mitigated | Add health-check routing and circuit breaker for sustained outages |
| **SQLite scalability** | SQLite is single-writer; not suitable for high-concurrency production use | Sufficient for demo scope; storage abstraction allows migration | P2 | Migrate to PostgreSQL; verify ≥50 concurrent writers with no lock contention |
| **Conversation context window** | Full conversation history is sent to both agents; long conversations may exceed token limits | Not yet implemented | P2 | Add sliding window (last N messages) + conversation summarization for older context |
| **Telegram sync latency** | Web → Telegram push may fail on transient network errors | Retry with exponential backoff (3 attempts, 1s/2s/4s); failures logged with context | P3 — mitigated | Verify 99.9% delivery rate under normal conditions |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── agents/      # Planner + Executor agents
│   │   │   ├── services/    # Chat, LLM (OpenAI/Anthropic/Fallback), Search services
│   │   │   ├── models/      # Pydantic schemas & events
│   │   │   ├── config.py    # Pydantic settings (env-based)
│   │   │   ├── storage.py   # Conversation storage (SQLite)
│   │   │   └── exceptions.py
│   │   ├── web/
│   │   │   ├── main.py      # FastAPI app with CORS
│   │   │   └── routes/      # chat, conversations, notify, health
│   │   ├── telegram/
│   │   │   ├── bot.py       # Telegram bot setup
│   │   │   ├── handlers/    # Message handlers
│   │   │   ├── storage.py   # Subscription storage (SQLite)
│   │   │   ├── scheduler.py # Scheduled tasks
│   │   │   └── formatter.py # Message formatting
│   │   └── entrypoint.py    # Startup (web/telegram/all modes)
│   └── tests/               # pytest test suite
├── frontend/
│   ├── app/                 # Next.js app router
│   └── src/
│       ├── components/      # React components (incl. OnboardingTour)
│       ├── hooks/           # Custom hooks (useChat, useSSE)
│       ├── i18n/            # Translations (en, zh-TW)
│       └── lib/             # Types and utilities
├── docs/
│   ├── architecture.md      # Final architecture + E2E flow
│   ├── ops.md               # Operational runbook
│   ├── ai_usage.md          # AI tool usage + prompts
│   └── plans/               # Historical implementation plans
└── Makefile
```
