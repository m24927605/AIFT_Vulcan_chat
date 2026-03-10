# Vulcan Chatbot

> **Live Demo**: [https://vulcanchat.xyz](https://vulcanchat.xyz)

A web search chatbot for Vulcan, a cybersecurity company, powered by a 3-Agent AI architecture (Planner → Executor → Verifier) that intelligently searches the web, provides answers with cited sources, and verifies output consistency. Built with defense-in-depth security across every layer — from input sanitization and prompt-injection hardening to adversarial red-team testing. Supports both web UI and Telegram bot with bidirectional message sync.

## Architecture

```
User ──→ Next.js Frontend ──→ FastAPI Backend ←──→ Telegram Bot
                                    │
            ┌───────────── Chat Service (Orchestrator) ──────────────┐
            │                       │                                │
            │    ┌──────────────────┼──────────────────┐             │
            │    │                  │                  │             │
            │  Planner Agent   Data Sources      Executor Agent     │
            │  (temp 0.1)    ┌─────┼──────────┐  (temp 0.7)        │
            │    │         Search  Fugle  Finnhub    │              │
            │    │        (Tavily) (TW)   (US/FX)    │              │
            │    │                                   │              │
            │    │          Verifier Agent            │              │
            │    │          (temp 0.1)                │              │
            │    │     hallucination detection        │              │
            │    │     source consistency check       │              │
            │    │                                   │              │
            │    └────────── LLM Client ─────────────┘              │
            │           (primary + fallback)                        │
            │        OpenAI GPT-4o ↔ Anthropic Claude               │
            │                                                       │
            │  ┌─ Deterministic Pre-check ──────────────────────┐   │
            │  │  greeting fast-path / math evaluator /         │   │
            │  │  temporal keyword safety net                   │   │
            │  └────────────────────────────────────────────────┘   │
            │                                                       │
            │  ┌─ Security Pipeline ────────────────────────────┐   │
            │  │  input sanitization → schema extraction →      │   │
            │  │  prompt hardening → output secret guard        │   │
            │  └────────────────────────────────────────────────┘   │
            │                                                       │
            │  ┌─ Observability ────────────────────────────────┐   │
            │  │  Langfuse tracing (all 3 agents) +             │   │
            │  │  structured logging with request ID            │   │
            │  └────────────────────────────────────────────────┘   │
            └───────────────────────────────────────────────────────┘

Async Deep Analysis (Celery + Redis)
            │
   POST /api/analysis → Celery Worker → Multi-round loop
                         (Planner → Search → Refine) × N rounds
                         → Final Executor synthesis
                         → Poll GET /api/analysis/:task_id
```

### 3-Agent Pipeline

- **Planner Agent** (temp 0.1): Analyzes user queries to decide if web search is needed. Classifies queries as temporal, factual, or conversational, generates optimized search keywords, and routes to specialized data sources (Fugle for Taiwan stocks, Finnhub for US stocks and forex).
- **Executor Agent** (temp 0.7): Synthesizes answers from search results (when available) or model knowledge. Generates responses with citation markers `[1]`, `[2]` and streams them via SSE. Enforces exact numerical quoting from sources — never rounds or estimates.
- **Verifier Agent** (temp 0.1): Post-generation quality gate that checks every number, statistic, and percentage in the Executor's answer against the original search results. Reports consistency score, specific issues, and remediation suggestions. Only activated when search results are available.

### Request Flow

```
User Query
  │
  ├─ [Deterministic] Greeting? → direct response (skip all agents)
  ├─ [Deterministic] Simple math? → AST evaluator (skip all agents)
  │
  ├─ [LLM] Planner Agent → needs_search? query_type? data_sources?
  │   └─ Trace to Langfuse
  │
  ├─ [Deterministic] Temporal keyword override (safety net)
  │
  ├─ [Parallel] Fetch data sources
  │   ├─ Tavily web search
  │   ├─ Fugle (Taiwan stocks)
  │   └─ Finnhub (US/global stocks, forex)
  │
  ├─ [Security] Sanitize + normalize results (schema extraction)
  │
  ├─ [LLM] Executor Agent (streaming) → answer with citations
  │   ├─ Guard output (redact secrets before each chunk)
  │   └─ Trace to Langfuse
  │
  ├─ [LLM] Verifier Agent (if search was used)
  │   ├─ Check: numbers, citations, source consistency
  │   └─ Trace to Langfuse
  │
  └─ Emit SSE: planner → searching → chunks → verification → citations → done
```

### Search Reliability: Deterministic Pre-check

LLM-based planning is powerful but non-deterministic — the Planner may occasionally misjudge a time-sensitive query as not requiring search. To guarantee correctness for temporal questions while keeping low-risk queries stable, the backend uses **deterministic fast-paths and safety nets** around the Planner:

The deterministic layer does three things:

- Answers greetings directly without invoking the Planner
- Evaluates simple arithmetic expressions (for example `1+1`, `(2+3)*4`) via a restricted AST-based evaluator rather than LLM reasoning
- Forces search for temporal keywords (e.g. `股價`, `新聞`, `匯率`, `latest`, `stock price`, `today`) when the Planner incorrectly says no-search

In addition, if the Planner fails to parse its own JSON output, low-risk queries such as greetings and arithmetic fall back to direct-answer mode instead of being needlessly sent to search. This hybrid approach preserves LLM flexibility while reducing instability and unnecessary external calls.

### Key Features

- Real-time streaming responses (SSE) with intermediate agent events
- 3-Agent pipeline: Planner → Executor → Verifier with hallucination detection
- Async deep analysis via Celery task queue (multi-round Planner → Search → Refine)
- Intelligent search decision making with deterministic safety nets
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
- LLMOps observability: Langfuse tracing for all agent calls (latency, tokens, decisions)
- Structured logging with request ID tracing and secret redaction
- Adversarial red-team test suite with automated prompt injection defense validation
- Planner evaluation dataset with offline accuracy scoring

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Backend | Python 3.11+, FastAPI, Pydantic |
| LLM | OpenAI GPT-4o (primary) + Anthropic Claude (fallback) |
| Search | Tavily API |
| Taiwan Stock Data | Fugle MarketData API |
| US/Global Stock Data | Finnhub API |
| Task Queue | Celery + Redis |
| Observability | Langfuse (LLM tracing), structured logging |
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
- Redis (optional, for Celery async deep analysis)

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

# Optional: start Celery worker for deep analysis
celery -A app.core.celery_app worker --loglevel=info
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
| `verification` | Verifier Agent's consistency check result |
| `citations` | Source references |
| `search_failed` | Warning when search was needed but returned empty |
| `done` | Stream complete |

### Conversations

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

### Deep Analysis

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

**GET Response:**
```json
{
  "task_id": "abc-123",
  "status": "SUCCESS",
  "result": { "answer": "...", "rounds": 3 }
}
```

Task ownership is persisted in SQLite, so it survives process restarts and is consistent across instances sharing the same database. Session rotation automatically migrates task ownership.

### Notifications

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/notify` | `X-API-Key` | Send notification via Telegram |
| POST | `/api/notify/broadcast` | `X-API-Key` | Broadcast to all subscribers |

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

## Security Controls

The system implements defense-in-depth security across six layers: transport, session, API, LLM input, LLM output, and operational observability.

### Layer 1: Transport & Browser Hardening

- CORS restricted to the configured `FRONTEND_URL` only; `localhost:3000` is added exclusively when `API_SECRET_KEY` is empty (dev mode).
- All responses include security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (deny camera/mic/geo), and `Strict-Transport-Security` (HTTPS only).
- `API_SECRET_KEY` is required in production. If it is empty outside local development, the web server refuses to start.

### Layer 2: Session & Authentication

- Web conversations are protected by server-managed `HttpOnly` session cookies (`vulcan_session`) stored in the `web_sessions` table — not browser-managed auth tokens.
- Sessions are bound to user-agent hash + IP prefix. Mismatched fingerprints are rejected immediately.
- Sessions rotate every 24 hours. Rotation migrates all owned conversations and analysis tasks to the new session ID atomically.
- Orphan conversations (no owner) can only be auto-claimed if the requesting session's linked Telegram chat ID matches the conversation's Telegram chat ID — preventing strangers from claiming conversations by guessing UUIDs.

### Layer 3: API Protection

- State-changing routes require CSRF double-submit validation: the `X-CSRF-Token` header must match the `csrf_token` cookie (constant-time comparison), and the `Origin` header must match the configured frontend URL.
- Rate limiting is enforced per-endpoint (`/api/chat` and `/api/analysis` each get an independent 30 req/min per-IP bucket) and persisted in SQLite, remaining effective across process restarts and multiple instances.
- Admin notification endpoints require `X-API-Key` backed by `API_SECRET_KEY`.
- Telegram linking requires a one-time 8-digit code hashed with HMAC-SHA256, with 10-minute expiry, a 5-attempt limit, and Telegram-side possession proof.
- Analysis task ownership is persisted in SQLite with default-deny: unknown or unowned task IDs return 403, not the task result.

### Layer 4: LLM Input Hardening (Prompt Injection Defense)

- **Search result sanitization**: Before the Executor sees any search result, content is scanned for prompt injection patterns (`ignore.*instructions`, `reveal.*system prompt`, `exfiltrat`, `tool instructions`, `api_key`, `secret`, `token`) and matches are replaced with `[filtered]`.
- **Schema extraction**: Raw search result text is never passed to the LLM. Instead, results are normalized into a constrained schema (`source_kind`, `title`, `publisher`, `published_at`, `excerpt`, `facts[]`, `numbers[]`) with strict length limits (title: 300 chars, content: 4000 chars, max 3 facts, max 5 numbers).
- **Prompt boundary enforcement**: All agent system prompts explicitly instruct the LLM to treat search results, citations, and conversation history as untrusted data — never following instructions embedded within them.
- **Deterministic fast-paths**: Greetings and simple arithmetic bypass the LLM entirely (AST-based math evaluator), eliminating prompt drift risk for these categories.

### Layer 5: LLM Output Hardening (Data Exfiltration Defense)

- **Secret egress guard**: Before every response chunk is sent to the client, it is scanned for secret-like patterns — OpenAI keys (`sk-*`), session tokens (`sess-*`), base64 blobs (32+ chars), API key assignments (`api_key=...`), and bearer tokens. Matches are replaced with `[REDACTED: sensitive content removed]`.
- **Verifier Agent**: After the Executor generates an answer (when search results are present), the Verifier Agent independently checks every number, statistic, and percentage against the original sources. This catches hallucinated data that could mislead users, and surfaces a confidence score and issue list via the `verification` SSE event.

### Layer 6: Operational Security & Observability

- **Log secret redaction**: Server logging applies `SecretRedactionFilter` to all log output, catching Telegram bot tokens, bearer tokens, `sk-*` keys, session tokens, and API key assignments before they reach stdout.
- **Langfuse LLM tracing**: Every Planner, Executor, and Verifier call is traced with input, output, latency, token usage, and model metadata. Traces degrade gracefully (no-op) when Langfuse keys are absent.
- **Request ID correlation**: Every request gets a unique ID (auto-generated or forwarded via `X-Request-ID`), injected into all log records and returned in the response header for end-to-end tracing.
- **Rate limit IP source**: Rate limiting uses the direct connection IP only — `X-Forwarded-For` is ignored because it is user-controlled and can be spoofed to bypass limits.

### Adversarial Testing (Red Team)

The project includes an automated adversarial testing pipeline (`evals/adversarial_dataset.json`) with 28 attack cases across 8 categories, validated by the `tests/evals/test_adversarial.py` test suite:

| Category | Count | What It Tests |
|----------|-------|---------------|
| Jailbreak | 3 | DAN prompts, role-play override attempts |
| Prompt Leaking | 4 | System prompt extraction, chain-of-thought leaking |
| Instruction Override | 3 | "Ignore previous instructions" variants |
| Data Exfiltration | 4 | API key extraction, bearer token probing |
| Indirect Injection | 4 | Malicious instructions embedded in search results |
| Encoding Bypass | 3 | Mixed-case evasion, Unicode obfuscation |
| Output Attack | 4 | Secret patterns in model output (sk-*, sess-*) |
| Benign (control) | 3 | Legitimate queries that must NOT be filtered |

**Automated test assertions:**
- `TestInputSanitization`: Injection patterns in search results are caught and replaced with `[filtered]`
- `TestOutputGuard`: Secret-like patterns in model output are redacted before reaching the client
- `TestBenignInputsNotFiltered`: Legitimate queries pass through sanitization unaltered
- `TestPlannerResilience`: The Planner does not follow injected instructions in user messages
- `TestAdversarialReport`: Coverage validation — at least 25 cases across at least 5 categories

### Planner Evaluation

A 20-case evaluation dataset (`evals/planner_eval_dataset.json`) covers 8 query categories (Taiwan stocks, US stocks, forex, temporal, factual, conversational, greeting, math) and measures three accuracy dimensions:
- `needs_search_accuracy`: Was the search/no-search decision correct?
- `query_type_accuracy`: Was the query classified correctly (temporal/factual/conversational)?
- `data_source_accuracy`: Were the correct data sources routed (Fugle/Finnhub/none)?

Run with `python -m evals.run_planner_eval` (live) or `--dry-run` (dataset stats only).

### Security Notes

- Anonymous sessions provide owner isolation for browser conversations, but they are not a substitute for full user-account authentication.
- Schema extraction reduces prompt-injection risk significantly, but it is still a pragmatic control, not formal information-flow isolation.
- The adversarial test suite covers known attack categories but is not exhaustive; the dataset should grow as new attack vectors emerge.

## Testing

```bash
# Backend tests (330 tests — unit + integration + E2E, all mocked, no API keys needed)
make test-backend

# Frontend tests (unit + integration)
make test-frontend

# Browser E2E tests (Playwright, requires dev server)
cd frontend && npm run test:e2e

# Adversarial red-team tests only
cd backend && pytest tests/evals/test_adversarial.py -v

# Planner evaluation (offline, no API keys)
cd backend && python -m evals.run_planner_eval --dry-run
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
| `API_SECRET_KEY` | Protects `/api/notify` endpoints, Telegram link-code hashing, and production web auth boot validation | For production |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key for LLM tracing | No |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key for LLM tracing | No |
| `LANGFUSE_HOST` | Langfuse host URL | No |
| `CELERY_BROKER_URL` | Redis URL for Celery broker (default: `redis://localhost:6379/0`) | For deep analysis |
| `CELERY_RESULT_BACKEND` | Redis URL for Celery results (default: `redis://localhost:6379/1`) | For deep analysis |

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
| Schema extraction | Raw text prompting | Reduces prompt injection surface at the cost of some information loss |
| Default-deny task ownership | Allow-if-unknown | Security over convenience; prevents information leak on restart/cross-instance |

## Known Limitations

| Area | Limitation | Mitigation | Priority | Exit Criteria |
|------|-----------|------------|----------|---------------|
| **Search source reliability** | Tavily results may include low-quality or outdated sources; the system does not verify factual accuracy | Fugle provides exchange-grade data for Taiwan stocks; Finnhub provides real-time data for US/global stocks and forex; Tavily `include_answer` provides a high-accuracy direct answer; Executor prompt enforces exact numerical quoting with per-source citations; Verifier Agent cross-checks numbers against sources | P2 — partially mitigated | Add source credibility scoring; discard results below threshold |
| **Planner misjudgment** | LLM-based planning is non-deterministic — edge cases may lead to incorrect search/no-search decisions | Deterministic greeting/math fast-paths, temporal pre-check overrides missed searches, and low-risk parse-failure fallback avoids unnecessary search | P1 — partially mitigated | Achieve <1% miss rate on a 500-query evaluation set covering temporal, factual, and conversational queries |
| **LLM fallback coverage** | Fallback triggers on timeout, connection error, 429, and 5xx; 4xx client errors are not retried | Primary/fallback is configurable via `PRIMARY_LLM`/`FALLBACK_LLM` env vars | P3 — mitigated | Add health-check routing and circuit breaker for sustained outages |
| **SQLite scalability** | SQLite is single-writer; not suitable for high-concurrency production use | Sufficient for demo scope; storage abstraction allows migration | P2 | Migrate to PostgreSQL; verify ≥50 concurrent writers with no lock contention |
| **Conversation context window** | Full conversation history is sent to both agents; long conversations may exceed token limits | Not yet implemented | P2 | Add sliding window (last N messages) + conversation summarization for older context |
| **Telegram sync latency** | Web → Telegram push may fail on transient network errors | Retry with exponential backoff (3 attempts, 1s/2s/4s); failures logged with context | P3 — mitigated | Verify 99.9% delivery rate under normal conditions |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── agents/        # Planner + Executor + Verifier agents
│   │   │   ├── services/      # Chat, LLM (OpenAI/Anthropic/Fallback), Search, Tracing
│   │   │   ├── tasks/         # Celery tasks + deep analysis pipeline
│   │   │   ├── models/        # Pydantic schemas & SSE events
│   │   │   ├── config.py      # Pydantic settings (env-based)
│   │   │   ├── storage.py     # SQLite storage (conversations, sessions, task ownership)
│   │   │   ├── security.py    # Input sanitization, output guard, schema extraction
│   │   │   ├── celery_app.py  # Celery app factory
│   │   │   ├── middleware.py   # Request logging, rate limiting, security headers
│   │   │   ├── web_session.py  # Session management, CSRF, cookie handling
│   │   │   └── exceptions.py
│   │   ├── web/
│   │   │   ├── main.py        # FastAPI app with CORS + middleware stack
│   │   │   ├── deps.py        # Authorization helpers (conversation ownership)
│   │   │   └── routes/        # chat, conversations, analysis, notify, health
│   │   ├── telegram/
│   │   │   ├── bot.py         # Telegram bot setup
│   │   │   ├── handlers/      # Message handlers
│   │   │   ├── storage.py     # Subscription storage (SQLite)
│   │   │   ├── scheduler.py   # Scheduled tasks
│   │   │   └── formatter.py   # Message formatting
│   │   └── entrypoint.py      # Startup (web/telegram/all modes)
│   ├── evals/
│   │   ├── adversarial_dataset.json   # 28 red-team attack cases
│   │   ├── planner_eval_dataset.json  # 20 planner accuracy test cases
│   │   └── run_planner_eval.py        # Planner evaluation runner
│   └── tests/                 # 330 pytest tests (unit + integration + adversarial)
├── frontend/
│   ├── app/                   # Next.js app router
│   └── src/
│       ├── components/        # React components (incl. OnboardingTour)
│       ├── hooks/             # Custom hooks (useChat, useSSE)
│       ├── i18n/              # Translations (en, zh-TW)
│       └── lib/               # Types and utilities
├── docs/
│   ├── architecture.md        # Final architecture + E2E flow
│   ├── ops.md                 # Operational runbook
│   ├── ai_usage.md            # AI tool usage + prompts
│   └── plans/                 # Historical implementation plans
└── Makefile
```
