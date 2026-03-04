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


def test_format_quote_negative_change(fugle_service):
    data = _mock_quote_response()
    data["change"] = -20
    data["changePercent"] = -1.01
    text = fugle_service.format_quote(data)
    assert "-20" in text
    assert "-1.01" in text
    # Negative sign comes from the number itself, no "+" prefix
    assert "+" not in text.split("漲跌")[1].split("\n")[0]


def test_format_historical_empty_candles(fugle_service):
    data = {"symbol": "2330", "data": []}
    text = fugle_service.format_historical(data, "2330")
    assert text == ""


def test_format_historical_missing_data_key(fugle_service):
    data = {"symbol": "2330"}
    text = fugle_service.format_historical(data, "2330")
    assert text == ""


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
