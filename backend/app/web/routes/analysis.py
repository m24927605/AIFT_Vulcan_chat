"""Async deep analysis endpoints powered by Celery task queue."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.celery_app import celery_app
from app.core.tasks.celery_tasks import deep_analysis_task

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class AnalysisRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    max_rounds: int = Field(default=3, ge=1, le=5)


class AnalysisSubmitResponse(BaseModel):
    task_id: str
    status: str = "pending"


class AnalysisStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None


@router.post("", response_model=AnalysisSubmitResponse, status_code=202)
async def submit_analysis(request: AnalysisRequest):
    task = deep_analysis_task.delay(query=request.query, max_rounds=request.max_rounds)
    return AnalysisSubmitResponse(task_id=task.id)


@router.get("/{task_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(task_id: str):
    result = celery_app.AsyncResult(task_id)
    return AnalysisStatusResponse(
        task_id=task_id,
        status=result.state,
        result=result.result if result.state == "SUCCESS" else None,
    )
