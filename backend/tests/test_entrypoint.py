import pytest
from unittest.mock import patch


def test_entrypoint_mode_web():
    with patch.dict("os.environ", {"MODE": "web"}):
        from app.entrypoint import get_mode
        assert get_mode() == "web"


def test_entrypoint_mode_telegram():
    with patch.dict("os.environ", {"MODE": "telegram"}):
        from app.entrypoint import get_mode
        assert get_mode() == "telegram"


def test_entrypoint_mode_all():
    with patch.dict("os.environ", {"MODE": "all"}):
        from app.entrypoint import get_mode
        assert get_mode() == "all"


def test_entrypoint_default_mode():
    with patch.dict("os.environ", {}, clear=True):
        from app.entrypoint import get_mode
        assert get_mode() == "web"
