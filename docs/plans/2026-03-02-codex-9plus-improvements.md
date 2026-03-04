# Codex 9+ Score Improvements — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement 6 improvements to push documentation and test quality from 8.6/10 to 9+.

**Architecture:** Documentation-heavy changes (4 doc tasks) + frontend unit tests (12 new tests across 3 files) + README enhancements. No backend code changes.

**Tech Stack:** Vitest, React Testing Library, Markdown

---

### Task 1: Create `docs/architecture.md` — Final Architecture + E2E Flow + Real Example

**Files:**
- Create: `docs/architecture.md`

**Step 1: Write the architecture doc**

Create `docs/architecture.md` with this content:

```markdown
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
│  - SSE      │ ──────────────────────── │  │  1. Planner Agent (GPT-4o)   │   │
│             │                          │  │     ↓ PlannerDecision        │   │
└─────────────┘                          │  │  2. Deterministic Pre-check  │   │
                                         │  │     ↓ override if temporal   │   │
┌─────────────┐                          │  │  3. Search Service (Tavily)  │   │
│  Telegram   │   python-telegram-bot    │  │     ↓ SearchResult[]        │   │
│  Bot        │ ◀──────────────────────▶ │  │  4. Executor Agent (GPT-4o)  │   │
│             │                          │  │     ↓ SSE stream            │   │
└─────────────┘                          │  └──────────────────────────────┘   │
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
| 5 | **Executor Agent** | Synthesizes answer from search results → streams tokens via SSE with `[1]`, `[2]` citation markers |
| 6 | **Frontend** | Renders streaming text + planner thinking + search progress + citation cards |

If the conversation is linked to Telegram, the backend also pushes the complete response (with formatted citations) to the linked Telegram chat.

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

## Key Design Decisions

| Decision | Alternative Considered | Rationale |
|----------|----------------------|-----------|
| SSE over WebSocket | WebSocket (bidirectional) | SSE is simpler for server→client streaming; we don't need client→server streaming mid-response |
| SQLite over PostgreSQL | PostgreSQL (scalable) | Zero-config, embedded, sufficient for demo; storage abstraction allows future migration |
| Tavily over Google Search API | Google Custom Search ($5/1000 queries) | Tavily has generous free tier, simpler API, built-in content extraction |
| localStorage for Telegram ID | Server-side user auth | No user account system needed for assignment scope; localStorage is simplest |
| 2-Agent (Planner+Executor) over single agent | Single LLM call with tools | Separation of concerns: Planner optimizes search decision, Executor optimizes answer quality |
| Deterministic pre-check | Trust LLM fully | Safety net for must-search temporal queries; hybrid approach preserves flexibility |
```

**Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add Final Architecture overview with E2E flow and real example"
```

---

### Task 2: Create `docs/ops.md` — Operational Runbook

**Files:**
- Create: `docs/ops.md`

**Step 1: Write the ops doc**

Create `docs/ops.md` with this content:

```markdown
# Operational Runbook

## Health Check

```bash
curl https://your-backend-url/api/health
# Expected: {"status":"ok"}
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `CORS: blocked by policy` | `FRONTEND_URL` env var doesn't match actual frontend origin | Set `FRONTEND_URL=https://your-frontend-domain` on backend |
| `HTTP 500` on `/api/chat` | Missing `OPENAI_API_KEY` or `TAVILY_API_KEY` | Verify `.env` has valid keys; check backend logs |
| `Search failed for query '...'` | Tavily API error (rate limit, network) | Tavily free tier: 1000 req/month; check quota at tavily.com dashboard |
| Telegram bot not responding | `TELEGRAM_BOT_TOKEN` invalid or bot not started | Verify token with BotFather; ensure `MODE=all` or `MODE=telegram` |
| Telegram messages not syncing | Conversation not linked to Telegram chat ID | User must enter Chat ID in sidebar; verify via `GET /api/conversations/:id` |
| `sqlite3.OperationalError: database is locked` | Concurrent write from multiple workers | Use single-worker deployment (`--workers 1`) or migrate to PostgreSQL |

## Rate Limits & Timeouts

| Service | Limit | Timeout | Behavior on Exceed |
|---------|-------|---------|--------------------|
| OpenAI API | Depends on plan tier | 30s (default) | SSE `error` event → frontend shows error |
| Tavily Search | 1000 req/month (free) | 10s per query | Returns empty results → Executor answers from knowledge |
| Backend → Telegram push | Telegram rate limit: 30 msg/sec | 5s | Fire-and-forget; logged server-side, message dropped |
| SSE connection | No server-side limit | Browser default (~5 min) | Frontend reconnects on next user message |

## Logs

- **Backend**: stdout/stderr via uvicorn; structured with Python `logging`
- **Railway**: `railway logs` CLI or dashboard → Deployments → Logs
- **Vercel**: `vercel logs` CLI or dashboard → Deployments → Functions tab

## Deployment Quick Reference

```bash
# Frontend (Vercel)
cd frontend && vercel --yes --prod

# Backend (Railway)
railway up --detach

# Or via Docker
docker build -t vulcan-backend ./backend
docker run -p 8000:8000 --env-file backend/.env vulcan-backend
```
```

**Step 2: Commit**

```bash
git add docs/ops.md
git commit -m "docs: add operational runbook (errors, rate limits, logs)"
```

---

### Task 3: Add Non-goals, Trade-offs, and Priority column to README

**Files:**
- Modify: `README.md:198-207` (Known Limitations section)

**Step 1: Insert Non-goals and Trade-offs before Known Limitations**

Insert before `## Known Limitations` (line 198):

```markdown
## Non-goals

These are explicitly out of scope for this project:

- **User authentication** — No login/signup system; conversations are identified by UUID only
- **Multi-LLM provider switching** — Hardcoded to OpenAI GPT-4o; no abstraction layer for switching providers
- **Search result ranking/re-ranking** — Results are used as-is from Tavily; no custom relevance scoring
- **Offline mode** — Both web search and LLM require active internet connection

## Trade-off Decisions

| Decision | Alternative | Why We Chose This |
|----------|------------|-------------------|
| SSE streaming | WebSocket | Simpler for unidirectional server→client flow; no need for mid-response client messages |
| SQLite | PostgreSQL | Zero-config, embedded, sufficient for demo scope; storage abstraction allows migration |
| Tavily | Google Custom Search | Generous free tier, simpler API, built-in content extraction |
| localStorage (Telegram ID) | Server-side auth | No user account system needed; simplest approach for assignment scope |
```

**Step 2: Add Priority column to Known Limitations table**

Replace the existing Known Limitations table with:

```markdown
## Known Limitations

| Area | Limitation | Mitigation | Priority |
|------|-----------|------------|----------|
| **Search source reliability** | Tavily results may include low-quality or outdated sources; the system does not verify factual accuracy of search results | Executor Agent is instructed to synthesize across multiple sources and cite each claim | P2 |
| **Planner misjudgment** | LLM-based planning is non-deterministic — edge cases (e.g., ambiguous phrasing) may lead to incorrect search/no-search decisions | Deterministic pre-check overrides missed temporal queries; Planner defaults to search on parse failure | P1 — partially mitigated |
| **Single LLM provider** | Hardcoded to OpenAI GPT-4o; no fallback if the API is down or rate-limited | Could be extended with provider abstraction, but out of scope for this assignment | P3 |
| **SQLite scalability** | SQLite is single-writer; not suitable for high-concurrency production use | Sufficient for demo/assignment scope; migration to PostgreSQL would be straightforward via the storage abstraction | P2 |
| **Conversation context window** | Full conversation history is sent to both agents; long conversations may exceed token limits | Could add sliding window or summarization, but not implemented | P2 |
| **Telegram sync latency** | Web → Telegram push is fire-and-forget; network failures silently drop messages | Logged server-side; no retry queue implemented | P3 |
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add Non-goals, Trade-offs, and priority levels to README"
```

---

### Task 4: Frontend tests — `useSSE.test.ts` (5 tests)

**Files:**
- Create: `frontend/src/__tests__/useSSE.test.ts`

**Step 1: Write the tests**

Create `frontend/src/__tests__/useSSE.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSSE } from "@/hooks/useSSE";

// Helper: create a ReadableStream from SSE text
function sseStream(text: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

function mockFetchSSE(sseText: string) {
  vi.spyOn(global, "fetch").mockResolvedValueOnce({
    ok: true,
    body: sseStream(sseText),
  } as unknown as Response);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("useSSE", () => {
  it("parses planner event", async () => {
    const sse =
      'event: planner\ndata: {"needs_search":true,"reasoning":"temporal","search_queries":["test"],"query_type":"temporal"}\n\nevent: done\ndata: {}\n\n';
    mockFetchSSE(sse);

    const onPlanner = vi.fn();
    const onDone = vi.fn();
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], { onPlanner, onDone });
    });

    expect(onPlanner).toHaveBeenCalledWith({
      needs_search: true,
      reasoning: "temporal",
      search_queries: ["test"],
      query_type: "temporal",
    });
    expect(onDone).toHaveBeenCalledOnce();
  });

  it("parses chunk events and accumulates content", async () => {
    const sse =
      'event: chunk\ndata: {"content":"Hello "}\n\nevent: chunk\ndata: {"content":"world"}\n\nevent: done\ndata: {}\n\n';
    mockFetchSSE(sse);

    const chunks: string[] = [];
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], {
        onChunk: (data) => chunks.push(data.content),
      });
    });

    expect(chunks).toEqual(["Hello ", "world"]);
  });

  it("parses citations event", async () => {
    const sse =
      'event: citations\ndata: {"citations":[{"index":1,"title":"Test","url":"https://example.com","snippet":"..."}]}\n\nevent: done\ndata: {}\n\n';
    mockFetchSSE(sse);

    const onCitations = vi.fn();
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], { onCitations });
    });

    expect(onCitations).toHaveBeenCalledWith({
      citations: [
        { index: 1, title: "Test", url: "https://example.com", snippet: "..." },
      ],
    });
  });

  it("skips malformed JSON without crashing", async () => {
    const sse =
      'event: chunk\ndata: {INVALID JSON}\n\nevent: chunk\ndata: {"content":"ok"}\n\nevent: done\ndata: {}\n\n';
    mockFetchSSE(sse);

    const chunks: string[] = [];
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], {
        onChunk: (data) => chunks.push(data.content),
      });
    });

    expect(chunks).toEqual(["ok"]);
  });

  it("calls onError for non-abort fetch failures", async () => {
    vi.spyOn(global, "fetch").mockRejectedValueOnce(new Error("Network error"));

    const onError = vi.fn();
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], { onError });
    });

    expect(onError).toHaveBeenCalledWith("Network error");
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test
```

Expected: All 5 new tests PASS + 4 existing ChatInput tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/useSSE.test.ts
git commit -m "test(frontend): add useSSE hook tests (5 cases)"
```

---

### Task 5: Frontend tests — `CitationCard.test.tsx` (2 tests)

**Files:**
- Create: `frontend/src/__tests__/CitationCard.test.tsx`

**Step 1: Write the tests**

Create `frontend/src/__tests__/CitationCard.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CitationCard } from "@/components/CitationCard";

describe("CitationCard", () => {
  it("extracts and displays domain from URL", () => {
    render(
      <CitationCard
        citation={{
          index: 1,
          title: "Test Article",
          url: "https://www.example.com/page",
          snippet: "...",
        }}
      />
    );

    expect(screen.getByText("example.com")).toBeDefined();
    expect(screen.getByText("1")).toBeDefined();
    expect(screen.getByText("Test Article")).toBeDefined();
  });

  it("falls back to raw URL on invalid URL", () => {
    render(
      <CitationCard
        citation={{
          index: 2,
          title: "Broken Link",
          url: "not-a-valid-url",
          snippet: "...",
        }}
      />
    );

    expect(screen.getByText("not-a-valid-url")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test
```

Expected: All 11 tests PASS (4 ChatInput + 5 useSSE + 2 CitationCard).

**Step 3: Commit**

```bash
git add frontend/src/__tests__/CitationCard.test.tsx
git commit -m "test(frontend): add CitationCard tests (domain extraction, invalid URL)"
```

---

### Task 6: Frontend tests — `ChatInput.test.tsx` (+1 test) + `useChat.test.ts` (4 tests)

**Files:**
- Modify: `frontend/src/__tests__/ChatInput.test.tsx`
- Create: `frontend/src/__tests__/useChat.test.ts`

**Step 1: Add Enter key test to ChatInput.test.tsx**

Append inside the `describe("ChatInput")` block:

```typescript
  it("sends message on Enter key (not Shift+Enter)", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByPlaceholderText("Ask anything...");
    fireEvent.change(textarea, { target: { value: "Hello" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    expect(onSend).toHaveBeenCalledWith("Hello");
  });
```

**Step 2: Create useChat.test.ts**

Create `frontend/src/__tests__/useChat.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// Mock dependencies before importing useChat
vi.mock("@/hooks/useSSE", () => ({
  useSSE: () => ({
    sendMessage: vi.fn(),
    abort: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  fetchConversations: vi.fn().mockResolvedValue([]),
  createConversation: vi.fn().mockResolvedValue({ id: "test", title: "test" }),
  fetchMessages: vi.fn().mockResolvedValue([]),
  deleteConversationApi: vi.fn().mockResolvedValue(undefined),
  linkTelegram: vi.fn().mockResolvedValue(undefined),
  unlinkTelegram: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("uuid", () => ({
  v4: () => "mock-uuid-1234",
}));

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();
vi.stubGlobal("localStorage", localStorageMock);

import { useChat } from "@/hooks/useChat";

beforeEach(() => {
  vi.clearAllMocks();
  localStorageMock.clear();
});

describe("useChat", () => {
  it("newChat creates a new conversation with empty state", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.newChat();
    });

    expect(result.current.activeId).toBe("mock-uuid-1234");
    expect(result.current.messages).toEqual([]);
    expect(result.current.isLoading).toBe(false);
  });

  it("deleteConversation removes active conversation and resets state", async () => {
    const { deleteConversationApi } = await import("@/lib/api");
    const { result } = renderHook(() => useChat());

    // Create a conversation first
    act(() => {
      result.current.newChat();
    });

    const id = result.current.activeId!;

    act(() => {
      result.current.deleteConversation(id);
    });

    expect(deleteConversationApi).toHaveBeenCalledWith(id);
    expect(result.current.activeId).toBeNull();
    expect(result.current.messages).toEqual([]);
  });

  it("updateTelegramChatId persists to localStorage", () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.updateTelegramChatId("12345");
    });

    expect(result.current.telegramChatId).toBe("12345");
    expect(localStorageMock.getItem("telegramChatId")).toBe("12345");
  });

  it("updateTelegramChatId removes from localStorage when empty", () => {
    localStorageMock.setItem("telegramChatId", "99999");
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.updateTelegramChatId("");
    });

    expect(result.current.telegramChatId).toBe("");
    expect(localStorageMock.getItem("telegramChatId")).toBeNull();
  });
});
```

**Step 3: Run all tests**

```bash
cd frontend && npm test
```

Expected: All 16 tests PASS (5 ChatInput + 5 useSSE + 2 CitationCard + 4 useChat).

**Step 4: Commit**

```bash
git add frontend/src/__tests__/ChatInput.test.tsx frontend/src/__tests__/useChat.test.ts
git commit -m "test(frontend): add useChat hook tests (4) and Enter key test for ChatInput"
```

---

### Task 7: Update design doc, final commit, deploy

**Files:**
- Modify: `docs/plans/2026-03-01-web-search-chatbot-design.md:270-276` (Testing Strategy section)

**Step 1: Update design doc test section**

In the Testing Strategy Frontend section, update to reflect new test count:

```markdown
### Frontend (Vitest + React Testing Library)

```
└── __tests__/
    ├── ChatInput.test.tsx     — Input submission, keyboard handling (5 tests)
    ├── useSSE.test.tsx        — SSE event parsing, error handling (5 tests)
    ├── useChat.test.ts        — State management, localStorage (4 tests)
    └── CitationCard.test.tsx  — Domain extraction, invalid URL (2 tests)
```

All external API calls are mocked — tests run offline.
```

**Step 2: Run full test suite (backend + frontend)**

```bash
make test-backend && make test-frontend
```

Expected: 75 backend + 16 frontend = 91 total tests PASS.

**Step 3: Commit and deploy**

```bash
git add docs/plans/2026-03-01-web-search-chatbot-design.md
git commit -m "docs: update design doc test section to reflect 16 frontend tests"
git push origin main
cd frontend && vercel --yes --prod
```
