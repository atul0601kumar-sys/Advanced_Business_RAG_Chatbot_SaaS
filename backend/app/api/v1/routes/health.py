import logging
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.redis_queue import shared_task_queue

router = APIRouter(tags=["health"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
def readiness_check() -> JSONResponse:
    checks = {
        "database": _database_ready(),
        "qdrant": _qdrant_ready(),
        "redis": shared_task_queue.ping(),
    }
    status_code = status.HTTP_200_OK if all(checks.values()) else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if status_code == status.HTTP_200_OK else "degraded",
            "service": "backend",
            "version": settings.app_version,
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def _database_ready() -> bool:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _qdrant_ready() -> bool:
    headers = {}
    if settings.qdrant_api_key.strip():
        headers["api-key"] = settings.qdrant_api_key.strip()

    try:
        request = Request(f"{settings.qdrant_url.rstrip('/')}/readyz", headers=headers)
        with urlopen(request, timeout=3) as response:
            return response.status == 200
    except Exception as exc:
        logger.warning("Primary Qdrant readiness probe failed", extra={"error": str(exc), "qdrant_url": settings.qdrant_url})
        # Qdrant Cloud may front requests differently than a local node, so
        # fall back to a lightweight authenticated API call that still proves
        # the cluster is reachable and serving traffic.
        try:
            request = Request(f"{settings.qdrant_url.rstrip('/')}/collections", headers=headers)
            with urlopen(request, timeout=3) as response:
                return response.status == 200
        except Exception as fallback_exc:
            logger.warning(
                "Fallback Qdrant readiness probe failed",
                extra={"error": str(fallback_exc), "qdrant_url": settings.qdrant_url},
            )
            return False
