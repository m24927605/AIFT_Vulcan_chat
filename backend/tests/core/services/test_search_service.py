import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.services.search_service import SearchService
from app.core.models.schemas import SearchResult


@pytest.fixture
def search_service():
    return SearchService(api_key="test-tavily-key")


def _mock_tavily_response():
    return {
        "results": [
            {
                "title": "TSMC Stock Price",
                "url": "https://example.com/tsmc",
                "content": "TSMC stock is at $180",
                "score": 0.95,
            },
            {
                "title": "TSMC News",
                "url": "https://example.com/tsmc-news",
                "content": "TSMC reported Q4 earnings",
                "score": 0.85,
            },
        ]
    }


@pytest.mark.asyncio
async def test_search_returns_results(search_service):
    with patch.object(
        search_service._client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_tavily_response()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = await search_service.search("TSMC stock price")

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "TSMC Stock Price"
        assert results[0].url == "https://example.com/tsmc"


@pytest.mark.asyncio
async def test_search_returns_empty_on_error(search_service):
    with patch.object(
        search_service._client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.side_effect = Exception("API Error")

        results = await search_service.search("failing query")

        assert results == []


@pytest.mark.asyncio
async def test_search_multiple_queries(search_service):
    with patch.object(
        search_service._client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_tavily_response()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = await search_service.search_multiple(
            ["query1", "query2"]
        )

        assert len(results) == 2  # Both queries return same URLs, deduplication reduces 4 to 2
        assert mock_post.call_count == 2
