"""Finnhub API service — US/global stock and forex data."""

import asyncio
import logging
from datetime import datetime, timedelta

import finnhub
import httpx

logger = logging.getLogger(__name__)


class FinnhubService:
    def __init__(self, api_key: str):
        self._client = finnhub.Client(api_key=api_key)

    # ------------------------------------------------------------------
    # Async get_* methods
    # ------------------------------------------------------------------

    async def get_quote(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(self._client.quote, symbol=symbol)
            return self.format_quote(data, symbol)
        except Exception as e:
            logger.warning("Finnhub quote failed for %s: %s", symbol, e)
            return ""

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "D",
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> str:
        try:
            now = datetime.now()
            if to_date is None:
                to_date = now
            if from_date is None:
                from_date = now - timedelta(days=90)
            from_ts = int(from_date.timestamp())
            to_ts = int(to_date.timestamp())
            data = await asyncio.to_thread(
                self._client.stock_candles, symbol, timeframe, from_ts, to_ts
            )
            return self.format_candles(data, symbol)
        except Exception as e:
            logger.warning("Finnhub candles failed for %s: %s", symbol, e)
            return ""

    async def get_forex_rates(self, symbol: str) -> str:
        """Fetch exchange rates from tw.rter.info (free, no API key needed)."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://tw.rter.info/capi.php")
                resp.raise_for_status()
                data = resp.json()
            return self.format_forex_rates(data, symbol)
        except Exception as e:
            logger.warning("Forex rates failed for %s: %s", symbol, e)
            return ""

    async def get_profile(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(
                self._client.company_profile2, symbol=symbol
            )
            return self.format_profile(data)
        except Exception as e:
            logger.warning("Finnhub profile failed for %s: %s", symbol, e)
            return ""

    async def get_financials(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(
                self._client.company_basic_financials, symbol, "all"
            )
            return self.format_financials(data, symbol)
        except Exception as e:
            logger.warning("Finnhub financials failed for %s: %s", symbol, e)
            return ""

    async def get_news(
        self,
        symbol: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> str:
        try:
            now = datetime.now()
            if to_date is None:
                to_date = now.strftime("%Y-%m-%d")
            if from_date is None:
                from_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            data = await asyncio.to_thread(
                self._client.company_news, symbol, _from=from_date, _to=to_date
            )
            return self.format_news(data)
        except Exception as e:
            logger.warning("Finnhub news failed for %s: %s", symbol, e)
            return ""

    async def get_earnings(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(
                self._client.company_earnings, symbol, limit=4
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
            logger.warning("Finnhub price target failed for %s: %s", symbol, e)
            return ""

    async def get_recommendation(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(
                self._client.recommendation_trends, symbol
            )
            return self.format_recommendation(data, symbol)
        except Exception as e:
            logger.warning("Finnhub recommendation failed for %s: %s", symbol, e)
            return ""

    async def get_insider(self, symbol: str) -> str:
        try:
            data = await asyncio.to_thread(
                self._client.stock_insider_transactions, symbol=symbol
            )
            return self.format_insider(data, symbol)
        except Exception as e:
            logger.warning("Finnhub insider failed for %s: %s", symbol, e)
            return ""

    # ------------------------------------------------------------------
    # Format methods — return English text
    # ------------------------------------------------------------------

    def format_quote(self, data: dict, symbol: str) -> str:
        current = data.get("c", 0)
        change = data.get("d", 0)
        change_pct = data.get("dp", 0)
        high = data.get("h", 0)
        low = data.get("l", 0)
        open_p = data.get("o", 0)

        sign = "+" if change >= 0 else ""
        return (
            f"{symbol} — Current: ${current:.2f}, "
            f"Change: {sign}{change:.2f} ({sign}{change_pct:.2f}%), "
            f"Day Range: ${low:.2f}\u2013${high:.2f}, "
            f"Open: ${open_p:.2f}"
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

        lines = [f"{symbol} Stock Candles (OHLCV):"]
        entries = min(len(closes), 20)
        for i in range(entries):
            date = datetime.fromtimestamp(timestamps[i]).strftime("%Y-%m-%d")
            lines.append(
                f"  {date} — O: {opens[i]:.2f}, H: {highs[i]:.2f}, "
                f"L: {lows[i]:.2f}, C: {closes[i]:.2f}, V: {volumes[i]:,}"
            )
        return "\n".join(lines)

    def format_forex_rates(self, data: dict, base: str) -> str:
        """Format tw.rter.info response. Keys are like 'USDTWD', values have 'Exrate' and 'UTC'."""
        if not data:
            return ""
        # Common target currencies to show
        targets = ["TWD", "JPY", "EUR", "GBP", "CNY", "HKD", "KRW", "AUD", "CAD", "CHF", "SGD"]
        lines = []
        utc_time = ""
        for target in targets:
            key = f"{base}{target}"
            if key in data:
                entry = data[key]
                rate = entry.get("Exrate")
                if rate is not None:
                    lines.append(f"  {base}/{target}: {rate}")
                    if not utc_time:
                        utc_time = entry.get("UTC", "")
        if not lines:
            # Fallback: show all matching entries for this base
            for key, entry in sorted(data.items()):
                if key.startswith(base) and len(key) == len(base) + 3:
                    rate = entry.get("Exrate")
                    if rate is not None:
                        target = key[len(base):]
                        lines.append(f"  {base}/{target}: {rate}")
        if not lines:
            return ""
        header = f"Exchange Rates (base: {base})"
        if utc_time:
            header += f" — Updated: {utc_time}"
        return header + "\n" + "\n".join(lines)

    def format_profile(self, data: dict) -> str:
        name = data.get("name", "")
        ticker = data.get("ticker", "")
        industry = data.get("finnhubIndustry", "")
        market_cap = data.get("marketCapitalization", 0)
        ipo = data.get("ipo", "")
        country = data.get("country", "")
        exchange = data.get("exchange", "")
        return (
            f"{name} ({ticker}) — Industry: {industry}, "
            f"Market Cap: ${market_cap:,.2f}M, IPO: {ipo}, "
            f"Country: {country}, Exchange: {exchange}"
        )

    def format_financials(self, data: dict, symbol: str) -> str:
        metric = data.get("metric", {})
        pe = metric.get("peNormalizedAnnual", "N/A")
        eps = metric.get("epsNormalizedAnnual", "N/A")
        div_yield = metric.get("dividendYieldIndicatedAnnual", "N/A")
        high_52w = metric.get("52WeekHigh", "N/A")
        low_52w = metric.get("52WeekLow", "N/A")
        return (
            f"{symbol} Financials — P/E: {pe}, EPS (TTM): {eps}, "
            f"Dividend Yield: {div_yield}%, "
            f"52W High: ${high_52w}, 52W Low: ${low_52w}"
        )

    def format_news(self, articles: list) -> str:
        if not articles:
            return ""
        lines = []
        for i, article in enumerate(articles[:5], start=1):
            headline = article.get("headline", "")
            source = article.get("source", "")
            ts = article.get("datetime", 0)
            date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            lines.append(f"{i}. {headline} ({source}, {date})")
        return "\n".join(lines)

    def format_earnings(self, data: list, symbol: str) -> str:
        if not data:
            return ""
        lines = [f"{symbol} Earnings:"]
        for e in data[:4]:
            actual = e.get("actual", "N/A")
            estimate = e.get("estimate", "N/A")
            period = e.get("period", "")
            surprise_pct = e.get("surprisePercent", 0)
            sign = "+" if surprise_pct >= 0 else ""
            lines.append(
                f"  {period} — EPS: {actual} (Est: {estimate}, "
                f"Surprise: {sign}{surprise_pct:.2f}%)"
            )
        return "\n".join(lines)

    def format_price_target(self, data: dict, symbol: str) -> str:
        high = data.get("targetHigh", "N/A")
        low = data.get("targetLow", "N/A")
        mean = data.get("targetMean", "N/A")
        median = data.get("targetMedian", "N/A")
        updated = data.get("lastUpdated", "")
        return (
            f"{symbol} Price Target — High: ${high}, Low: ${low}, "
            f"Mean: ${mean}, Median: ${median} (Updated: {updated})"
        )

    def format_recommendation(self, data: list, symbol: str) -> str:
        if not data:
            return ""
        latest = data[0]
        period = latest.get("period", "")
        strong_buy = latest.get("strongBuy", 0)
        buy = latest.get("buy", 0)
        hold = latest.get("hold", 0)
        sell = latest.get("sell", 0)
        strong_sell = latest.get("strongSell", 0)
        return (
            f"{symbol} Analyst Recommendations ({period}):\n"
            f"  Strong Buy: {strong_buy}, Buy: {buy}, Hold: {hold}, "
            f"Sell: {sell}, Strong Sell: {strong_sell}"
        )

    def format_insider(self, data: dict, symbol: str) -> str:
        transactions = data.get("data", [])
        if not transactions:
            return ""
        lines = [f"{symbol} Insider Transactions:"]
        for tx in transactions[:5]:
            name = tx.get("name", "")
            change = tx.get("change", 0)
            date = tx.get("transactionDate", "")
            price = tx.get("transactionPrice", 0)
            action = "Sold" if change < 0 else "Bought"
            lines.append(
                f"  {name} — {action} {abs(change):,} shares "
                f"at ${price:.2f} on {date}"
            )
        return "\n".join(lines)
