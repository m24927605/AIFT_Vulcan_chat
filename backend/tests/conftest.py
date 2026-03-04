import pytest

from app.core.config import Settings


@pytest.fixture
def test_settings():
    return Settings(
        openai_api_key="test-key",
        tavily_api_key="test-tavily-key",
    )
