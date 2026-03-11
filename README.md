# Vulcan Chatbot

> **Live Demo**: [https://vulcanchat.xyz](https://vulcanchat.xyz)
> **Slides**: [https://vulcanchat.xyz/slides](https://vulcanchat.xyz/slides)

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

- **Planner Agent** (temp 0.1): Analyzes user queries to decide if web search is needed. Classifies queries as temporal, factual, or conversational, generates optimized search keywords, and routes to specialized data sources (Fugle for Taiwan stocks, Finnhub for US stocks, tw.rter.info for forex).
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
  │   ├─ Finnhub (US/global stocks)
  │   └─ tw.rter.info (forex/exchange rates)
  │
  ├─ [Security] Sanitize → filter AI summaries → normalize (schema extraction)
  │
  ├─ [Gate] Refusal check: if search needed but no results → localized refusal, stop
  │
  ├─ [LLM] Executor Agent (streaming) → answer with citations
  │   ├─ guard_model_output on every chunk (redact secrets)
  │   └─ Trace to Langfuse
  │
  ├─ [LLM] Verifier Agent (if search was used)
  │   ├─ Check: numbers, citations, source consistency
  │   └─ Trace to Langfuse
  │
  └─ Emit SSE: planner → searching → [search_failed?] → chunks → verification → citations → done
```

> See [docs/architecture.md](docs/architecture.md) for end-to-end flow details, real request/response examples, LLM client abstraction, and design decisions.

## Security Highlights

Defense-in-depth across 6 layers — the full breakdown is in [docs/security.md](docs/security.md).

| Layer | Key Controls |
|-------|-------------|
| **LLM Input** | Prompt injection pattern scanning + schema extraction (raw text never reaches LLM) + prompt boundary enforcement |
| **LLM Output** | Secret egress guard (redacts `sk-*`, `sess-*`, bearer tokens before streaming) + Verifier Agent cross-checks numbers against sources. Shared `secure_answer_pipeline` ensures chat and deep analysis apply identical security controls |
| **Adversarial Testing** | 28-case red-team suite across 8 attack categories (jailbreak, prompt leaking, data exfiltration, indirect injection, encoding bypass) with automated CI validation |
| **Transport** | CORS lockdown, HSTS, security headers, production `API_SECRET_KEY` enforcement |
| **Session** | `HttpOnly` cookies, UA/IP binding, 24h rotation, CSRF double-submit |
| **Operational** | Log secret redaction, Langfuse tracing, request ID correlation |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Backend | Python 3.11+, FastAPI, Pydantic |
| LLM | OpenAI GPT-4o (primary) + Anthropic Claude (fallback) |
| Search | Tavily API |
| Taiwan Stock Data | Fugle MarketData API |
| US/Global Stock Data | Finnhub API |
| Forex / Exchange Rates | tw.rter.info API |
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
- Finnhub API key (optional, for US/global stock data: https://finnhub.io)
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
make test-backend     # Run 361 backend tests
make test-frontend    # Run frontend tests
```

### Using Docker Compose

Docker Compose supports two modes: **development** (hot reload) and **production-like** (built artifacts).

**Prerequisites:**

```bash
cp frontend/.env.example frontend/.env
cp backend/.env.example backend/.env
# Edit both .env files with your API keys
```

**Development mode** (default — auto-loads override file, supports hot reload):

```bash
docker compose up --build                # frontend + backend + redis
docker compose --profile worker up --build  # also start Celery worker
docker compose up -d                     # run in background
docker compose logs -f backend           # follow logs
```

**Production-like mode** (builds images, runs production artifacts):

```bash
docker compose -f docker-compose.yml up --build
docker compose -f docker-compose.yml --profile worker up --build
```

**Common operations:**

```bash
docker compose down                      # stop all services
docker compose down -v                   # stop and delete all data (SQLite, Redis)
docker compose up --build backend        # rebuild a single service
docker compose restart worker            # restart worker after code change
```

| Service | URL | Description |
|---------|-----|-------------|
| frontend | http://localhost:3000 | Next.js web UI |
| backend | http://localhost:8000 | FastAPI API server |
| redis | localhost:6379 | Celery message broker |
| worker | — | Celery worker (requires `--profile worker`) |

> **Note:** In development mode, frontend and backend code changes auto-reload. Celery worker requires manual restart (`docker compose restart worker`) after code changes. Switching between dev and production-like modes requires `--build` to rebuild the frontend image (they use different build targets).

## Testing

```bash
make test-backend              # 361 tests (unit + integration + adversarial)
make test-frontend             # Frontend unit + integration tests
cd frontend && npm run test:e2e  # Browser E2E (Playwright)
```

> See [docs/testing.md](docs/testing.md) for CI/CD pipeline details and GitHub Secrets configuration.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── agents/        # Planner + Executor + Verifier agents
│   │   │   ├── pipelines/     # Shared secure answer pipeline (refusal gate, output guard, verification)
│   │   │   ├── services/      # Chat, LLM (OpenAI/Anthropic/Fallback), Search, Tracing
│   │   │   ├── tasks/         # Celery tasks + deep analysis pipeline
│   │   │   ├── models/        # Pydantic schemas & SSE events
│   │   │   ├── security.py    # Input sanitization, output guard, schema extraction, result pre-filtering
│   │   │   └── ...            # config, storage, middleware, web_session
│   │   ├── web/               # FastAPI app, routes, auth
│   │   └── telegram/          # Telegram bot, handlers, sync
│   ├── evals/
│   │   ├── adversarial_dataset.json   # 28 red-team attack cases
│   │   ├── planner_eval_dataset.json  # 20 planner accuracy test cases
│   │   └── run_planner_eval.py        # Planner evaluation runner
│   └── tests/                 # 361 pytest tests
├── frontend/
│   ├── app/                   # Next.js app router
│   └── src/                   # Components, hooks, i18n, lib
├── docs/
│   ├── architecture.md        # System design, E2E flow, design decisions
│   ├── security.md            # 6-layer security controls + adversarial testing
│   ├── api.md                 # API reference (all endpoints)
│   ├── testing.md             # Test strategy + CI/CD pipeline
│   ├── configuration.md       # Environment variables
│   ├── ops.md                 # Operational runbook
│   ├── ai_usage.md            # AI tool usage + prompts
│   └── plans/                 # Historical implementation plans
└── Makefile
```

> **Full documentation:** [docs/api.md](docs/api.md) · [docs/security.md](docs/security.md) · [docs/architecture.md](docs/architecture.md) · [docs/configuration.md](docs/configuration.md) · [docs/testing.md](docs/testing.md) · [docs/ops.md](docs/ops.md)
