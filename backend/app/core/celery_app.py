"""Celery application factory for async AI task execution."""
from __future__ import annotations

from celery import Celery

from app.core.config import settings


def create_celery_app(
    broker_url: str | None = None, result_backend: str | None = None
) -> Celery:
    app = Celery("vulcan")
    app.conf.broker_url = broker_url or settings.celery_broker_url
    app.conf.result_backend = result_backend or settings.celery_result_backend
    app.conf.task_serializer = "json"
    app.conf.result_serializer = "json"
    app.conf.accept_content = ["json"]
    app.conf.task_track_started = True
    app.conf.task_time_limit = 300
    app.conf.task_soft_time_limit = 240
    return app


celery_app = create_celery_app()
