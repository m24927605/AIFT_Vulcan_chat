# Architecture Overview

## System Diagram

```
┌─────────────┐     POST /api/chat      ┌──────────────────────────────────────┐
│             │ ──────────────────────── │            FastAPI Backend           │
│  Next.js    │                          │                                      │
│  Frontend   │     SSE stream           │  ┌──────────────────────────────┐   │
│             │ ◀──────────────────────  │  │     Chat Service             │   │
│  - React 19 │                          │  │     (Orchestrator)           │   │
│  - Tailwind │     GET /api/conv/:id    │  │                              │   │
│  - SSE      │ ──────────────────────── │  │  1. Deterministic Fast-path   │   │
│             │                          │  │     ↓ greeting / simple math │   │
└─────────────┘                          │  │  2. Planner Agent             │   │
                                         │  │     ↓ PlannerDecision        │   │
┌─────────────┐                          │  │  3. Deterministic Pre-check  │   │
│  Telegram   │   python-telegram-bot    │  │     ↓ override if temporal   │   │
│  Bot        │ ◀──────────────────────▶ │  │  4. Search Service (Tavily)  │   │
│             │                          │  │     ↓ SearchResult[]        │   │
│             │                          │  │  4b. Fugle Service (TW stk) │   │
│             │                          │  │     ↓ FugleQuote            │   │
│             │                          │  │  4c. Finnhub Service (US+)  │   │
│             │                          │  │     ↓ FinnhubSource         │   │
│             │                          │  │  5. Security Normalizer      │   │
│             │                          │  │     ↓ NormalizedSearchResult│   │
│             │                          │  │  6. Executor Agent           │   │
│             │                          │  │     ↓ SSE stream            │   │
└─────────────┘                          │  │                              │   │
                                         │  │  LLMClient (primary+fallback)│   │
                                         │  │  OpenAI GPT-4o ↔ Anthropic  │   │
                                         │  └──────────────────────────────┘   │
       ↕ bidirectional sync              │                                      │
┌─────────────┐                          │  SQLite: conversations + messages    │
│  Telegram   │                          └──────────────────────────────────────┘
│  User       │
└─────────────┘
```

## End-to-End Flow

A user asks **"台積電今天股價多少？"** (What is TSMC's stock price today?):

| Step | Component | Action |
|------|-----------|--------|
| 1 | **Frontend** | User types message → `POST /api/chat` with `{ message, conversation_id }` |
| 2 | **Planner Agent** | Analyzes query → `{ needs_search: true, query_type: "temporal", search_queries: ["TSMC stock price today", "台積電 股價"] }` |
| 3 | **Deterministic Pre-check** | Confirms: "股價" matches temporal pattern → no override needed (Planner already correct) |
| 4 | **Search Service** | Executes 2 Tavily queries in parallel → returns 8 deduplicated results |
| 5 | **Security Normalizer** | Sanitizes external results, extracts constrained schema fields (`excerpt`, `facts`, `numbers`, metadata), and strips prompt-injection patterns before LLM synthesis |
| 6 | **Executor Agent** | Synthesizes answer from normalized results → streams tokens via SSE with `[1]`, `[2]` citation markers |
| 7 | **Frontend** | Renders streaming text + planner thinking + search progress + citation cards |

For low-risk inputs, the flow is shorter:

- Greetings are answered by a deterministic fast-path without invoking the Planner.
- Simple arithmetic is evaluated by a restricted AST-based evaluator without invoking search or LLM planning.
- If planner JSON parsing fails for a low-risk query, the backend falls back to direct-answer mode instead of forcing web search.

If the conversation is linked to Telegram, the backend also pushes the complete response (with formatted citations) to the linked Telegram chat. Multiple web conversations can link to the same Telegram chat — messages from Telegram are synced to all linked conversations.

## Real Request/Response Example

**Request:**
```json
POST /api/chat
{
  "message": "台積電今天股價多少？",
  "conversation_id": "a1b2c3d4-...",
  "history": []
}
```

**SSE Response Stream:**
```
event: planner
data: {"needs_search":true,"reasoning":"This is a temporal question about current stock price","search_queries":["TSMC stock price today","台積電 股價"],"query_type":"temporal"}

event: searching
data: {"query":"TSMC stock price today","status":"searching"}

event: searching
data: {"query":"台積電 股價","status":"searching"}

event: searching
data: {"query":"TSMC stock price today","status":"done","results_count":5}

event: searching
data: {"query":"台積電 股價","status":"done","results_count":5}

event: chunk
data: {"content":"根據最新資料，"}

event: chunk
data: {"content":"台積電（TSMC, 2330.TW）"}

event: chunk
data: {"content":"今日股價約為 **XXX 元新台幣** [1]。"}

event: citations
data: {"citations":[{"index":1,"title":"台積電(2330) 即時股價","url":"https://example.com/tsmc","snippet":"台積電即時報價..."},{"index":2,"title":"TSMC Stock","url":"https://example.com/tsmc-en","snippet":"TSMC (TSM) stock..."}]}

event: done
data: {}
```

## LLM Client Abstraction

Both agents use an `LLMClient` protocol for dependency injection, enabling provider-agnostic operation and automatic failover:

```
LLMClient (Protocol)
├── OpenAIClient      → OpenAI GPT-4o
├── AnthropicClient   → Anthropic Claude
└── FallbackLLMClient → wraps primary + fallback
```

- **`LLMClient`** (`llm_client.py`): Protocol defining `chat()`, `chat_stream()`, and `provider_name`.
- **`FallbackLLMClient`** (`fallback_client.py`): Wraps a primary and fallback client. On timeout, connection error, HTTP 429, or 5xx from the primary, automatically retries with the fallback. Client errors (4xx, non-429) are re-raised without fallback.
- **`llm_factory.py`**: Reads `PRIMARY_LLM` and `FALLBACK_LLM` from config to construct the appropriate client chain.

## Key Design Decisions

| Decision | Alternative Considered | Rationale |
|----------|----------------------|-----------|
| SSE over WebSocket | WebSocket (bidirectional) | SSE is simpler for server→client streaming; we don't need client→server streaming mid-response |
| SQLite over PostgreSQL | PostgreSQL (scalable) | Zero-config, embedded, sufficient for demo; storage abstraction allows future migration |
| Tavily over Google Search API | Google Custom Search ($5/1000 queries) | Tavily has generous free tier, simpler API, built-in content extraction |
| Session cookie + session table | `localStorage` conversation tokens | `HttpOnly` cookie keeps auth material out of browser JS; server enforces owner checks |
| One-to-many Telegram sync | One-to-one (UNIQUE) | Multiple conversations can link to the same Telegram chat; messages sync to all linked conversations across browsers |
| Anonymous web sessions (`web_sessions`) | No per-conversation auth | Owner-bound access control without login/signup; includes UA/IP binding + periodic rotation |
| CSRF token + `Origin` verification | Cookie session without CSRF | Prevents cross-site state-changing requests in cross-origin deployment |
| Security headers middleware | No browser hardening headers | Adds `HSTS`, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, and `Permissions-Policy` |
| Schema extraction before Executor | Pass raw search text directly to LLM | Reduces prompt-injection surface while preserving useful facts, numbers, and source metadata |
| Secret-egress output guard | Trust raw model output | Redacts secret-like values before streaming them back to users |
| Secret-redacted logging | Raw exception strings in logs | Reduces the chance of Telegram/API credential leakage through server logs |
| Deterministic greeting / math fast-path | Send all low-risk queries through LLM planner | Improves stability for simple inputs and reduces unnecessary search/LLM surface area |
| Telegram OTP linking (`telegram_link_codes`) | Direct `link-telegram` by chat ID | Prevents accidental/malicious mis-linking by requiring Telegram-side possession proof (`/start` -> `Start Linking` numeric keypad or `/link <code>`) |
| 3-Agent (Planner+Executor+Verifier) over single agent | Single LLM call with tools | Separation of concerns: Planner optimizes search decision, Executor optimizes answer quality, Verifier checks hallucination/consistency |
| Deterministic pre-check | Trust LLM fully | Safety net for must-search temporal queries; hybrid approach preserves flexibility |
| Request ID tracing | No tracing | Every request gets a unique ID propagated through all log messages for debugging |
| Storage-backed IP rate limiting | In-memory limiter only | Protects `/api/chat` from abuse with shared SQLite-backed enforcement across compatible app instances |
| Telegram retry with backoff | Fire-and-forget | 3 attempts with exponential backoff (1s, 2s between attempts) for transient network failures |
| LLM fallback (OpenAI→Anthropic) | Single provider | Eliminates single-point-of-failure; auto-switches on timeout/429/5xx |
| Tavily `include_answer` | Raw results only | Tavily's AI-generated answer is injected as result `[1]`, improving numerical accuracy for temporal queries (stock prices, exchange rates) |
| Executor strict quoting prompt | Generic "be accurate" | Numbers must be quoted exactly as they appear in search results; prevents LLM from rounding, averaging, or hallucinating figures |
| Fugle for TW stocks | Tavily only | Exchange-grade data for Taiwan stocks; Tavily supplements with news/analysis |
| Finnhub API | Alpha Vantage, Yahoo Finance | Free tier with 60 calls/min, comprehensive endpoints (quote, candles, forex, financials, news, earnings, price target, recommendation, insider), official Python SDK |
