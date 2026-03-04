# Codex 9+ Score Improvements — Design

## Goal
Implement 6 improvements identified by Codex AI review to push documentation and test quality from 8.6/10 to 9+.

## Improvements

### 1. Final Architecture Doc (merged with #5)
**New file**: `docs/architecture.md` (1-2 pages)
- System overview ASCII diagram
- End-to-end numbered flow (6 steps)
- Real request/response example: "台積電股價" → full SSE event sequence with citations
- Design decisions summary table
- Plan docs remain as-is (historical appendix)

### 2. Frontend Unit Tests (12 new, 16 total)

| File | Tests | Count |
|------|-------|-------|
| `useSSE.test.ts` | parse planner event, parse chunk events, parse citations event, handle abort gracefully, skip malformed JSON | 5 |
| `useChat.test.ts` | sendMessage updates state, newChat resets state, loadConversation fetches messages, deleteConversation removes entry | 4 |
| `CitationCard.test.tsx` | extract domain from URL, fallback on invalid URL | 2 |
| `ChatInput.test.tsx` | Enter key sends message (append to existing) | +1 |

Mock strategy: `vi.fn()`, `vi.spyOn(global, 'fetch')`, `vi.stubGlobal('localStorage', ...)`.

### 3. Non-goals & Trade-off Decisions (README)
Insert before Known Limitations:
- **Non-goals**: user accounts, multi-LLM switching, search ranking optimization, offline mode
- **Trade-offs table**: SSE vs WebSocket, SQLite vs PostgreSQL, localStorage vs auth, Tavily vs Google Search

### 4. docs/ops.md (Operational Runbook)
- Common errors & solutions (6 items)
- Rate limit / timeout behavior
- Health check usage
- Log location

### 5. End-to-end Flow + Real Example
Merged into #1 (`docs/architecture.md`).

### 6. Known Limitations Priority Column
Add `Priority` column (P1/P2/P3) to existing table in README.

## Files Changed

| File | Action |
|------|--------|
| `docs/architecture.md` | NEW — Final Architecture + E2E flow + real example |
| `docs/ops.md` | NEW — Operational runbook |
| `README.md` | MODIFY — Non-goals, Trade-offs, priority column |
| `frontend/src/__tests__/useSSE.test.ts` | NEW — 5 tests |
| `frontend/src/__tests__/useChat.test.ts` | NEW — 4 tests |
| `frontend/src/__tests__/CitationCard.test.tsx` | NEW — 2 tests |
| `frontend/src/__tests__/ChatInput.test.tsx` | MODIFY — +1 test |
