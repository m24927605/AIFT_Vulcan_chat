"""Celery task definitions for async AI workloads."""
from app.core.celery_app import celery_app
from app.core.tasks.deep_analysis import run_deep_analysis_sync


@celery_app.task(name="deep_analysis", bind=True, max_retries=1)
def deep_analysis_task(self, query: str, max_rounds: int = 3) -> dict:
    try:
        return run_deep_analysis_sync(query=query, max_rounds=max_rounds)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)
