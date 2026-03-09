"""Async deep analysis endpoints powered by Celery task queue."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.celery_app import celery_app
from app.core.tasks.celery_tasks import deep_analysis_task
from app.core.web_session import ensure_web_session, verify_csrf
from app.web.deps import get_storage

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# In-memory mapping of task_id → session_id for ownership checks.
# In production this should be persisted (e.g. Redis or DB), but for
# demo scope an in-process dict is sufficient.
_task_owners: dict[str, str] = {}


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
async def submit_analysis(
    request: Request,
    response: Response,
    body: AnalysisRequest,
    _csrf: None = Depends(verify_csrf),
):
    storage = get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    task = deep_analysis_task.delay(query=body.query, max_rounds=body.max_rounds)
    _task_owners[task.id] = session_id
    return AnalysisSubmitResponse(task_id=task.id)


@router.get("/{task_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    task_id: str,
    request: Request,
    response: Response,
):
    storage = get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    owner = _task_owners.get(task_id)
    if owner is not None and owner != session_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    result = celery_app.AsyncResult(task_id)
    return AnalysisStatusResponse(
        task_id=task_id,
        status=result.state,
        result=result.result if result.state == "SUCCESS" else None,
    )
