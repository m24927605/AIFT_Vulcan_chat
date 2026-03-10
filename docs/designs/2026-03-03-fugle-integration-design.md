# Fugle MarketData API Integration Design

## Goal

Integrate Fugle MarketData API as a dedicated Taiwan stock data source alongside Tavily web search. When users ask about Taiwan stocks, the system fetches precise exchange data from Fugle while Tavily provides supplementary news/analysis — both in parallel.

## Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fugle role | Supplement (not replacement) | Fugle for TW stock precision, Tavily for everything else |
| Routing | Extend Planner output | Single decision point, aligns with 2-Agent architecture |
| TW stock + Tavily | Parallel | Fugle provides numbers, Tavily provides context/news |
| Data format to Executor | Formatted text summary | Human-readable, consistent with existing search results |
| Symbol resolution | LLM (Planner) | GPT-4o/Claude know TW stock symbols; no mapping table needed |
| API key management | Optional env var | `FUGLE_API_KEY` empty = graceful degradation to pure Tavily |

## Architecture

```
User Query
    │
    ▼
Planner Agent ──► PlannerDecision
    │                  │
    │          ┌───────┴────────┐
    │          │ data_sources:  │
    │          │ [{type, symbol}]│
    │          └───────┬────────┘
    │                  │
    ▼                  ▼
Deterministic      ┌──────────────────┐
Pre-check          │  ChatService     │
(unchanged)        │                  │
                   │  asyncio.gather: │
                   │  ├─ FugleService │  ← NEW
                   │  └─ Tavily       │
                   │                  │
                   │  merge results   │
                   │  (Fugle first)   │
                   └───────┬──────────┘
                           │
                           ▼
                    Executor Agent
                    (unchanged prompt)
```

## Data Model Changes

### PlannerDecision (extended)

```python
class FugleSource(BaseModel):
    type: str       # "fugle_quote" | "fugle_historical"
    symbol: str     # e.g. "2330"
    timeframe: str | None = None  # "D", "W", "M" (historical only)

class PlannerDecision(BaseModel):
    needs_search: bool
    reasoning: str
    search_queries: list[str]
    query_type: str
    data_sources: list[FugleSource] = []  # NEW — empty = no Fugle
```

### Planner Prompt Extension

Add rule: when the query involves Taiwan stocks (stock codes like 2330, 0050, or names like 台積電, 鴻海), output `data_sources` with appropriate Fugle endpoints and symbols. Keep `needs_search: true` to also trigger Tavily for news/analysis.

## FugleService

New file: `backend/app/core/services/fugle_service.py`

```python
class FugleService:
    def __init__(self, api_key: str):
        self._client = RestClient(api_key=api_key)

    async def get_quote(self, symbol: str) -> str:
        """Call intraday/quote, return formatted text summary."""
        # Uses asyncio.to_thread() since Fugle SDK is synchronous

    async def get_historical(self, symbol: str, timeframe: str = "D") -> str:
        """Call historical/candles, return formatted text summary."""

    def format_quote(self, data: dict) -> str:
        """Convert Fugle quote JSON to human-readable text."""
        # e.g. "台積電(2330) 收盤價 1,975 元，漲跌 +15 (+0.76%)，成交量 28,453 張"

    def format_historical(self, data: dict, symbol: str) -> str:
        """Convert Fugle candles JSON to human-readable text."""
```

Key design:
- Fugle SDK is sync → wrap with `asyncio.to_thread()` to avoid blocking
- Returns formatted text, not JSON — consistent with Tavily search results
- On failure: log warning, return empty string (graceful degradation)

## ChatService Integration

```python
# Parallel fetch
fugle_results, search_results = await asyncio.gather(
    self._fetch_fugle(decision.data_sources),
    self._search.search_multiple(decision.search_queries),
)

# Merge — Fugle first (most precise data takes priority)
all_results = fugle_results + search_results
```

Fugle results are wrapped as `SearchResult(title="Fugle: ...", url="", content=formatted, score=1.0)`.

## Unchanged Components

- **Executor prompt**: Already has "Answer based ONLY on search results" + strict numerical quoting
- **`build_citations`**: Already filters out results with empty URL (Fugle won't appear in citation cards)
- **Deterministic pre-check**: Only manages `needs_search`, unrelated to Fugle routing
- **Frontend**: No changes needed — Fugle data flows through existing search result pipeline

## Config

```python
# config.py
fugle_api_key: str = ""  # empty = Fugle disabled, pure Tavily fallback
```

```bash
# .env.example
FUGLE_API_KEY=          # Fugle MarketData API key (optional, for TW stock data)
```

## Fugle Free Tier Limits

| Item | Limit |
|------|-------|
| Intraday API | 60 calls/min |
| Historical API | 60 calls/min |
| Cost | Free (Fugle member) |

60 calls/min is sufficient for a chatbot use case.

## Files Summary

| File | Action |
|------|--------|
| `backend/app/core/services/fugle_service.py` | NEW |
| `backend/app/core/models/schemas.py` | MODIFY — add FugleSource |
| `backend/app/core/agents/planner.py` | MODIFY — extend prompt + output |
| `backend/app/core/services/chat_service.py` | MODIFY — parallel Fugle + Tavily |
| `backend/app/core/config.py` | MODIFY — add fugle_api_key |
| `backend/pyproject.toml` | MODIFY — add fugle-marketdata dep |
| `backend/.env.example` | MODIFY — add FUGLE_API_KEY |
| `backend/tests/core/services/test_fugle_service.py` | NEW |
| `backend/tests/core/services/test_chat_service.py` | MODIFY |
| `backend/tests/core/agents/test_planner.py` | MODIFY |
| `README.md` | MODIFY — env vars, tech stack, limitations |
| `docs/architecture.md` | MODIFY — diagram, design decisions |

## Testing

New tests:
- `test_get_quote_returns_formatted_text`
- `test_get_historical_returns_formatted_text`
- `test_get_quote_handles_error_gracefully`
- `test_format_quote_extracts_key_fields`

Modified tests:
- `test_chat_with_fugle_and_tavily_parallel`
- `test_planner_outputs_data_sources_for_tw_stock`
