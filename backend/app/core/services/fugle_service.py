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
