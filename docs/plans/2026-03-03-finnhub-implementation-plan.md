# Finnhub API Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate Finnhub API as a US/global stock and forex data source alongside Fugle (Taiwan stocks), with 10 endpoint types and Planner-driven smart routing.

**Architecture:** Extend the existing `data_sources` pattern in `PlannerDecision` with a new `FinnhubSource` union variant. A new `FinnhubService` wraps the sync `finnhub-python` SDK using `asyncio.to_thread()`. `ChatService._fetch_fugle()` is generalized to `_fetch_data_sources()` handling both Fugle and Finnhub in the same parallel-fetch loop.

**Tech Stack:** finnhub-python SDK, Pydantic, asyncio, pytest

**Design doc:** `docs/plans/2026-03-03-finnhub-integration-design.md`

---

## Task 1: Add finnhub-python dependency and config

**Files:**
- Modify: `backend/pyproject.toml:6-20` — add dependency
- Modify: `backend/app/core/config.py:12` — add `finnhub_api_key` field
- Modify: `backend/.env.example:17-19` — add env var

**Step 1: Add `finnhub-python` to dependencies**

In `backend/pyproject.toml`, add after the `"fugle-marketdata>=1.0.0"` line (line 19):

```toml
    "finnhub-python>=2.4.0",
```

**Step 2: Add `finnhub_api_key` to Settings**

In `backend/app/core/config.py`, add after `fugle_api_key: str = ""` (line 12):

```python
    finnhub_api_key: str = ""
```

**Step 3: Add env var to `.env.example`**

In `backend/.env.example`, add after the Fugle section (after line 19):

```bash

# Finnhub (US/global stock + forex data, optional)
# Get API key at https://finnhub.io
FINNHUB_API_KEY=
```

**Step 4: Install and verify**

Run:
```bash
cd backend && pip install -e ".[dev]"
python -c "import finnhub; print(finnhub.__version__)"
```
Expected: Version number printed (e.g., `2.4.27`)

**Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/core/config.py backend/.env.example
git commit -m "chore: add finnhub-python dependency and config"
```

---

## Task 2: Add FinnhubSource to data models

**Files:**
- Modify: `backend/app/core/models/schemas.py:15-26` — add FinnhubSource, update PlannerDecision
- Test: `backend/tests/core/agents/test_planner.py`

**Step 1: Write the failing test**

Add to `backend/tests/core/agents/test_planner.py`:

```python
@pytest.mark.asyncio
async def test_planner_outputs_finnhub_source_for_us_stock(planner, mock_llm):
    mock_llm.chat.return_value = json.dumps({
        "needs_search": True,
        "reasoning": "US stock price query",
        "search_queries": ["AAPL stock price"],
        "query_type": "temporal",
        "data_sources": [{"type": "finnhub_quote", "symbol": "AAPL"}],
    })
    decision = await planner.plan("What is Apple stock price?")
    assert decision.needs_search is True
    assert len(decision.data_sources) == 1
    assert decision.data_sources[0].type == "finnhub_quote"
    assert decision.data_sources[0].symbol == "AAPL"


@pytest.mark.asyncio
async def test_planner_outputs_finnhub_forex(planner, mock_llm):
    mock_llm.chat.return_value = json.dumps({
        "needs_search": True,
        "reasoning": "Forex rate query",
        "search_queries": ["USD TWD exchange rate"],
        "query_type": "temporal",
        "data_sources": [{"type": "finnhub_forex", "symbol": "USD"}],
    })
    decision = await planner.plan("美金換台幣匯率多少？")
    assert decision.data_sources[0].type == "finnhub_forex"
    assert decision.data_sources[0].symbol == "USD"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/core/agents/test_planner.py::test_planner_outputs_finnhub_source_for_us_stock -v`
Expected: FAIL — `ValidationError` because `finnhub_quote` doesn't match FugleSource pattern.

**Step 3: Add FinnhubSource and update PlannerDecision**

In `backend/app/core/models/schemas.py`, add **after** the `FugleSource` class (after line 18) and **before** `PlannerDecision`:

```python
class FinnhubSource(BaseModel):
    type: str = Field(
        ...,
        pattern="^(finnhub_quote|finnhub_candles|finnhub_forex|finnhub_profile|finnhub_financials|finnhub_news|finnhub_earnings|finnhub_price_target|finnhub_recommendation|finnhub_insider)$",
    )
    symbol: str = Field(..., min_length=1, max_length=20)
    timeframe: str | None = Field(None, pattern="^(1|5|15|30|60|D|W|M)$")
    from_date: str | None = None
    to_date: str | None = None
```

Then update `PlannerDecision.data_sources` field (currently line 26):

```python
    data_sources: list[FugleSource | FinnhubSource] = Field(default_factory=list)
```

Also add `FinnhubSource` to the module's exports/imports wherever `FugleSource` is exported.

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/core/agents/test_planner.py -v`
Expected: ALL PASS (including both new tests and all existing tests)

**Step 5: Commit**

```bash
git add backend/app/core/models/schemas.py backend/tests/core/agents/test_planner.py
git commit -m "feat: add FinnhubSource model and union type in PlannerDecision"
```

---

## Task 3: Create FinnhubService with all 10 endpoints

**Files:**
- Create: `backend/app/core/services/finnhub_service.py`
- Create: `backend/tests/core/services/test_finnhub_service.py`

This task follows the exact same pattern as `fugle_service.py`: sync SDK → `asyncio.to_thread()` → format to English text → return string (or `""` on error).

**Step 1: Write the failing tests**

Create `backend/tests/core/services/test_finnhub_service.py`:

```python
import pytest
from unittest.mock import patch, MagicMock

from app.core.services.finnhub_service import FinnhubService


@pytest.fixture
def finnhub():
    return FinnhubService(api_key="test-key")


# ---------- Mock response factories ----------

def _mock_quote():
    return {"c": 189.50, "d": 2.30, "dp": 1.23, "h": 190.15, "l": 187.20, "o": 187.50, "pc": 187.20, "t": 1709510400}


def _mock_profile():
    return {
        "name": "Apple Inc",
        "ticker": "AAPL",
        "finnhubIndustry": "Technology",
        "marketCapitalization": 2950000,
        "ipo": "1980-12-12",
        "country": "US",
        "exchange": "NASDAQ",
        "weburl": "https://www.apple.com",
    }


def _mock_candles():
    return {
        "s": "ok",
        "c": [190.0, 191.5],
        "h": [191.0, 192.0],
        "l": [188.0, 189.5],
        "o": [189.0, 190.0],
        "v": [45200000, 38100000],
        "t": [1709424000, 1709510400],
    }


def _mock_financials():
    return {
        "metric": {
            "peBasicExclExtraTTM": 29.5,
            "epsBasicExclExtraItemsTTM": 6.42,
            "dividendYieldIndicatedAnnual": 0.55,
            "52WeekHigh": 199.62,
            "52WeekLow": 164.08,
            "marketCapitalization": 2950000,
        },
        "metricType": "all",
        "symbol": "AAPL",
    }


def _mock_news():
    return [
        {
            "headline": "Apple announces new AI features",
            "datetime": 1709424000,
            "source": "Reuters",
            "url": "https://example.com/1",
            "summary": "Apple unveiled new AI capabilities.",
        },
        {
            "headline": "AAPL hits all-time high",
            "datetime": 1709337600,
            "source": "Bloomberg",
            "url": "https://example.com/2",
            "summary": "Apple stock reached record levels.",
        },
    ]


def _mock_earnings():
    return [
        {"actual": 2.10, "estimate": 2.05, "period": "2025-12-31", "quarter": 4, "year": 2025, "surprise": 0.05, "surprisePercent": 2.4390},
        {"actual": 1.95, "estimate": 1.90, "period": "2025-09-30", "quarter": 3, "year": 2025, "surprise": 0.05, "surprisePercent": 2.6316},
    ]


def _mock_price_target():
    return {"targetHigh": 250.0, "targetLow": 180.0, "targetMean": 215.0, "targetMedian": 218.0, "lastUpdated": "2026-03-01", "symbol": "AAPL"}


def _mock_recommendation():
    return [
        {"buy": 28, "hold": 7, "sell": 1, "strongBuy": 12, "strongSell": 0, "period": "2026-03-01", "symbol": "AAPL"},
    ]


def _mock_insider():
    return {
        "data": [
            {"name": "Tim Cook", "share": 100000, "change": -100000, "transactionDate": "2026-02-15", "transactionPrice": 189.50, "transactionCode": "S"},
        ],
        "symbol": "AAPL",
    }


def _mock_forex():
    return {"base": "USD", "quote": {"TWD": 32.15, "JPY": 149.80, "EUR": 0.92}}


# ---------- Format tests ----------

class TestFormatMethods:
    def test_format_quote(self, finnhub):
        result = finnhub.format_quote(_mock_quote(), "AAPL")
        assert "189.5" in result
        assert "+2.3" in result or "2.30" in result
        assert "AAPL" in result

    def test_format_quote_negative(self, finnhub):
        data = {"c": 185.0, "d": -2.50, "dp": -1.33, "h": 188.0, "l": 184.5, "o": 187.5, "pc": 187.50, "t": 1709510400}
        result = finnhub.format_quote(data, "AAPL")
        assert "185" in result
        assert "-2.5" in result or "-2.50" in result

    def test_format_profile(self, finnhub):
        result = finnhub.format_profile(_mock_profile())
        assert "Apple Inc" in result
        assert "AAPL" in result
        assert "Technology" in result

    def test_format_candles(self, finnhub):
        result = finnhub.format_candles(_mock_candles(), "AAPL")
        assert "AAPL" in result
        assert "190" in result

    def test_format_candles_no_data(self, finnhub):
        result = finnhub.format_candles({"s": "no_data"}, "AAPL")
        assert result == ""

    def test_format_financials(self, finnhub):
        result = finnhub.format_financials(_mock_financials(), "AAPL")
        assert "29.5" in result  # P/E
        assert "6.42" in result  # EPS
        assert "AAPL" in result

    def test_format_news(self, finnhub):
        result = finnhub.format_news(_mock_news())
        assert "Apple announces new AI features" in result
        assert "AAPL hits all-time high" in result

    def test_format_news_empty(self, finnhub):
        result = finnhub.format_news([])
        assert result == ""

    def test_format_earnings(self, finnhub):
        result = finnhub.format_earnings(_mock_earnings(), "AAPL")
        assert "2.10" in result or "2.1" in result
        assert "AAPL" in result

    def test_format_price_target(self, finnhub):
        result = finnhub.format_price_target(_mock_price_target(), "AAPL")
        assert "250" in result  # high
        assert "180" in result  # low
        assert "215" in result  # mean

    def test_format_recommendation(self, finnhub):
        result = finnhub.format_recommendation(_mock_recommendation(), "AAPL")
        assert "Buy" in result or "buy" in result.lower()
        assert "28" in result

    def test_format_insider(self, finnhub):
        result = finnhub.format_insider(_mock_insider(), "AAPL")
        assert "Tim Cook" in result
        assert "100,000" in result or "100000" in result

    def test_format_forex(self, finnhub):
        result = finnhub.format_forex_rates(_mock_forex(), "USD")
        assert "TWD" in result
        assert "32.15" in result


# ---------- Async get_* tests ----------

class TestAsyncMethods:
    @pytest.mark.asyncio
    async def test_get_quote(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.quote.return_value = _mock_quote()
            result = await finnhub.get_quote("AAPL")
            assert "AAPL" in result
            assert "189.5" in result
            mock_client.quote.assert_called_once_with(symbol="AAPL")

    @pytest.mark.asyncio
    async def test_get_quote_error(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.quote.side_effect = Exception("API error")
            result = await finnhub.get_quote("AAPL")
            assert result == ""

    @pytest.mark.asyncio
    async def test_get_candles(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.stock_candles.return_value = _mock_candles()
            result = await finnhub.get_candles("AAPL", "D")
            assert "AAPL" in result
            mock_client.stock_candles.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_profile(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.company_profile2.return_value = _mock_profile()
            result = await finnhub.get_profile("AAPL")
            assert "Apple Inc" in result

    @pytest.mark.asyncio
    async def test_get_financials(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.company_basic_financials.return_value = _mock_financials()
            result = await finnhub.get_financials("AAPL")
            assert "29.5" in result

    @pytest.mark.asyncio
    async def test_get_news(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.company_news.return_value = _mock_news()
            result = await finnhub.get_news("AAPL")
            assert "Apple announces" in result

    @pytest.mark.asyncio
    async def test_get_earnings(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.company_earnings.return_value = _mock_earnings()
            result = await finnhub.get_earnings("AAPL")
            assert "AAPL" in result

    @pytest.mark.asyncio
    async def test_get_price_target(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.price_target.return_value = _mock_price_target()
            result = await finnhub.get_price_target("AAPL")
            assert "250" in result

    @pytest.mark.asyncio
    async def test_get_recommendation(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.recommendation_trends.return_value = _mock_recommendation()
            result = await finnhub.get_recommendation("AAPL")
            assert "28" in result

    @pytest.mark.asyncio
    async def test_get_insider(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.stock_insider_transactions.return_value = _mock_insider()
            result = await finnhub.get_insider("AAPL")
            assert "Tim Cook" in result

    @pytest.mark.asyncio
    async def test_get_forex(self, finnhub):
        with patch.object(finnhub, "_client") as mock_client:
            mock_client.forex_rates.return_value = _mock_forex()
            result = await finnhub.get_forex_rates("USD")
            assert "TWD" in result
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/core/services/test_finnhub_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.services.finnhub_service'`

**Step 3: Implement FinnhubService**

Create `backend/app/core/services/finnhub_service.py`:

```python
"""Finnhub API service — US/global stock and forex data."""

import asyncio
import logging
from datetime import datetime, timedelta

import finnhub

logger = logging.getLogger(__name__)


class FinnhubService:
    def __init__(self, api_key: str):
        self._client = finnhub.Client(api_key=api_key)

    # ── Async methods (wrap sync SDK) ──────────────────────────

    async def get_quote(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(self._client.quote, symbol=symbol)
            return self.format_quote(data, symbol)
        except Exception as e:
            logger.warning("Finnhub quote failed for %s: %s", symbol, e)
            return ""

    async def get_candles(
        self, symbol: str, timeframe: str = "D",
        from_date: str | None = None, to_date: str | None = None,
    ) -> str:
        try:
            now = datetime.now()
            to_ts = int(datetime.strptime(to_date, "%Y-%m-%d").timestamp()) if to_date else int(now.timestamp())
            from_ts = int(datetime.strptime(from_date, "%Y-%m-%d").timestamp()) if from_date else int((now - timedelta(days=90)).timestamp())
            data = await asyncio.to_thread(
                self._client.stock_candles, symbol, timeframe, from_ts, to_ts,
            )
            return self.format_candles(data, symbol)
        except Exception as e:
            logger.warning("Finnhub candles failed for %s: %s", symbol, e)
            return ""

    async def get_forex_rates(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(self._client.forex_rates, base=symbol)
            return self.format_forex_rates(data, symbol)
        except Exception as e:
            logger.warning("Finnhub forex failed for %s: %s", symbol, e)
            return ""

    async def get_profile(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(self._client.company_profile2, symbol=symbol)
            return self.format_profile(data)
        except Exception as e:
            logger.warning("Finnhub profile failed for %s: %s", symbol, e)
            return ""

    async def get_financials(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(
                self._client.company_basic_financials, symbol, "all",
            )
            return self.format_financials(data, symbol)
        except Exception as e:
            logger.warning("Finnhub financials failed for %s: %s", symbol, e)
            return ""

    async def get_news(
        self, symbol: str,
        from_date: str | None = None, to_date: str | None = None,
    ) -> str:
        try:
            now = datetime.now()
            _to = to_date or now.strftime("%Y-%m-%d")
            _from = from_date or (now - timedelta(days=7)).strftime("%Y-%m-%d")
            data = await asyncio.to_thread(
                self._client.company_news, symbol, _from=_from, _to=_to,
            )
            return self.format_news(data)
        except Exception as e:
            logger.warning("Finnhub news failed for %s: %s", symbol, e)
            return ""

    async def get_earnings(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(
                self._client.company_earnings, symbol, limit=4,
            )
            return self.format_earnings(data, symbol)
        except Exception as e:
            logger.warning("Finnhub earnings failed for %s: %s", symbol, e)
            return ""

    async def get_price_target(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(self._client.price_target, symbol)
            return self.format_price_target(data, symbol)
        except Exception as e:
            logger.warning("Finnhub price_target failed for %s: %s", symbol, e)
            return ""

    async def get_recommendation(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(self._client.recommendation_trends, symbol)
            return self.format_recommendation(data, symbol)
        except Exception as e:
            logger.warning("Finnhub recommendation failed for %s: %s", symbol, e)
            return ""

    async def get_insider(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(
                self._client.stock_insider_transactions, symbol=symbol,
            )
            return self.format_insider(data, symbol)
        except Exception as e:
            logger.warning("Finnhub insider failed for %s: %s", symbol, e)
            return ""

    # ── Format methods (dict → human-readable English) ─────────

    def format_quote(self, data: dict, symbol: str) -> str:
        c = data.get("c", 0)
        d = data.get("d", 0)
        dp = data.get("dp", 0)
        h = data.get("h", 0)
        l = data.get("l", 0)
        o = data.get("o", 0)
        sign = "+" if d >= 0 else ""
        return (
            f"{symbol} — Current: ${c:,.2f}, Change: {sign}{d:,.2f} ({sign}{dp:.2f}%), "
            f"Day Range: ${l:,.2f}–${h:,.2f}, Open: ${o:,.2f}"
        )

    def format_candles(self, data: dict, symbol: str) -> str:
        if data.get("s") != "ok":
            return ""
        closes = data.get("c", [])
        highs = data.get("h", [])
        lows = data.get("l", [])
        opens = data.get("o", [])
        volumes = data.get("v", [])
        timestamps = data.get("t", [])
        lines = [f"{symbol} Historical:"]
        for i in range(min(len(closes), 20)):
            date = datetime.fromtimestamp(timestamps[i]).strftime("%Y-%m-%d")
            vol = f"{volumes[i]/1_000_000:.1f}M" if volumes[i] >= 1_000_000 else f"{volumes[i]:,}"
            lines.append(
                f"  {date} O:{opens[i]:.2f} H:{highs[i]:.2f} L:{lows[i]:.2f} C:{closes[i]:.2f} V:{vol}"
            )
        return "\n".join(lines)

    def format_forex_rates(self, data: dict, base: str) -> str:
        quote = data.get("quote", {})
        if not quote:
            return ""
        lines = [f"Exchange Rates (base: {base}):"]
        for currency, rate in sorted(quote.items()):
            lines.append(f"  {currency}: {rate}")
        return "\n".join(lines)

    def format_profile(self, data: dict) -> str:
        if not data:
            return ""
        name = data.get("name", "")
        ticker = data.get("ticker", "")
        industry = data.get("finnhubIndustry", "")
        mcap = data.get("marketCapitalization", 0)
        ipo = data.get("ipo", "")
        country = data.get("country", "")
        exchange = data.get("exchange", "")
        mcap_str = f"${mcap/1000:.2f}B" if mcap >= 1000 else f"${mcap:.0f}M"
        return (
            f"{name} ({ticker}) — Industry: {industry}, "
            f"Market Cap: {mcap_str}, IPO: {ipo}, "
            f"Country: {country}, Exchange: {exchange}"
        )

    def format_financials(self, data: dict, symbol: str) -> str:
        m = data.get("metric", {})
        if not m:
            return ""
        pe = m.get("peBasicExclExtraTTM", "N/A")
        eps = m.get("epsBasicExclExtraItemsTTM", "N/A")
        div_yield = m.get("dividendYieldIndicatedAnnual", "N/A")
        high_52 = m.get("52WeekHigh", "N/A")
        low_52 = m.get("52WeekLow", "N/A")
        mcap = m.get("marketCapitalization", "N/A")
        return (
            f"{symbol} Financials — P/E: {pe}, EPS (TTM): {eps}, "
            f"Dividend Yield: {div_yield}%, 52W High: ${high_52}, 52W Low: ${low_52}"
        )

    def format_news(self, articles: list) -> str:
        if not articles:
            return ""
        lines = ["Recent News:"]
        for i, a in enumerate(articles[:5], 1):
            headline = a.get("headline", "")
            ts = a.get("datetime", 0)
            date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""
            source = a.get("source", "")
            lines.append(f"  {i}. {headline} ({source}, {date})")
        return "\n".join(lines)

    def format_earnings(self, data: list, symbol: str) -> str:
        if not data:
            return ""
        lines = [f"{symbol} Earnings:"]
        for e in data[:4]:
            period = e.get("period", "")
            actual = e.get("actual", "N/A")
            estimate = e.get("estimate", "N/A")
            surprise_pct = e.get("surprisePercent", 0)
            sign = "+" if surprise_pct >= 0 else ""
            lines.append(
                f"  {period}: EPS ${actual} (est ${estimate}, surprise {sign}{surprise_pct:.1f}%)"
            )
        return "\n".join(lines)

    def format_price_target(self, data: dict, symbol: str) -> str:
        high = data.get("targetHigh", "N/A")
        low = data.get("targetLow", "N/A")
        mean = data.get("targetMean", "N/A")
        median = data.get("targetMedian", "N/A")
        return (
            f"{symbol} Price Target — High: ${high}, Low: ${low}, "
            f"Mean: ${mean}, Median: ${median}"
        )

    def format_recommendation(self, data: list, symbol: str) -> str:
        if not data:
            return ""
        r = data[0]
        period = r.get("period", "")
        return (
            f"{symbol} Analyst Consensus ({period}): "
            f"Strong Buy: {r.get('strongBuy', 0)}, Buy: {r.get('buy', 0)}, "
            f"Hold: {r.get('hold', 0)}, Sell: {r.get('sell', 0)}, "
            f"Strong Sell: {r.get('strongSell', 0)}"
        )

    def format_insider(self, data: dict, symbol: str) -> str:
        transactions = data.get("data", [])
        if not transactions:
            return ""
        lines = [f"{symbol} Insider Transactions:"]
        for t in transactions[:5]:
            name = t.get("name", "Unknown")
            shares = abs(t.get("change", 0))
            price = t.get("transactionPrice", 0)
            date = t.get("transactionDate", "")
            code = t.get("transactionCode", "")
            action = "sold" if code in ("S", "S-Sale") else "bought"
            lines.append(f"  {name} {action} {shares:,.0f} shares at ${price:,.2f} ({date})")
        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/core/services/test_finnhub_service.py -v`
Expected: ALL PASS (~25 tests)

**Step 5: Run full test suite**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: ALL existing tests still pass

**Step 6: Commit**

```bash
git add backend/app/core/services/finnhub_service.py backend/tests/core/services/test_finnhub_service.py
git commit -m "feat: create FinnhubService with 10 endpoints and tests"
```

---

## Task 4: Extend Planner prompt with rule 6 for US/global stocks

**Files:**
- Modify: `backend/app/core/agents/planner.py:9-27` — add rule 6, update JSON format
- Test: `backend/tests/core/agents/test_planner.py`

**Step 1: Write the failing test**

The tests from Task 2 already verify parsing. Now add a test that validates the prompt includes Finnhub guidance (this is a prompt content test):

```python
def test_planner_prompt_contains_finnhub_instructions():
    from app.core.agents.planner import PLANNER_SYSTEM_PROMPT
    assert "finnhub_quote" in PLANNER_SYSTEM_PROMPT
    assert "finnhub_forex" in PLANNER_SYSTEM_PROMPT
    assert "finnhub_candles" in PLANNER_SYSTEM_PROMPT
```

Add this to `backend/tests/core/agents/test_planner.py`.

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/core/agents/test_planner.py::test_planner_prompt_contains_finnhub_instructions -v`
Expected: FAIL — `AssertionError`

**Step 3: Extend PLANNER_SYSTEM_PROMPT**

In `backend/app/core/agents/planner.py`, locate the system prompt (lines 9–27). Add rule 6 **after** rule 5 (Taiwan stocks) and **before** the JSON format block:

```
6. NON-TAIWAN STOCKS & FOREX: For US/international stocks (AAPL, MSFT, TSLA, GOOGL)
   or forex pairs (USD/TWD, EUR/USD), use finnhub_* types in data_sources.
   Choose endpoints based on what the user asks:
   - Price/quote → finnhub_quote
   - Historical trend/chart → finnhub_candles (set timeframe: D/W/M, from_date, to_date)
   - Exchange rate → finnhub_forex (symbol = base currency, e.g. "USD")
   - Company info → finnhub_profile
   - Financial metrics (P/E, EPS) → finnhub_financials
   - Recent news → finnhub_news
   - Earnings history → finnhub_earnings
   - Analyst targets → finnhub_price_target
   - Buy/sell consensus → finnhub_recommendation
   - Insider trading → finnhub_insider
   Always also set needs_search=true for supplementary context.
```

Also update the JSON format block to show `FinnhubSource` example:

```
data_sources is optional — use [] when the query is NOT about stocks/forex.
Taiwan stocks → fugle_quote/fugle_historical. US/global/forex → finnhub_* types.
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/core/agents/test_planner.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/planner.py backend/tests/core/agents/test_planner.py
git commit -m "feat: extend planner prompt with Finnhub routing rules"
```

---

## Task 5: Integrate Finnhub into ChatService

**Files:**
- Modify: `backend/app/core/services/chat_service.py:34-140` — refactor `_fetch_fugle` → `_fetch_data_sources`, add `finnhub_api_key` param
- Modify: `backend/app/web/routes/chat.py:31-36` — pass `finnhub_api_key`
- Modify: `backend/app/entrypoint.py:37-41` — pass `finnhub_api_key`
- Test: `backend/tests/core/services/test_chat_service.py`

**Step 1: Write the failing tests**

Add to `backend/tests/core/services/test_chat_service.py`:

```python
@pytest.mark.asyncio
async def test_chat_with_finnhub_and_tavily_parallel(mock_llm):
    """When data_sources has Finnhub entries, fetch Finnhub + Tavily in parallel."""
    from app.core.models.schemas import FinnhubSource
    from unittest.mock import MagicMock

    service = ChatService(llm=mock_llm, tavily_api_key="test-tavily", finnhub_api_key="test-finnhub")
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="US stock query",
        search_queries=["AAPL stock news"],
        query_type="temporal",
        data_sources=[FinnhubSource(type="finnhub_quote", symbol="AAPL")],
    )
    tavily_results = [
        SearchResult(
            title="Apple News",
            url="https://example.com/aapl",
            content="Apple stock rises",
            score=0.9,
        )
    ]

    async def mock_execute(message, search_results, history=None):
        assert len(search_results) >= 2  # Finnhub + Tavily
        assert search_results[0].title.startswith("Finnhub:")
        for chunk in ["AAPL ", "is $189.50 [1]"]:
            yield chunk

    with (
        patch.object(service._planner, "plan", new_callable=AsyncMock, return_value=planner_decision),
        patch.object(service._search, "search_multiple", new_callable=AsyncMock, return_value=tavily_results),
        patch.object(service._executor, "execute", side_effect=mock_execute),
        patch.object(service._executor, "build_citations", return_value=[]),
    ):
        service._finnhub = MagicMock()
        service._finnhub.get_quote = AsyncMock(return_value="AAPL — Current: $189.50, Change: +2.30 (+1.23%)")

        events = []
        async for event in service.process_message("Apple stock price?"):
            events.append(event)

        service._finnhub.get_quote.assert_called_once_with("AAPL")
        chunk_events = [e for e in events if isinstance(e, ChunkEvent)]
        assert len(chunk_events) == 2


@pytest.mark.asyncio
async def test_chat_without_finnhub_key_skips_finnhub(mock_llm):
    """When finnhub_api_key is empty, skip Finnhub even if data_sources present."""
    from app.core.models.schemas import FinnhubSource

    service = ChatService(llm=mock_llm, tavily_api_key="test-tavily", finnhub_api_key="")
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="US stock",
        search_queries=["AAPL"],
        query_type="temporal",
        data_sources=[FinnhubSource(type="finnhub_quote", symbol="AAPL")],
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
        async for event in service.process_message("AAPL?"):
            events.append(event)
        assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_chat_with_fugle_and_finnhub_and_tavily(mock_llm):
    """Triple parallel: Fugle + Finnhub + Tavily."""
    from app.core.models.schemas import FinnhubSource
    from unittest.mock import MagicMock

    service = ChatService(
        llm=mock_llm, tavily_api_key="test-tavily",
        fugle_api_key="test-fugle", finnhub_api_key="test-finnhub",
    )
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="Compare TW and US stocks",
        search_queries=["TSMC vs AAPL"],
        query_type="temporal",
        data_sources=[
            FugleSource(type="fugle_quote", symbol="2330"),
            FinnhubSource(type="finnhub_quote", symbol="AAPL"),
        ],
    )

    async def mock_execute(message, search_results, history=None):
        # Fugle first, then Finnhub, then Tavily
        assert len(search_results) >= 3
        for chunk in ["comparison"]:
            yield chunk

    with (
        patch.object(service._planner, "plan", new_callable=AsyncMock, return_value=planner_decision),
        patch.object(service._search, "search_multiple", new_callable=AsyncMock, return_value=[
            SearchResult(title="Compare", url="https://example.com", content="comparison", score=0.9),
        ]),
        patch.object(service._executor, "execute", side_effect=mock_execute),
        patch.object(service._executor, "build_citations", return_value=[]),
    ):
        service._fugle = MagicMock()
        service._fugle.get_quote = AsyncMock(return_value="台積電(2330) 最新價 1,975 元")
        service._finnhub = MagicMock()
        service._finnhub.get_quote = AsyncMock(return_value="AAPL — Current: $189.50")

        events = []
        async for event in service.process_message("台積電 vs Apple"):
            events.append(event)

        service._fugle.get_quote.assert_called_once_with("2330")
        service._finnhub.get_quote.assert_called_once_with("AAPL")
        assert isinstance(events[-1], DoneEvent)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/core/services/test_chat_service.py::test_chat_with_finnhub_and_tavily_parallel -v`
Expected: FAIL — `ChatService.__init__() got unexpected keyword argument 'finnhub_api_key'`

**Step 3: Refactor ChatService**

In `backend/app/core/services/chat_service.py`:

**3a. Update imports** — add at top:
```python
from app.core.services.finnhub_service import FinnhubService
from app.core.models.schemas import FinnhubSource
```

(Keep existing FugleSource import.)

**3b. Update constructor** — add `finnhub_api_key` param after `fugle_api_key`:
```python
def __init__(
    self, llm: LLMClient, tavily_api_key: str,
    fugle_api_key: str = "", finnhub_api_key: str = "",
):
    ...
    self._fugle = FugleService(api_key=fugle_api_key) if fugle_api_key else None
    self._finnhub = FinnhubService(api_key=finnhub_api_key) if finnhub_api_key else None
```

**3c. Rename `_fetch_fugle` → `_fetch_data_sources`** and handle both types:

```python
async def _fetch_data_sources(
    self, data_sources: list[FugleSource | FinnhubSource],
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
            provider = "Fugle" if isinstance(src, FugleSource) else "Finnhub"
            results.append(SearchResult(
                title=f"{provider}: {src.symbol} {src.type}",
                url="",
                content=text,
                score=1.0,
            ))
    return results

async def _dispatch_finnhub(self, src: FinnhubSource) -> str:
    dispatch = {
        "finnhub_quote": lambda: self._finnhub.get_quote(src.symbol),
        "finnhub_candles": lambda: self._finnhub.get_candles(src.symbol, src.timeframe or "D", src.from_date, src.to_date),
        "finnhub_forex": lambda: self._finnhub.get_forex_rates(src.symbol),
        "finnhub_profile": lambda: self._finnhub.get_profile(src.symbol),
        "finnhub_financials": lambda: self._finnhub.get_financials(src.symbol),
        "finnhub_news": lambda: self._finnhub.get_news(src.symbol, src.from_date, src.to_date),
        "finnhub_earnings": lambda: self._finnhub.get_earnings(src.symbol),
        "finnhub_price_target": lambda: self._finnhub.get_price_target(src.symbol),
        "finnhub_recommendation": lambda: self._finnhub.get_recommendation(src.symbol),
        "finnhub_insider": lambda: self._finnhub.get_insider(src.symbol),
    }
    handler = dispatch.get(src.type)
    if handler:
        return await handler()
    return ""
```

**3d. Update `process_message`** — replace the `fugle_task` line:

```python
# Before:
fugle_task = self._fetch_fugle(decision.data_sources)
# After:
data_task = self._fetch_data_sources(decision.data_sources)
```

And update the `asyncio.gather` line:

```python
# Before:
fugle_results, search_results = await asyncio.gather(fugle_task, tavily_task)
# After:
data_results, search_results = await asyncio.gather(data_task, tavily_task)
```

And update the merge line:

```python
# Before:
all_results = fugle_results + search_results
# After:
all_results = data_results + search_results
```

**3e. Update routes and entrypoint**

In `backend/app/web/routes/chat.py`, update `get_chat_service()`:

```python
def get_chat_service() -> ChatService:
    return ChatService(
        llm=create_llm_client(settings),
        tavily_api_key=settings.tavily_api_key,
        fugle_api_key=settings.fugle_api_key,
        finnhub_api_key=settings.finnhub_api_key,
    )
```

In `backend/app/entrypoint.py`, update `start_telegram()` ChatService creation:

```python
chat_service = ChatService(
    llm=create_llm_client(settings),
    tavily_api_key=settings.tavily_api_key,
    fugle_api_key=settings.fugle_api_key,
    finnhub_api_key=settings.finnhub_api_key,
)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/core/services/test_chat_service.py -v`
Expected: ALL PASS (including 3 new Finnhub tests and all existing Fugle tests)

**Step 5: Run full test suite**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/core/services/chat_service.py backend/app/web/routes/chat.py backend/app/entrypoint.py backend/tests/core/services/test_chat_service.py
git commit -m "feat: integrate FinnhubService into ChatService with parallel fetch"
```

---

## Task 6: Add Finnhub E2E test

**Files:**
- Modify: `backend/tests/e2e/test_chat_e2e.py` — add Finnhub E2E test

**Step 1: Write the E2E test**

Add a new `CONV_ID_5` at top and add test to `TestChatE2E`:

```python
CONV_ID_5 = "e5f6a7b8-c9d0-1234-efab-345678901234"
```

```python
async def test_full_chat_flow_with_finnhub_and_tavily(self, client, storage):
    """
    Scenario: User asks about US stock → Planner outputs finnhub data_sources
    → Finnhub + Tavily fetched in parallel → Executor streams answer → DB persists.
    Finnhub results have url="" (excluded from citations).
    """
    from app.core.models.schemas import FinnhubSource

    conv_response = await client.post(
        "/api/conversations",
        json={"id": CONV_ID_5, "title": "Apple Stock"},
    )
    assert conv_response.status_code == 200

    mock_planner = AsyncMock(return_value=PlannerDecision(
        needs_search=True,
        reasoning="US stock price query — need Finnhub + web search",
        search_queries=["AAPL stock latest"],
        query_type="temporal",
        data_sources=[FinnhubSource(type="finnhub_quote", symbol="AAPL")],
    ))

    mock_search = AsyncMock(return_value=[
        SearchResult(
            title="Apple Stock Analysis",
            url="https://news.example.com/aapl",
            content="Apple stock surges on AI news.",
            score=0.90,
        ),
    ])

    mock_finnhub_quote = AsyncMock(
        return_value="AAPL — Current: $189.50, Change: +2.30 (+1.23%), Day Range: $187.20–$190.15"
    )

    async def mock_execute(message, search_results, history=None):
        assert len(search_results) == 2
        assert search_results[0].title.startswith("Finnhub:")
        assert search_results[0].url == ""
        assert "189.50" in search_results[0].content
        assert search_results[1].url == "https://news.example.com/aapl"
        for chunk in [
            "Apple (AAPL) is currently trading at ",
            "**$189.50** [1], ",
            "up 1.23% today. Recent AI news boosts sentiment [2].",
        ]:
            yield chunk

    with (
        patch(
            "app.core.config.settings.finnhub_api_key",
            "test-finnhub-key",
        ),
        patch(
            "app.core.agents.planner.PlannerAgent.plan",
            mock_planner,
        ),
        patch(
            "app.core.services.search_service.SearchService.search_multiple",
            mock_search,
        ),
        patch(
            "app.core.agents.executor.ExecutorAgent.execute",
            side_effect=mock_execute,
        ),
        patch(
            "app.core.services.finnhub_service.FinnhubService.get_quote",
            mock_finnhub_quote,
        ),
    ):
        response = await client.post(
            "/api/chat",
            json={
                "message": "What is Apple stock price today?",
                "conversation_id": CONV_ID_5,
                "history": [],
            },
        )

    assert response.status_code == 200

    events = _parse_sse_events(response.text)
    event_types = [e["event"] for e in events]

    assert events[0]["data"]["needs_search"] is True
    assert "searching" in event_types

    chunks = [e["data"]["content"] for e in events if e["event"] == "chunk"]
    full_content = "".join(chunks)
    assert "189.50" in full_content
    assert "[1]" in full_content
    assert "[2]" in full_content

    # Citations: only Tavily (Finnhub has url="")
    citation_events = [e for e in events if e["event"] == "citations"]
    assert len(citation_events) == 1
    citations = citation_events[0]["data"]["citations"]
    assert len(citations) == 1
    assert citations[0]["url"] == "https://news.example.com/aapl"

    assert event_types[-1] == "done"

    messages = await storage.get_messages(CONV_ID_5)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert "189.50" in messages[1]["content"]
    assert messages[1]["search_used"]
```

**Step 2: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/e2e/test_chat_e2e.py::TestChatE2E::test_full_chat_flow_with_finnhub_and_tavily -v`
Expected: PASS (since service code is already implemented in Task 5)

**Step 3: Run full test suite**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/tests/e2e/test_chat_e2e.py
git commit -m "test: add Finnhub E2E integration test"
```

---

## Task 7: Update docs

**Files:**
- Modify: `README.md` — tech stack, env vars, test count, architecture diagram
- Modify: `docs/architecture.md` — add Finnhub to diagrams and design decisions

**Step 1: Update README.md**

Make these changes:

**Architecture diagram** — add `Finnhub` next to `Fugle`:
```
          Data Sources
        ┌─────┴──────┐
    Search Service  Fugle    Finnhub
    (Tavily API)  Service   Service
```

**Tech stack table** — add row:
```
| US/Global Stock Data | Finnhub API |
```

**Prerequisites** — add:
```
- Finnhub API key (optional, for US/global stock + forex data: https://finnhub.io)
```

**Environment Variables table** — add:
```
| `FINNHUB_API_KEY` | Finnhub API key (for US/global stock + forex data) | No |
```

**Known Limitations** — update search source reliability mitigation to mention Finnhub.

**Test count** — update from `153` to the new count (run `pytest` to count).

**Step 2: Update `docs/architecture.md`**

Add a row to design decisions:
```
| Finnhub API | Alpha Vantage, Yahoo Finance | Free tier with 60 calls/min, comprehensive endpoints (quote, candles, forex, financials, news, earnings, price target, recommendation, insider), official Python SDK |
```

Add Finnhub to the system diagram alongside Fugle.

**Step 3: Run full test suite to get final count**

Run: `cd backend && python -m pytest -v --tb=short 2>&1 | tail -5`

**Step 4: Commit**

```bash
git add README.md docs/architecture.md
git commit -m "docs: add Finnhub integration to README and architecture"
```

---

## Task 8: Final verification

**Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: ALL PASS (should be ~180+ tests)

**Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: 17 tests pass (no frontend changes)

**Step 3: Run coverage check**

Run: `cd backend && python -m pytest --cov=app --cov-report=term-missing --tb=short 2>&1 | tail -30`
Expected: finnhub_service.py ≥95%, chat_service.py ≥85%

**Step 4: Verify import chain**

Run: `cd backend && python -c "from app.core.services.finnhub_service import FinnhubService; print('OK')"`
Expected: `OK`

**Step 5: Verify graceful degradation (no API key)**

Run: `cd backend && python -c "from app.core.config import settings; print('finnhub:', repr(settings.finnhub_api_key))"`
Expected: `finnhub: ''`
