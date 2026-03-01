import pytest
from unittest.mock import patch

from app.telegram.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    return RateLimiter(max_requests=3, window_seconds=60)


def test_allows_requests_under_limit(limiter):
    assert limiter.is_allowed(chat_id=123) is True
    assert limiter.is_allowed(chat_id=123) is True
    assert limiter.is_allowed(chat_id=123) is True


def test_blocks_requests_over_limit(limiter):
    for _ in range(3):
        limiter.is_allowed(chat_id=123)
    assert limiter.is_allowed(chat_id=123) is False


def test_different_users_have_separate_limits(limiter):
    for _ in range(3):
        limiter.is_allowed(chat_id=123)
    assert limiter.is_allowed(chat_id=123) is False
    assert limiter.is_allowed(chat_id=456) is True


def test_allows_after_window_expires(limiter):
    with patch("app.telegram.rate_limiter.time") as mock_time:
        mock_time.monotonic.return_value = 0.0
        for _ in range(3):
            limiter.is_allowed(chat_id=123)
        assert limiter.is_allowed(chat_id=123) is False

        mock_time.monotonic.return_value = 61.0
        assert limiter.is_allowed(chat_id=123) is True


def test_remaining_returns_correct_count(limiter):
    assert limiter.remaining(chat_id=123) == 3
    limiter.is_allowed(chat_id=123)
    assert limiter.remaining(chat_id=123) == 2
