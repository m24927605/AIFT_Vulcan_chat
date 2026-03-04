import pytest
from app.core.config import Settings


def test_telegram_settings_have_defaults():
    s = Settings(openai_api_key="k", tavily_api_key="k", _env_file=None)
    assert s.telegram_bot_token == ""
    assert s.telegram_admin_ids == []
    assert s.mode == "web"


def test_telegram_admin_ids_parsed_from_list():
    s = Settings(
        openai_api_key="k",
        tavily_api_key="k",
        telegram_admin_ids=[123, 456],
    )
    assert s.telegram_admin_ids == [123, 456]
