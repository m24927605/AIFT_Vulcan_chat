import pytest
from unittest.mock import patch

from app.core.services.finnhub_service import FinnhubService


@pytest.fixture
def finnhub_service():
    return FinnhubService(api_key="test-finnhub-key")


# ---------------------------------------------------------------------------
# Mock response factories
# ---------------------------------------------------------------------------

def _mock_quote_response():
    return {
        "c": 189.50,
        "d": 2.30,
        "dp": 1.23,
        "h": 190.15,
        "l": 187.20,
        "o": 187.50,
        "pc": 187.20,
        "t": 1700000000,
    }


def _mock_quote_negative_response():
    return {
        "c": 185.00,
        "d": -2.20,
        "dp": -1.18,
        "h": 188.00,
        "l": 184.50,
        "o": 187.20,
        "pc": 187.20,
        "t": 1700000000,
    }


def _mock_candles_response():
    return {
        "s": "ok",
        "c": [150.0, 152.0, 153.5],
        "h": [151.0, 153.0, 154.0],
        "l": [149.0, 151.0, 152.0],
        "o": [149.5, 151.5, 152.5],
        "v": [1000000, 1200000, 1100000],
        "t": [1700000000, 1700086400, 1700172800],
    }


def _mock_candles_no_data_response():
    return {"s": "no_data"}


def _mock_forex_response():
    return {
        "base": "USD",
        "quote": {
            "TWD": 32.15,
            "EUR": 0.92,
            "JPY": 149.50,
        },
    }


def _mock_profile_response():
    return {
        "name": "Apple Inc",
        "ticker": "AAPL",
        "finnhubIndustry": "Technology",
        "marketCapitalization": 2950.0,
        "ipo": "1980-12-12",
        "country": "US",
        "exchange": "NASDAQ",
        "weburl": "https://www.apple.com",
    }


def _mock_financials_response():
    return {
        "metric": {
            "peNormalizedAnnual": 29.5,
            "epsNormalizedAnnual": 6.42,
            "dividendYieldIndicatedAnnual": 0.55,
            "52WeekHigh": 199.62,
            "52WeekLow": 164.08,
        },
        "metricType": "all",
        "symbol": "AAPL",
    }


def _mock_news_response():
    return [
        {
            "headline": "Apple launches new iPhone",
            "datetime": 1700000000,
            "source": "Reuters",
            "url": "https://example.com/1",
            "summary": "Apple has launched a new iPhone model.",
        },
        {
            "headline": "Apple earnings beat estimates",
            "datetime": 1699900000,
            "source": "Bloomberg",
            "url": "https://example.com/2",
            "summary": "Apple earnings exceeded expectations.",
        },
    ]


def _mock_news_empty_response():
    return []


def _mock_earnings_response():
    return [
        {
            "actual": 1.52,
            "estimate": 1.43,
            "period": "2026-01-01",
            "quarter": 1,
            "year": 2026,
            "surprise": 0.09,
            "surprisePercent": 6.29,
        },
        {
            "actual": 1.46,
            "estimate": 1.40,
            "period": "2025-10-01",
            "quarter": 4,
            "year": 2025,
            "surprise": 0.06,
            "surprisePercent": 4.29,
        },
    ]


def _mock_price_target_response():
    return {
        "targetHigh": 220.0,
        "targetLow": 160.0,
        "targetMean": 195.0,
        "targetMedian": 198.0,
        "lastUpdated": "2026-03-01",
        "symbol": "AAPL",
    }


def _mock_recommendation_response():
    return [
        {
            "buy": 20,
            "hold": 10,
            "sell": 2,
            "strongBuy": 8,
            "strongSell": 1,
            "period": "2026-03-01",
            "symbol": "AAPL",
        },
    ]


def _mock_insider_response():
    return {
        "data": [
            {
                "name": "Tim Cook",
                "share": 100000,
                "change": -5000,
                "transactionDate": "2026-02-15",
                "transactionPrice": 189.50,
                "transactionCode": "S",
            },
            {
                "name": "Luca Maestri",
                "share": 50000,
                "change": 2000,
                "transactionDate": "2026-02-10",
                "transactionPrice": 185.00,
                "transactionCode": "P",
            },
        ],
        "symbol": "AAPL",
    }


# ---------------------------------------------------------------------------
# TestFormatMethods — pure formatting logic, no async
# ---------------------------------------------------------------------------

class TestFormatMethods:
    def test_format_quote(self, finnhub_service):
        text = finnhub_service.format_quote(_mock_quote_response(), "AAPL")
        assert "AAPL" in text
        assert "189.50" in text
        assert "+2.30" in text
        assert "+1.23%" in text
        assert "187.20" in text
        assert "190.15" in text
        assert "187.50" in text

    def test_format_quote_negative(self, finnhub_service):
        text = finnhub_service.format_quote(_mock_quote_negative_response(), "AAPL")
        assert "AAPL" in text
        assert "185.00" in text
        assert "-2.20" in text
        assert "-1.18%" in text
        # No "+" prefix for negative changes
        assert "+2.20" not in text
        assert "+1.18" not in text

    def test_format_profile(self, finnhub_service):
        text = finnhub_service.format_profile(_mock_profile_response())
        assert "Apple Inc" in text
        assert "AAPL" in text
        assert "Technology" in text
        assert "2950" in text or "2,950" in text
        assert "1980-12-12" in text
        assert "US" in text
        assert "NASDAQ" in text

    def test_format_candles(self, finnhub_service):
        text = finnhub_service.format_candles(_mock_candles_response(), "AAPL")
        assert "AAPL" in text
        assert "150" in text
        assert "152" in text
        assert "153.5" in text or "153.50" in text

    def test_format_candles_no_data(self, finnhub_service):
        text = finnhub_service.format_candles(_mock_candles_no_data_response(), "AAPL")
        assert text == ""

    def test_format_financials(self, finnhub_service):
        text = finnhub_service.format_financials(_mock_financials_response(), "AAPL")
        assert "AAPL" in text
        assert "29.5" in text
        assert "6.42" in text
        assert "0.55" in text
        assert "199.62" in text
        assert "164.08" in text

    def test_format_news(self, finnhub_service):
        text = finnhub_service.format_news(_mock_news_response())
        assert "Apple launches new iPhone" in text
        assert "Reuters" in text
        assert "Apple earnings beat estimates" in text
        assert "Bloomberg" in text

    def test_format_news_empty(self, finnhub_service):
        text = finnhub_service.format_news(_mock_news_empty_response())
        assert text == ""

    def test_format_earnings(self, finnhub_service):
        text = finnhub_service.format_earnings(_mock_earnings_response(), "AAPL")
        assert "AAPL" in text
        assert "1.52" in text
        assert "1.43" in text
        assert "6.29" in text

    def test_format_price_target(self, finnhub_service):
        text = finnhub_service.format_price_target(_mock_price_target_response(), "AAPL")
        assert "AAPL" in text
        assert "220" in text
        assert "160" in text
        assert "195" in text
        assert "198" in text

    def test_format_recommendation(self, finnhub_service):
        text = finnhub_service.format_recommendation(_mock_recommendation_response(), "AAPL")
        assert "AAPL" in text
        assert "20" in text
        assert "10" in text
        assert "2" in text or "Sell" in text
        assert "8" in text
        assert "1" in text

    def test_format_insider(self, finnhub_service):
        text = finnhub_service.format_insider(_mock_insider_response(), "AAPL")
        assert "AAPL" in text
        assert "Tim Cook" in text
        assert "Luca Maestri" in text
        assert "5,000" in text or "5000" in text
        assert "2,000" in text or "2000" in text

    def test_format_forex(self, finnhub_service):
        text = finnhub_service.format_forex_rates(_mock_forex_response(), "USD")
        assert "USD" in text
        assert "TWD" in text
        assert "32.15" in text
        assert "EUR" in text
        assert "0.92" in text
        assert "JPY" in text
        assert "149.50" in text or "149.5" in text


# ---------------------------------------------------------------------------
# TestAsyncMethods — mock the SDK client, verify async get_* returns text
# ---------------------------------------------------------------------------

class TestAsyncMethods:
    @pytest.mark.asyncio
    async def test_get_quote(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.quote.return_value = _mock_quote_response()
            result = await finnhub_service.get_quote("AAPL")
            assert "AAPL" in result
            assert "189.50" in result

    @pytest.mark.asyncio
    async def test_get_quote_error(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.quote.side_effect = Exception("API Error")
            result = await finnhub_service.get_quote("AAPL")
            assert result == ""

    @pytest.mark.asyncio
    async def test_get_candles(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.stock_candles.return_value = _mock_candles_response()
            result = await finnhub_service.get_candles("AAPL")
            assert "AAPL" in result
            assert "150" in result

    @pytest.mark.asyncio
    async def test_get_profile(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.company_profile2.return_value = _mock_profile_response()
            result = await finnhub_service.get_profile("AAPL")
            assert "Apple Inc" in result
            assert "AAPL" in result

    @pytest.mark.asyncio
    async def test_get_financials(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.company_basic_financials.return_value = _mock_financials_response()
            result = await finnhub_service.get_financials("AAPL")
            assert "AAPL" in result
            assert "29.5" in result

    @pytest.mark.asyncio
    async def test_get_news(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.company_news.return_value = _mock_news_response()
            result = await finnhub_service.get_news("AAPL")
            assert "Apple launches new iPhone" in result

    @pytest.mark.asyncio
    async def test_get_earnings(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.company_earnings.return_value = _mock_earnings_response()
            result = await finnhub_service.get_earnings("AAPL")
            assert "AAPL" in result
            assert "1.52" in result

    @pytest.mark.asyncio
    async def test_get_price_target(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.price_target.return_value = _mock_price_target_response()
            result = await finnhub_service.get_price_target("AAPL")
            assert "AAPL" in result
            assert "220" in result

    @pytest.mark.asyncio
    async def test_get_recommendation(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.recommendation_trends.return_value = _mock_recommendation_response()
            result = await finnhub_service.get_recommendation("AAPL")
            assert "AAPL" in result

    @pytest.mark.asyncio
    async def test_get_insider(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.stock_insider_transactions.return_value = _mock_insider_response()
            result = await finnhub_service.get_insider("AAPL")
            assert "AAPL" in result
            assert "Tim Cook" in result

    @pytest.mark.asyncio
    async def test_get_forex(self, finnhub_service):
        with patch.object(finnhub_service, "_client") as mock_client:
            mock_client.forex_rates.return_value = _mock_forex_response()
            result = await finnhub_service.get_forex_rates("USD")
            assert "USD" in result
            assert "TWD" in result
            assert "32.15" in result
