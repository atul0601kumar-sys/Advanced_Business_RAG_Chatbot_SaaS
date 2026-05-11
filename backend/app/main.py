import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.analytics import router as analytics_router
from app.api.v1.routes.chat import router as chat_router
from app.api.v1.routes.documents import router as documents_router
from app.api.v1.routes.export import router as export_router
from app.api.v1.routes.faq import router as faq_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.integrations import router as integrations_router
from app.api.v1.routes.leads import handoff_router as handoff_router
from app.api.v1.routes.leads import router as leads_router
from app.api.v1.routes.notifications import router as notifications_router
from app.api.v1.routes.retrieval import router as retrieval_router
from app.api.v1.routes.scheduling import router as scheduling_router
from app.api.v1.routes.settings import router as settings_router
from app.api.v1.routes.voice import router as voice_router
from app.api.v1.routes.widget import router as widget_router
from app.api.v1.routes.website_sources import router as website_sources_router
from app.api.v1.routes.website_sources import website_router
from app.api.v1.routes.workspaces import router as workspaces_router
from app.core.audit_logger import SecurityAuditMiddleware
from app.core.auth_security import CSRFMiddleware
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.monitoring import configure_error_monitoring
from app.core.request_context import RequestIdMiddleware
from app.core.security_headers import HTTPSRedirectMiddleware, SecurityHeadersMiddleware
from app.core.rate_limiter import RateLimitMiddleware
from app.middleware.widget_cors import WidgetCorsMiddleware
from app.services.job_queue import shared_export_queue
from app.services.integration_queue import shared_integration_queue
from app.services.notification_queue import shared_notification_queue

settings = get_settings()
configure_logging(settings)
configure_error_monitoring(settings)
logger = logging.getLogger(__name__)


def start_inline_workers() -> None:
    if settings.worker_mode == "inline":
        shared_notification_queue.start()
        shared_export_queue.start()
        shared_integration_queue.start()
    else:
        logger.info("Inline background workers are disabled", extra={"worker_mode": settings.worker_mode})


def stop_inline_workers() -> None:
    if settings.worker_mode == "inline":
        shared_notification_queue.stop()
        shared_export_queue.stop()
        shared_integration_queue.stop()


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_inline_workers()
    try:
        yield
    finally:
        stop_inline_workers()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins or [settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Widget-Token"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware, excluded_prefixes=("/api/v1/health",))
app.add_middleware(SecurityAuditMiddleware)
app.add_middleware(WidgetCorsMiddleware)

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(faq_router, prefix="/api/v1")
app.include_router(leads_router, prefix="/api/v1")
app.include_router(handoff_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(retrieval_router, prefix="/api/v1")
app.include_router(scheduling_router, prefix="/api/v1")
app.include_router(website_sources_router, prefix="/api/v1")
app.include_router(website_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(widget_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Request validation failed", extra={"path": request.url.path, "errors": exc.errors()})
    return JSONResponse(status_code=422, content={"detail": "Invalid request payload."})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "An internal server error occurred."})
