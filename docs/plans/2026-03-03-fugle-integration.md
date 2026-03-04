# Fugle MarketData API Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate Fugle MarketData API so Taiwan stock queries get precise exchange data (Fugle) alongside web search context (Tavily), both in parallel.

**Architecture:** Extend PlannerDecision with `data_sources` field. ChatService fetches Fugle + Tavily in parallel via `asyncio.gather`, merges results (Fugle first), feeds combined results to Executor unchanged.

**Tech Stack:** fugle-marketdata Python SDK, asyncio.to_thread (sync→async wrapper), Pydantic models

---

### Task 1: Add `fugle-marketdata` dependency and config

**Files:**
- Modify: `backend/pyproject.toml:6-19`
- Modify: `backend/app/core/config.py:1-22`
- Modify: `backend/.env.example`

**Step 1: Add dependency to pyproject.toml**

In `backend/pyproject.toml`, add to the `dependencies` list:

```python
    "fugle-marketdata>=1.0.0",
```

**Step 2: Add config field**

In `backend/app/core/config.py`, add after line 11 (`tavily_api_key`):

```python
    fugle_api_key: str = ""  # Fugle MarketData API key (optional, for TW stock data)
```

**Step 3: Add to .env.example**

In `backend/.env.example`, add after the Tavily section:

```bash
# Fugle MarketData (Taiwan stock data, optional)
# Get API key at https://developer.fugle.tw
FUGLE_API_KEY=
```

**Step 4: Install the dependency**

Run: `cd backend && .venv/bin/pip install -e ".[dev]"`
Expected: Successfully installed fugle-marketdata

**Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/core/config.py backend/.env.example
git commit -m "chore: add fugle-marketdata dependency and config"
```

---

### Task 2: Add FugleSource to data models

**Files:**
- Modify: `backend/app/core/models/schemas.py:15-19`

**Step 1: Write the test**

No separate test needed — Pydantic model validation is implicitly tested in Task 4 (planner tests). The model is trivial.

**Step 2: Add FugleSource and extend PlannerDecision**

In `backend/app/core/models/schemas.py`, add before `PlannerDecision`:

```python
class FugleSource(BaseModel):
    type: str = Field(..., pattern="^(fugle_quote|fugle_historical)$")
    symbol: str = Field(..., min_length=1, max_length=10)
    timeframe: str | None = Field(None, pattern="^[DWMK]$")
```

Then add to `PlannerDecision`:

```python
class PlannerDecision(BaseModel):
    needs_search: bool
    reasoning: str
    search_queries: list[str] = Field(default_factory=list, max_length=3)
    query_type: str = Field(..., pattern="^(temporal|factual|conversational)$")
    data_sources: list[FugleSource] = Field(default_factory=list)
```

**Step 3: Run existing tests to verify no breakage**

Run: `cd backend && .venv/bin/python -m pytest tests/core/agents/test_planner.py tests/core/services/test_chat_service.py -v`
Expected: All existing tests PASS (data_sources defaults to [] so nothing breaks)

**Step 4: Commit**

```bash
git add backend/app/core/models/schemas.py
git commit -m "feat: add FugleSource model and data_sources to PlannerDecision"
```

---

### Task 3: Create FugleService

**Files:**
- Create: `backend/app/core/services/fugle_service.py`
- Create: `backend/tests/core/services/test_fugle_service.py`

**Step 1: Write failing tests**

Create `backend/tests/core/services/test_fugle_service.py`:

```python
import pytest
from unittest.mock import MagicMock, patch

from app.core.services.fugle_service import FugleService


@pytest.fixture
def fugle_service():
    return FugleService(api_key="test-fugle-key")


def _mock_quote_response():
    return {
        "date": "2026-03-03",
        "symbol": "2330",
        "name": "台積電",
        "openPrice": 1980,
        "highPrice": 1990,
        "lowPrice": 1960,
        "closePrice": 1975,
        "lastPrice": 1975,
        "change": 15,
        "changePercent": 0.76,
        "total": {
            "tradeVolume": 28453,
            "tradeValue": 56200000000,
            "transaction": 15230,
        },
    }


def _mock_historical_response():
    return {
        "symbol": "2330",
        "type": "EQUITY",
        "exchange": "TWSE",
        "market": "TSE",
        "data": [
            {"date": "2026-03-03", "open": 1980, "high": 1990, "low": 1960, "close": 1975, "volume": 28453},
            {"date": "2026-03-02", "open": 1950, "high": 1970, "low": 1945, "close": 1960, "volume": 25100},
            {"date": "2026-02-28", "open": 1940, "high": 1955, "low": 1935, "close": 1950, "volume": 22300},
        ],
    }


def test_format_quote(fugle_service):
    text = fugle_service.format_quote(_mock_quote_response())
    assert "台積電" in text
    assert "2330" in text
    assert "1,975" in text
    assert "15" in text
    assert "0.76" in text
    assert "28,453" in text


def test_format_historical(fugle_service):
    text = fugle_service.format_historical(_mock_historical_response(), "2330")
    assert "2330" in text
    assert "1,975" in text
    assert "2026-03-03" in text
    assert "2026-03-02" in text


@pytest.mark.asyncio
async def test_get_quote_returns_formatted_text(fugle_service):
    with patch.object(fugle_service, "_client") as mock_client:
        mock_client.stock.intraday.quote.return_value = _mock_quote_response()
        result = await fugle_service.get_quote("2330")
        assert "台積電" in result
        assert "1,975" in result


@pytest.mark.asyncio
async def test_get_historical_returns_formatted_text(fugle_service):
    with patch.object(fugle_service, "_client") as mock_client:
        mock_client.stock.historical.candles.return_value = _mock_historical_response()
        result = await fugle_service.get_historical("2330")
        assert "2330" in result
        assert "1,975" in result


@pytest.mark.asyncio
async def test_get_quote_handles_error_gracefully(fugle_service):
    with patch.object(fugle_service, "_client") as mock_client:
        mock_client.stock.intraday.quote.side_effect = Exception("API Error")
        result = await fugle_service.get_quote("2330")
        assert result == ""


@pytest.mark.asyncio
async def test_get_historical_handles_error_gracefully(fugle_service):
    with patch.object(fugle_service, "_client") as mock_client:
        mock_client.stock.historical.candles.side_effect = Exception("API Error")
        result = await fugle_service.get_historical("2330")
        assert result == ""
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/core/services/test_fugle_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.services.fugle_service'`

**Step 3: Write implementation**

Create `backend/app/core/services/fugle_service.py`:

```python
import asyncio
import logging

from fugle_marketdata import RestClient

logger = logging.getLogger(__name__)


class FugleService:
    def __init__(self, api_key: str):
        self._client = RestClient(api_key=api_key)

    async def get_quote(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(
                self._client.stock.intraday.quote, symbol=symbol
            )
            return self.format_quote(data)
        except Exception as e:
            logger.warning("Fugle quote failed for %s: %s", symbol, e)
            return ""

    async def get_historical(self, symbol: str, timeframe: str = "D") -> str:
        try:
            data = await asyncio.to_thread(
                self._client.stock.historical.candles,
                symbol=symbol,
                timeframe=timeframe,
            )
            return self.format_historical(data, symbol)
        except Exception as e:
            logger.warning("Fugle historical failed for %s: %s", symbol, e)
            return ""

    def format_quote(self, data: dict) -> str:
        name = data.get("name", "")
        symbol = data.get("symbol", "")
        date = data.get("date", "")
        last = data.get("lastPrice") or data.get("closePrice", 0)
        open_p = data.get("openPrice", 0)
        high = data.get("highPrice", 0)
        low = data.get("lowPrice", 0)
        close = data.get("closePrice", 0)
        change = data.get("change", 0)
        change_pct = data.get("changePercent", 0)
        total = data.get("total", {})
        volume = total.get("tradeVolume", 0)

        sign = "+" if change >= 0 else ""
        return (
            f"{name}({symbol}) {date} 即時報價：\n"
            f"最新價 {last:,.0f} 元，漲跌 {sign}{change:,.0f} ({sign}{change_pct:.2f}%)\n"
            f"開盤 {open_p:,.0f}，最高 {high:,.0f}，最低 {low:,.0f}，收盤 {close:,.0f}\n"
            f"成交量 {volume:,} 張"
        )

    def format_historical(self, data: dict, symbol: str) -> str:
        candles = data.get("data", [])
        if not candles:
            return ""
        lines = [f"{symbol} 歷史股價："]
        for c in candles[:10]:
            date = c.get("date", "")
            close = c.get("close", 0)
            volume = c.get("volume", 0)
            lines.append(f"  {date} 收 {close:,.0f}，量 {volume:,}")
        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/core/services/test_fugle_service.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add backend/app/core/services/fugle_service.py backend/tests/core/services/test_fugle_service.py
git commit -m "feat: add FugleService with quote and historical formatting"
```

---

### Task 4: Extend Planner prompt for data_sources

**Files:**
- Modify: `backend/app/core/agents/planner.py:9-23`
- Modify: `backend/tests/core/agents/test_planner.py`

**Step 1: Write failing test**

Add to `backend/tests/core/agents/test_planner.py`:

```python
@pytest.mark.asyncio
async def test_planner_outputs_data_sources_for_tw_stock(planner, mock_llm):
    mock_llm.chat.return_value = json.dumps({
        "needs_search": True,
        "reasoning": "Taiwan stock price query",
        "search_queries": ["台積電 股價"],
        "query_type": "temporal",
        "data_sources": [{"type": "fugle_quote", "symbol": "2330"}],
    })
    decision = await planner.plan("台積電今天股價多少？")
    assert decision.needs_search is True
    assert len(decision.data_sources) == 1
    assert decision.data_sources[0].type == "fugle_quote"
    assert decision.data_sources[0].symbol == "2330"


@pytest.mark.asyncio
async def test_planner_empty_data_sources_for_non_tw_query(planner, mock_llm):
    mock_llm.chat.return_value = _mock_planner_response(True, "temporal")
    decision = await planner.plan("What is Apple stock price?")
    assert decision.data_sources == []
```

**Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/core/agents/test_planner.py::test_planner_outputs_data_sources_for_tw_stock -v`
Expected: FAIL — `data_sources` not in PlannerDecision (actually it passes because of Task 2, but the planner prompt doesn't instruct LLM to output it yet — the test validates the parsing works)

**Step 3: Update Planner prompt**

In `backend/app/core/agents/planner.py`, replace `PLANNER_SYSTEM_PROMPT`:

```python
PLANNER_SYSTEM_PROMPT = """You are a search planning agent. Your job is to analyze user queries and decide whether a web search is needed.

RULES:
1. Temporal questions (stock prices, news, exchange rates, weather, current events, scores, "today", "now", "latest") → MUST search
2. Factual questions where you are uncertain or the answer might have changed → search
3. Greetings, math, coding, creative writing, general knowledge you're confident about → no search
4. When searching, generate 1-3 precise search queries optimized for the user's language
5. TAIWAN STOCKS: When the query is about a Taiwan-listed stock (e.g. 台積電, 鴻海, 2330, 0050), add data_sources with the stock symbol. Use "fugle_quote" for current/today's price, "fugle_historical" for historical trends. Always also set needs_search=true for supplementary news.

Respond with ONLY valid JSON in this exact format:
{
  "needs_search": true/false,
  "reasoning": "brief explanation of your decision",
  "search_queries": ["query1", "query2"],
  "query_type": "temporal" | "factual" | "conversational",
  "data_sources": [{"type": "fugle_quote", "symbol": "2330"}]
}

data_sources is optional — omit or use [] when the query is NOT about Taiwan stocks."""
```

**Step 4: Run all planner tests**

Run: `cd backend && .venv/bin/python -m pytest tests/core/agents/test_planner.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/planner.py backend/tests/core/agents/test_planner.py
git commit -m "feat: extend planner prompt to output data_sources for TW stocks"
```

---

### Task 5: Integrate Fugle into ChatService

**Files:**
- Modify: `backend/app/core/services/chat_service.py`
- Modify: `backend/tests/core/services/test_chat_service.py`

**Step 1: Write failing test**

Add to `backend/tests/core/services/test_chat_service.py`:

```python
from app.core.models.schemas import FugleSource


@pytest.mark.asyncio
async def test_chat_with_fugle_and_tavily_parallel(chat_service):
    """When data_sources has Fugle entries, fetch Fugle + Tavily in parallel."""
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="Taiwan stock query",
        search_queries=["台積電 最新消息"],
        query_type="temporal",
        data_sources=[FugleSource(type="fugle_quote", symbol="2330")],
    )
    tavily_results = [
        SearchResult(
            title="TSMC News",
            url="https://example.com/tsmc",
            content="TSMC announces Q4 results",
            score=0.9,
        )
    ]

    async def mock_execute(message, search_results, history=None):
        assert len(search_results) >= 2  # Fugle + Tavily
        assert search_results[0].title.startswith("Fugle:")
        for chunk in ["台積電 ", "收盤 1,975 [1]"]:
            yield chunk

    with (
        patch.object(
            chat_service._planner, "plan",
            new_callable=AsyncMock, return_value=planner_decision,
        ),
        patch.object(
            chat_service._search, "search_multiple",
            new_callable=AsyncMock, return_value=tavily_results,
        ),
        patch.object(
            chat_service._executor, "execute", side_effect=mock_execute,
        ),
        patch.object(
            chat_service._executor, "build_citations",
            return_value=[],
        ),
        patch(
            "app.core.services.chat_service.FugleService",
        ) as MockFugle,
    ):
        mock_fugle_instance = MockFugle.return_value
        mock_fugle_instance.get_quote = AsyncMock(
            return_value="台積電(2330) 2026-03-03 即時報價：\n最新價 1,975 元"
        )
        # Re-create service with fugle
        chat_service._fugle = mock_fugle_instance

        events = []
        async for event in chat_service.process_message("台積電今天股價？"):
            events.append(event)

        mock_fugle_instance.get_quote.assert_called_once_with("2330")
        chunk_events = [e for e in events if isinstance(e, ChunkEvent)]
        assert len(chunk_events) == 2


@pytest.mark.asyncio
async def test_chat_without_fugle_key_skips_fugle(mock_llm):
    """When fugle_api_key is empty, skip Fugle even if data_sources present."""
    service = ChatService(llm=mock_llm, tavily_api_key="test-tavily", fugle_api_key="")
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="Taiwan stock",
        search_queries=["台積電"],
        query_type="temporal",
        data_sources=[FugleSource(type="fugle_quote", symbol="2330")],
    )

    async def mock_execute(*args, **kwargs):
        yield "answer"

    with (
        patch.object(service._planner, "plan", new_callable=AsyncMock, return_value=planner_decision),
        patch.object(service._search, "search_multiple", new_callable=AsyncMock, return_value=[]),
        patch.object(service._executor, "execute", side_effect=mock_execute),
        patch.object(service._executor, "build_citations", return_value=[]),
    ):
        events = []
        async for event in service.process_message("台積電股價？"):
            events.append(event)
        # Should complete without error, no Fugle call
        assert isinstance(events[-1], DoneEvent)
```

**Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/core/services/test_chat_service.py::test_chat_with_fugle_and_tavily_parallel -v`
Expected: FAIL

**Step 3: Modify ChatService**

Update `backend/app/core/services/chat_service.py`:

```python
import asyncio
import logging
import re
from collections.abc import AsyncGenerator

from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.services.llm_client import LLMClient
from app.core.services.search_service import SearchService
from app.core.services.fugle_service import FugleService
from app.core.models.schemas import SearchResult, FugleSource
from app.core.models.events import (
    ChatEvent,
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    SearchFailedEvent,
    DoneEvent,
)

logger = logging.getLogger(__name__)

_TEMPORAL_PATTERNS = re.compile(
    r"(股價|股票|新聞|匯率|天氣|比分|即時|最新|今[天日]|現在|目前|當前"
    r"|stock.?price|exchange.?rate|weather|score|latest|current|today|right\s?now"
    r"|news|headline|breaking)",
    re.IGNORECASE,
)


class ChatService:
    def __init__(
        self,
        llm: LLMClient,
        tavily_api_key: str,
        fugle_api_key: str = "",
    ):
        self._planner = PlannerAgent(llm=llm)
        self._executor = ExecutorAgent(llm=llm)
        self._search = SearchService(api_key=tavily_api_key)
        self._fugle = FugleService(api_key=fugle_api_key) if fugle_api_key else None

    async def _fetch_fugle(self, data_sources: list[FugleSource]) -> list[SearchResult]:
        if not self._fugle or not data_sources:
            return []

        results = []
        for src in data_sources:
            if src.type == "fugle_quote":
                text = await self._fugle.get_quote(src.symbol)
            elif src.type == "fugle_historical":
                text = await self._fugle.get_historical(src.symbol, src.timeframe or "D")
            else:
                continue

            if text:
                results.append(SearchResult(
                    title=f"Fugle: {src.symbol} {'即時報價' if src.type == 'fugle_quote' else '歷史股價'}",
                    url="",
                    content=text,
                    score=1.0,
                ))
        return results

    async def process_message(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[ChatEvent, None]:
        decision = await self._planner.plan(message, history)

        if not decision.needs_search and _TEMPORAL_PATTERNS.search(message):
            logger.info(f"Rule-based override: forcing search for '{message[:50]}'")
            decision.needs_search = True
            decision.query_type = "temporal"
            if not decision.search_queries:
                decision.search_queries = [message]

        yield PlannerEvent(
            needs_search=decision.needs_search,
            reasoning=decision.reasoning,
            search_queries=decision.search_queries,
            query_type=decision.query_type,
        )

        # Step 2: Fetch Fugle + Tavily in parallel
        search_results = []
        fugle_results = []

        if decision.needs_search and decision.search_queries:
            for query in decision.search_queries:
                yield SearchingEvent(query=query, status="searching")

            fugle_task = self._fetch_fugle(decision.data_sources)
            tavily_task = self._search.search_multiple(decision.search_queries)
            fugle_results, search_results = await asyncio.gather(fugle_task, tavily_task)

            for query in decision.search_queries:
                yield SearchingEvent(
                    query=query,
                    status="done",
                    results_count=len(search_results) + len(fugle_results),
                )
        elif decision.data_sources:
            # data_sources but no search queries (edge case)
            fugle_results = await self._fetch_fugle(decision.data_sources)

        all_results = fugle_results + search_results

        search_failed = decision.needs_search and not all_results
        if search_failed:
            logger.warning("Search returned 0 results for temporal query: '%s'", message[:80])
            yield SearchFailedEvent(
                message="Web search returned no results. The answer below may not reflect the latest information."
            )

        async for chunk in self._executor.execute(
            message=message,
            search_results=all_results,
            history=history,
        ):
            yield ChunkEvent(content=chunk)

        if all_results:
            citations = self._executor.build_citations(all_results)
            yield CitationsEvent(
                citations=[
                    {"index": c.index, "title": c.title, "url": c.url, "snippet": c.snippet}
                    for c in citations
                ]
            )

        yield DoneEvent()
```

**Step 4: Update ChatService constructor callers**

In `backend/app/web/routes/chat.py`, add `fugle_api_key=settings.fugle_api_key` to `ChatService(...)`.

In `backend/app/entrypoint.py`, add `fugle_api_key=settings.fugle_api_key` to `ChatService(...)`.

**Step 5: Run all tests**

Run: `cd backend && .venv/bin/python -m pytest -v --tb=short`
Expected: All tests PASS (135 existing + new ones)

**Step 6: Commit**

```bash
git add backend/app/core/services/chat_service.py backend/app/web/routes/chat.py backend/app/entrypoint.py backend/tests/core/services/test_chat_service.py
git commit -m "feat: integrate FugleService into ChatService with parallel fetch"
```

---

### Task 6: Update docs

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`

**Step 1: Update README.md**

- Tech Stack table: add `| Taiwan Stock Data | Fugle MarketData API |`
- Environment Variables table: add `| FUGLE_API_KEY | Fugle MarketData API key (for TW stock data) | No |`
- Known Limitations: update search source reliability row
- Test count: update to new count

**Step 2: Update docs/architecture.md**

- Add Fugle to system diagram
- Add to Key Design Decisions: `| Fugle for TW stocks | Tavily only | Exchange-grade data for Taiwan stocks; Tavily supplements with news/analysis |`

**Step 3: Commit**

```bash
git add README.md docs/architecture.md
git commit -m "docs: add Fugle integration to README and architecture"
```

---

### Task 7: Full test run and final verification

**Step 1: Run all backend tests**

Run: `cd backend && .venv/bin/python -m pytest -v --tb=short`
Expected: All tests PASS

**Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: 17 tests PASS

**Step 3: Verify test count in README matches actual**

Update README test count if needed.

**Step 4: Final commit if needed**

```bash
git add -A && git commit -m "fix: update test count"
```
