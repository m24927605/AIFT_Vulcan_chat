from unittest.mock import patch

import pytest

from app.web.main import _validate_web_settings


def test_exits_when_no_key_and_production_url():
    with patch("app.web.main.settings") as mock:
        mock.api_secret_key = ""
        mock.frontend_url = "https://app.example.com"
        with pytest.raises(SystemExit):
            _validate_web_settings()


def test_warns_when_no_key_and_localhost(caplog):
    with patch("app.web.main.settings") as mock:
        mock.api_secret_key = ""
        mock.frontend_url = "http://localhost:3000"
        _validate_web_settings()
    assert "auth disabled" in caplog.text


def test_no_warning_when_key_set(caplog):
    with patch("app.web.main.settings") as mock:
        mock.api_secret_key = "secret"
        mock.frontend_url = "https://app.example.com"
        _validate_web_settings()
    assert "auth disabled" not in caplog.text
