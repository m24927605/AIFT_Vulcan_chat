import time
import logging

from fastapi import APIRouter, Request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/health")
async def health(request: Request):
    checks = {}

    # DB check
    try:
        storage = request.app.state.conversation_storage
        await storage.db.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        logger.error("Health check DB failure: %s", e)
        checks["database"] = "error"

    # Uptime
    started_at = getattr(request.app.state, "started_at", None)
    uptime_s = int(time.time() - started_at) if started_at else None

    all_ok = all(v == "ok" for v in checks.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
        "uptime_seconds": uptime_s,
    }
