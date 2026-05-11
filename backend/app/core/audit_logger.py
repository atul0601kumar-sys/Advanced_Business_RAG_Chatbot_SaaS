from __future__ import annotations

from time import perf_counter
import uuid

from fastapi import Request
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.access_control import get_client_ip
from app.db.session import SessionLocal
from app.models import AccessLog, AuditLog


class AuditAction:
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    ACCOUNT_LOCKED = "account_locked"
    TOKEN_REFRESHED = "token_refreshed"
    LOGOUT = "logout"
    RATE_LIMITED = "rate_limited"
    PROMPT_INJECTION = "prompt_injection_detected"
    SUSPICIOUS_REQUEST = "suspicious_request"


class AuditLogger:
    def log(
        self,
        db: Session,
        *,
        action: str,
        request: Request,
        user_id=None,
        workspace_id=None,
        metadata: dict | None = None,
    ) -> None:
        db.add(
            AuditLog(
                user_id=user_id,
                workspace_id=workspace_id,
                action=action,
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent", "")[:512] or None,
                request_id=getattr(request.state, "request_id", None),
                metadata_json=metadata or {},
            )
        )


shared_audit_logger = AuditLogger()


def flag_suspicious_request(request: Request, *, action: str, metadata: dict | None = None) -> None:
    entries = getattr(request.state, "security_audit_events", [])
    entries.append({"action": action, "metadata": metadata or {}})
    request.state.security_audit_events = entries


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        started = perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            with SessionLocal() as db:
                self._persist_access_log(db, request, response, started)
                self._persist_audit_events(db, request)
                db.commit()

    def _persist_access_log(self, db: Session, request: Request, response, started_at: float) -> None:  # noqa: ANN001
        latency_ms = int((perf_counter() - started_at) * 1000)
        workspace_id = request.path_params.get("workspace_id") if hasattr(request, "path_params") else None
        if isinstance(workspace_id, str):
            try:
                workspace_id = uuid.UUID(workspace_id)
            except ValueError:
                workspace_id = None
        db.add(
            AccessLog(
                workspace_id=workspace_id,
                user_id=getattr(request.state, "auth_user_id", None),
                path=request.url.path[:255],
                method=request.method[:10],
                status_code=getattr(response, "status_code", 500),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent", "")[:512] or None,
                request_id=request.state.request_id,
                latency_ms=latency_ms,
            )
        )

    def _persist_audit_events(self, db: Session, request: Request) -> None:
        workspace_id = request.path_params.get("workspace_id") if hasattr(request, "path_params") else None
        if isinstance(workspace_id, str):
            try:
                workspace_id = uuid.UUID(workspace_id)
            except ValueError:
                workspace_id = None
        for event in getattr(request.state, "security_audit_events", []):
            shared_audit_logger.log(
                db,
                action=event["action"],
                request=request,
                user_id=getattr(request.state, "auth_user_id", None),
                workspace_id=workspace_id,
                metadata=event.get("metadata"),
            )
