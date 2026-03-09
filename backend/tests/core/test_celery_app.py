import pytest
from unittest.mock import patch, MagicMock


def test_celery_app_configurable():
    from app.core.celery_app import create_celery_app

    app = create_celery_app(broker_url="redis://localhost:6379/0")
    assert app.main == "vulcan"
    assert "redis" in app.conf.broker_url


def test_celery_app_uses_json_serializer():
    from app.core.celery_app import create_celery_app

    app = create_celery_app(broker_url="redis://test:6379/0")
    assert app.conf.task_serializer == "json"
    assert app.conf.result_serializer == "json"
