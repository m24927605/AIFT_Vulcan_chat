import logging

import pytest
from unittest.mock import patch

from app.entrypoint import get_mode, _validate_production_settings


def test_entrypoint_mode_web():
    with patch.dict("os.environ", {"MODE": "web"}):
        assert get_mode() == "web"


def test_entrypoint_mode_telegram():
    with patch.dict("os.environ", {"MODE": "telegram"}):
        assert get_mode() == "telegram"


def test_entrypoint_mode_all():
    with patch.dict("os.environ", {"MODE": "all"}):
        assert get_mode() == "all"


def test_entrypoint_default_mode():
    with patch.dict("os.environ", {}, clear=True), \
         patch("app.entrypoint.settings") as mock_settings:
        mock_settings.mode = "web"
        assert get_mode() == "web"


def test_validate_warns_in_web_mode(caplog):
    with patch("app.entrypoint.settings") as mock_settings:
        mock_settings.api_secret_key = ""
        mock_settings.frontend_url = "http://localhost:3000"
        with caplog.at_level(logging.WARNING):
            _validate_production_settings("web")
        assert "unprotected" in caplog.text


def test_validate_raises_in_all_mode():
    with patch("app.entrypoint.settings") as mock_settings:
        mock_settings.api_secret_key = ""
        with pytest.raises(SystemExit):
            _validate_production_settings("all")


def test_validate_raises_in_telegram_mode():
    with patch("app.entrypoint.settings") as mock_settings:
        mock_settings.api_secret_key = ""
        with pytest.raises(SystemExit):
            _validate_production_settings("telegram")


def test_validate_raises_in_web_mode_with_production_url():
    with patch("app.entrypoint.settings") as mock_settings:
        mock_settings.api_secret_key = ""
        mock_settings.frontend_url = "https://vulcanchat.xyz"
        with pytest.raises(SystemExit):
            _validate_production_settings("web")


def test_validate_ok_when_key_set(caplog):
    with patch("app.entrypoint.settings") as mock_settings:
        mock_settings.api_secret_key = "secret-123"
        with caplog.at_level(logging.WARNING):
            _validate_production_settings("all")
        assert "API_SECRET_KEY" not in caplog.text
