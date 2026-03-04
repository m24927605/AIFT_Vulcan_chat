# Finnhub API Integration Design

## Goal

Integrate Finnhub API as a dedicated US/global stock and forex data source alongside Fugle (Taiwan stocks) and Tavily (web search). The Planner intelligently selects which Finnhub endpoints to call based on the user's query, and all data sources run in parallel.

## Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Finnhub role | Supplement (not replacement) | Finnhub for US/global/forex, Fugle for TW stocks, Tavily for everything else |
| Scope | All major endpoints | Quote, candles, forex, profile, financials, news, earnings, price target, recommendation, insider |
| Routing | Planner smart selection | Planner picks relevant endpoints per query; avoids unnecessary API calls |
| With Fugle | Complementary | TW stocks → Fugle, US/global/forex → Finnhub, no overlap |
| Format language | English | Finnhub data is English-native; Executor handles response language |
| API key management | Optional env var | `FINNHUB_API_KEY` empty = graceful degradation |
| Architecture | Extend existing data_sources | Add FinnhubSource alongside FugleSource in PlannerDecision |

## Architecture

```
User Query
    │
    ▼
Planner Agent ──► PlannerDecision
    │                  │
    │          ┌───────┴────────┐
    │          │ data_sources:  │
    │          │ FugleSource[]  │
    │          │ FinnhubSource[]│
    │          └───────┬────────┘
    │                  │
    ▼                  ▼
Deterministic      ┌──────────────────┐
Pre-check          │  ChatService     │
(unchanged)        │                  │
                   │  asyncio.gather: │
                   │  ├─ DataSources  │  (Fugle + Finnhub)
                   │  └─ Tavily       │
                   │                  │
                   │  merge results   │
                   │  (data first)    │
                   └───────┬──────────┘
                           │
                           ▼
                    Executor Agent
                    (unchanged prompt)
```

## Data Model Changes

### FinnhubSource (new)

```python
class FinnhubSource(BaseModel):
    type: str = Field(..., pattern="^(finnhub_quote|finnhub_candles|finnhub_forex|finnhub_profile|finnhub_financials|finnhub_news|finnhub_earnings|finnhub_price_target|finnhub_recommendation|finnhub_insider)$")
    symbol: str = Field(..., min_length=1, max_length=20)
    timeframe: str | None = Field(None, pattern="^(1|5|15|30|60|D|W|M)$")
    from_date: str | None = None
    to_date: str | None = None
```

### PlannerDecision (extended)

```python
class PlannerDecision(BaseModel):
    needs_search: bool
    reasoning: str
    search_queries: list[str] = Field(default_factory=list, max_length=3)
    query_type: str = Field(..., pattern="^(temporal|factual|conversational)$")
    data_sources: list[FugleSource | FinnhubSource] = Field(default_factory=list)
```

### Finnhub endpoint types

| type | Finnhub endpoint | Use case |
|------|-----------------|----------|
| `finnhub_quote` | `/quote` | Real-time stock price |
| `finnhub_candles` | `/stock/candle` | Historical OHLCV data |
| `finnhub_forex` | `/forex/rates` | Exchange rates |
| `finnhub_profile` | `/stock/profile2` | Company info (name, industry, market cap) |
| `finnhub_financials` | `/stock/metric` | Key financial ratios (P/E, EPS, etc.) |
| `finnhub_news` | `/company-news` | Recent company news |
| `finnhub_earnings` | `/stock/earnings` | Historical EPS surprises |
| `finnhub_price_target` | `/stock/price-target` | Analyst price targets |
| `finnhub_recommendation` | `/stock/recommendation` | Buy/sell/hold consensus |
| `finnhub_insider` | `/stock/insider-transactions` | Insider trading activity |

### Planner Prompt Extension

Add after existing Taiwan stock rule (rule 5):

```
6. NON-TAIWAN STOCKS & FOREX: For US/international stocks (AAPL, MSFT, TSLA)
   or forex pairs (USD/TWD), use finnhub_* types in data_sources.
   Choose endpoints based on what the user asks:
   - Price/quote → finnhub_quote
   - Historical trend → finnhub_candles
   - Exchange rate → finnhub_forex
   - Company info → finnhub_profile
   - Financial metrics → finnhub_financials
   - Recent news → finnhub_news
   - Earnings history → finnhub_earnings
   - Analyst targets → finnhub_price_target
   - Buy/sell consensus → finnhub_recommendation
   - Insider trading → finnhub_insider
   Always also set needs_search=true for supplementary context.
```

## FinnhubService

New file: `backend/app/core/services/finnhub_service.py`

```python
class FinnhubService:
    def __init__(self, api_key: str):
        self._client = finnhub.Client(api_key=api_key)

    # --- Async methods (wrap sync SDK with asyncio.to_thread) ---
    async def get_quote(self, symbol: str) -> str: ...
    async def get_candles(self, symbol: str, timeframe: str = "D",
                          from_date: str | None = None, to_date: str | None = None) -> str: ...
    async def get_forex_rates(self, symbol: str) -> str: ...
    async def get_profile(self, symbol: str) -> str: ...
    async def get_financials(self, symbol: str) -> str: ...
    async def get_news(self, symbol: str, from_date: str | None = None,
                       to_date: str | None = None) -> str: ...
    async def get_earnings(self, symbol: str) -> str: ...
    async def get_price_target(self, symbol: str) -> str: ...
    async def get_recommendation(self, symbol: str) -> str: ...
    async def get_insider(self, symbol: str) -> str: ...

    # --- Format methods (dict → human-readable English text) ---
    def format_quote(self, data: dict, symbol: str) -> str: ...
    def format_candles(self, data: dict, symbol: str) -> str: ...
    def format_forex_rates(self, data: dict, base: str) -> str: ...
    def format_profile(self, data: dict) -> str: ...
    def format_financials(self, data: dict, symbol: str) -> str: ...
    def format_news(self, articles: list) -> str: ...
    def format_earnings(self, data: list, symbol: str) -> str: ...
    def format_price_target(self, data: dict, symbol: str) -> str: ...
    def format_recommendation(self, data: list, symbol: str) -> str: ...
    def format_insider(self, data: dict, symbol: str) -> str: ...
```

Key design:
- Finnhub SDK is sync → wrap with `asyncio.to_thread()` to avoid blocking
- Returns formatted English text, not JSON — consistent with existing pipeline
- On failure: log warning, return empty string (graceful degradation)

### Format examples

- **quote**: `"AAPL (Apple Inc) — Current: $189.50, Change: +2.30 (+1.23%), Day Range: $187.20–$190.15"`
- **candles**: `"AAPL Historical (Daily):\n  2026-03-03 O:189 H:191 L:188 C:190 V:45.2M\n  ..."`
- **forex**: `"Exchange Rates (base: USD):\n  TWD: 32.15, JPY: 149.80, EUR: 0.92"`
- **profile**: `"Apple Inc (AAPL) — Industry: Technology, Market Cap: $2.95T, IPO: 1980-12-12"`
- **financials**: `"AAPL Financials — P/E: 29.5, EPS (TTM): $6.42, Dividend Yield: 0.55%, 52W High: $199.62"`
- **news**: `"AAPL Recent News:\n  1. Apple announces new AI features (2026-03-01)\n  2. ..."`
- **earnings**: `"AAPL Earnings:\n  Q4 2025: EPS $2.10 (est $2.05, surprise +2.4%)\n  ..."`
- **price_target**: `"AAPL Price Target — High: $250, Low: $180, Mean: $215 (25 analysts)"`
- **recommendation**: `"AAPL Analyst Consensus (2026-03): Buy: 28, Hold: 7, Sell: 1, Strong Buy: 12"`
- **insider**: `"AAPL Insider Transactions:\n  Tim Cook sold 100,000 shares at $189.50 (2026-02-15)\n  ..."`

## ChatService Integration

### Refactor `_fetch_fugle` → `_fetch_data_sources`

```python
async def _fetch_data_sources(
    self, data_sources: list[FugleSource | FinnhubSource]
) -> list[SearchResult]:
    if not data_sources:
        return []

    results = []
    for src in data_sources:
        text = ""
        if isinstance(src, FugleSource) and self._fugle:
            if src.type == "fugle_quote":
                text = await self._fugle.get_quote(src.symbol)
            elif src.type == "fugle_historical":
                text = await self._fugle.get_historical(src.symbol, src.timeframe or "D")
        elif isinstance(src, FinnhubSource) and self._finnhub:
            text = await self._dispatch_finnhub(src)

        if text:
            results.append(SearchResult(
                title=f"{'Fugle' if isinstance(src, FugleSource) else 'Finnhub'}: {src.symbol} {src.type}",
                url="",
                content=text,
                score=1.0,
            ))
    return results
```

### Constructor

```python
class ChatService:
    def __init__(
        self,
        llm: LLMClient,
        tavily_api_key: str,
        fugle_api_key: str = "",
        finnhub_api_key: str = "",
    ):
        ...
        self._fugle = FugleService(api_key=fugle_api_key) if fugle_api_key else None
        self._finnhub = FinnhubService(api_key=finnhub_api_key) if finnhub_api_key else None
```

### Parallel fetch (unchanged pattern)

```python
fugle_task = self._fetch_data_sources(decision.data_sources)
tavily_task = self._search.search_multiple(decision.search_queries)
data_results, search_results = await asyncio.gather(fugle_task, tavily_task)
all_results = data_results + search_results
```

## Unchanged Components

- **Executor prompt**: Already handles "Answer based ONLY on search results" + strict numerical quoting
- **`build_citations`**: Already filters `url=""` results (Finnhub won't appear in citation cards)
- **Deterministic pre-check**: Manages `needs_search`, unrelated to Finnhub routing
- **Frontend**: No changes — Finnhub data flows through existing search result pipeline

## Config

```python
# config.py
finnhub_api_key: str = ""  # empty = Finnhub disabled
```

```bash
# .env.example
FINNHUB_API_KEY=  # Finnhub API key (optional, for US/global stock + forex data)
```

## Finnhub Free Tier Limits

| Item | Limit |
|------|-------|
| API calls/minute | 60 |
| API calls/second | 30 |
| Historical depth | Several years |
| Cost | Free (registration required) |

## Files Summary

| File | Action |
|------|--------|
| `backend/app/core/services/finnhub_service.py` | NEW |
| `backend/tests/core/services/test_finnhub_service.py` | NEW |
| `backend/app/core/models/schemas.py` | MODIFY — add FinnhubSource, union type |
| `backend/app/core/agents/planner.py` | MODIFY — extend prompt with rule 6 |
| `backend/app/core/services/chat_service.py` | MODIFY — refactor to _fetch_data_sources, add finnhub_api_key |
| `backend/app/web/routes/chat.py` | MODIFY — pass finnhub_api_key |
| `backend/app/entrypoint.py` | MODIFY — pass finnhub_api_key |
| `backend/app/core/config.py` | MODIFY — add finnhub_api_key |
| `backend/pyproject.toml` | MODIFY — add finnhub-python dep |
| `backend/.env.example` | MODIFY — add FINNHUB_API_KEY |
| `backend/tests/core/agents/test_planner.py` | MODIFY — Finnhub routing tests |
| `backend/tests/core/services/test_chat_service.py` | MODIFY — Finnhub parallel tests |
| `backend/tests/e2e/test_chat_e2e.py` | MODIFY — Finnhub E2E test |
| `README.md` | MODIFY — tech stack, env vars, test count |
| `docs/architecture.md` | MODIFY — diagram, design decisions |

## Testing

New tests (in `test_finnhub_service.py`):
- `test_format_quote` / `test_get_quote_returns_formatted_text` / `test_get_quote_handles_error`
- Same pattern for each of the 10 endpoints (format + get + error = ~30 tests)

Modified tests:
- `test_chat_with_finnhub_and_tavily_parallel`
- `test_chat_with_fugle_and_finnhub_and_tavily` (triple parallel)
- `test_chat_without_finnhub_key_skips_finnhub`
- `test_planner_outputs_finnhub_source_for_us_stock`
- `test_planner_outputs_finnhub_forex`
- Finnhub E2E integration test
