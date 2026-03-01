# Web Search Chatbot - Design Document

## Overview

A web search chatbot using a 2-Agent architecture (Planner + Executor) for the Vulcan Senior SWE Assignment B. The system intelligently decides when to search the web, executes searches via Tavily, and generates streaming responses with cited sources.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS |
| Backend | Python 3.11+, FastAPI, Pydantic |
| LLM | OpenAI GPT-4o |
| Search | Tavily API |
| Streaming | Server-Sent Events (SSE) |
| Testing | pytest (backend), Vitest + RTL (frontend) |
| Deployment | Vercel (frontend) + Railway/Render (backend) |

## Architecture

```
User → Frontend (Next.js) → POST /api/chat → Backend (FastAPI)
                                                    │
                                              Chat Service
                                             (Orchestrator)
                                                    │
                                    ┌───────────────┼───────────────┐
                                    │               │               │
                              Planner Agent   Search Service   Executor Agent
                              (GPT-4o)        (Tavily API)     (GPT-4o)
                                    │               │               │
                                    └───────────────┼───────────────┘
                                                    │
                                          SSE Stream Response
                                                    │
                                                 Frontend
```

### Data Flow

1. User sends message via frontend
2. Backend receives POST /api/chat
3. **Planner Agent** analyzes query:
   - Determines if web search is needed
   - Classifies query type (temporal / factual / conversational)
   - Generates optimized search queries (up to 3)
4. If search needed: **Search Service** executes Tavily queries
5. **Executor Agent** synthesizes answer:
   - Incorporates search results (if any)
   - Generates response with citation markers [1], [2], etc.
   - Streams tokens via SSE
6. Frontend renders streaming response with citations

## Backend Design

### Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, CORS, lifespan
│   ├── config.py                  # Settings (Pydantic BaseSettings)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── planner.py             # Planner Agent
│   │   └── executor.py            # Executor Agent
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── chat.py            # POST /api/chat (SSE)
│   │       └── health.py          # GET /api/health
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chat_service.py        # Orchestrator
│   │   ├── openai_client.py       # OpenAI API wrapper
│   │   └── search_service.py      # Tavily API wrapper
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic models
│   └── core/
│       ├── __init__.py
│       └── exceptions.py          # Custom exceptions + handlers
├── tests/
│   ├── conftest.py
│   ├── agents/
│   │   ├── test_planner.py
│   │   └── test_executor.py
│   ├── services/
│   │   ├── test_chat_service.py
│   │   ├── test_openai_client.py
│   │   └── test_search_service.py
│   └── api/
│       └── test_chat.py
├── pyproject.toml
├── Dockerfile
└── .env.example
```

### Planner Agent

**Input:** User message + conversation history
**Output:** PlannerDecision

```python
class PlannerDecision(BaseModel):
    needs_search: bool              # Whether web search is needed
    reasoning: str                  # Decision reasoning (shown to user)
    search_queries: list[str]       # Search keywords (max 3)
    query_type: str                 # "temporal" | "factual" | "conversational"
```

**Decision Logic (System Prompt):**
- Temporal questions (stock prices, news, exchange rates, weather) → **must search**
- Factual questions (history, science, geography) → **search if uncertain**
- Chat/greetings/math → **no search**
- Generate precise search queries, optimized for language (Chinese/English)

### Executor Agent

**Input:** User message + search results (if any)
**Output:** Streaming answer chunks + citations

```python
class Citation(BaseModel):
    index: int                      # [1], [2], ...
    title: str
    url: str
    snippet: str
```

**Response Logic (System Prompt):**
- With search results: answer based on results, cite with [1], [2] markers
- Without search results: answer from model knowledge
- Match response language to user input language
- Stream output token by token

### SSE Event Stream

```
Event 1: { "event": "planner",   "data": { "needs_search": true, "reasoning": "...", "queries": [...] } }
Event 2: { "event": "searching", "data": { "query": "TSMC stock price", "status": "searching" } }
Event 3: { "event": "searching", "data": { "query": "TSMC stock price", "status": "done", "results_count": 5 } }
Event 4: { "event": "chunk",     "data": { "content": "Based on " } }
Event 5: { "event": "chunk",     "data": { "content": "the latest" } }
...
Event N: { "event": "citations", "data": { "citations": [{...}, {...}] } }
Event N+1: { "event": "done",   "data": { "total_tokens": 1234 } }
```

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Main chat endpoint (SSE streaming) |
| `/api/health` | GET | Health check |

**POST /api/chat Request:**
```json
{
  "message": "What is TSMC's stock price today?",
  "conversation_id": "optional-uuid",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

## Frontend Design

### Project Structure

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── globals.css
├── src/
│   ├── components/
│   │   ├── ChatLayout.tsx          # Overall layout: sidebar + main area
│   │   ├── Sidebar.tsx             # Conversation history list
│   │   ├── ChatPanel.tsx           # Message list + input
│   │   ├── MessageBubble.tsx       # Single message bubble (user/AI)
│   │   ├── AgentThinking.tsx       # Planner thinking process animation
│   │   ├── SearchProgress.tsx      # Search progress indicator
│   │   ├── CitationList.tsx        # Citation source card list
│   │   ├── CitationCard.tsx        # Single citation source card
│   │   ├── StreamingText.tsx       # Streaming text render + Markdown
│   │   └── ChatInput.tsx           # Input box (Enter to send, Shift+Enter newline)
│   ├── hooks/
│   │   ├── useChat.ts              # Chat state management
│   │   └── useSSE.ts               # SSE connection management
│   ├── lib/
│   │   ├── api.ts                  # API client
│   │   └── types.ts                # TypeScript type definitions
│   └── __tests__/
│       ├── ChatPanel.test.tsx
│       └── useChat.test.ts
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.ts
└── Dockerfile
```

### UI Layout (ChatGPT Style)

```
┌──────────────────────────────────────────────────────────┐
│  ┌──────────┐  ┌──────────────────────────────────────┐  │
│  │  Sidebar  │  │            Chat Area                 │  │
│  │           │  │                                      │  │
│  │ + New Chat│  │  ┌─────────────────────────────────┐ │  │
│  │           │  │  │ Planner: searching for prices    │ │  │
│  │ Today     │  │  │    Query: "TSMC stock price"    │ │  │
│  │ ─ TSMC    │  │  │    ✓ Found 5 results            │ │  │
│  │ ─ Weather │  │  └─────────────────────────────────┘ │  │
│  │           │  │                                      │  │
│  │ Yesterday │  │  Based on the latest info, TSMC...   │  │
│  │ ─ Forex   │  │  current price is XXX TWD [1]       │  │
│  │           │  │                                      │  │
│  │           │  │  Sources:                            │  │
│  │           │  │  ┌─────┐ ┌─────┐ ┌─────┐           │  │
│  │           │  │  │ [1] │ │ [2] │ │ [3] │           │  │
│  │           │  │  │Yahoo│ │CNBC │ │Reut.│           │  │
│  │           │  │  └─────┘ └─────┘ └─────┘           │  │
│  │           │  │                                      │  │
│  │           │  │  ┌──────────────────────────┐  ┌──┐ │  │
│  │           │  │  │ Ask anything...          │  │➤ │ │  │
│  │           │  │  └──────────────────────────┘  └──┘ │  │
│  └──────────┘  └──────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### UI Features

1. **Agent thinking visualization** — Planner decision shown as collapsible section
2. **Search progress animation** — Shows search queries and progress
3. **Streaming text** — Token-by-token rendering with Markdown support
4. **Citation cards** — Clickable [1] markers in text, source cards at bottom
5. **Conversation history** — Sidebar manages multiple conversations (localStorage)
6. **Responsive design** — Sidebar collapses on mobile

### Tech Choices

- **Tailwind CSS** — Rapid development, consistent design
- **react-markdown** — Markdown rendering
- **localStorage** — Conversation history persistence
- **uuid** — Conversation ID generation

## Testing Strategy

### Backend (pytest)

```
Unit Tests:
├── agents/test_planner.py     — Planner decision logic (search/no-search correctness)
├── agents/test_executor.py    — Executor citation formatting, answer structure
├── services/test_search.py    — Tavily API mock, error handling
└── services/test_openai.py    — OpenAI API mock, streaming

Integration Tests:
└── api/test_chat.py           — SSE event sequence, end-to-end flow

All external API calls are mocked — tests run offline.
```

### Frontend (Vitest + React Testing Library)

```
├── ChatPanel.test.tsx         — Message display, input submission
└── useChat.test.ts            — State management logic
```

## Deployment

```
Frontend (Vercel):
  - Next.js auto-deploy
  - Env: NEXT_PUBLIC_API_URL

Backend (Railway or Render):
  - Docker container
  - Env: OPENAI_API_KEY, TAVILY_API_KEY
  - Free tier sufficient for demo
```

## Git Strategy

- **Conventional Commits** — `feat()`, `fix()`, `test()`, `docs()`
- **Incremental history** — Progressive development, not single big commit
- **No API keys** — `.env.example` templates only

## Deliverables

1. Git repository with source code
2. README with setup guide + architecture explanation
3. Online demo link (Vercel + Railway/Render)
4. `docs/ai_usage.md` — AI tool usage documentation

## Evaluation Alignment

| Criteria | How We Address It |
|----------|-------------------|
| 1. User experience | ChatGPT-style UI, streaming, agent thinking visualization |
| 2. UI comfort | Tailwind CSS, responsive, clean design |
| 3. Architecture | Clean 2-Agent separation, service layer, dependency injection |
| 4. Code quality | Type-safe, Pydantic validation, error handling |
| 5. Git commits | Conventional commits, incremental development |
| 6. Documentation | Comprehensive README, design doc, AI usage doc |
| 7. Search correctness | Planner accuracy tests, Tavily integration, citation quality |
