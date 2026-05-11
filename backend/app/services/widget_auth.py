from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse
import uuid

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.input_validator import validate_origin_value
from app.core.security import create_signed_token, decode_signed_token

settings = get_settings()


@dataclass
class WidgetPrincipal:
    workspace_id: uuid.UUID
    origin: str | None


class WidgetAuthService:
    def build_token(self, *, workspace_id: uuid.UUID, origin: str | None) -> tuple[str, int]:
        expires_delta = timedelta(minutes=settings.widget_token_expire_minutes)
        token = create_signed_token(
            {
                "type": "widget",
                "workspace_id": str(workspace_id),
                "origin": origin,
            },
            expires_delta=expires_delta,
        )
        expires_at = int(expires_delta.total_seconds())
        return token, expires_at

    def authenticate(self, request: Request) -> WidgetPrincipal:
        token = request.headers.get("X-Widget-Token")
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget token is required.")
        payload = decode_signed_token(token, expected_type="widget")
        workspace_id = payload.get("workspace_id")
        if not workspace_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget token is missing a workspace.")
        token_origin = payload.get("origin")
        request_origin = self.extract_request_origin(request)
        if token_origin and request_origin and token_origin != request_origin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Widget origin mismatch.")
        return WidgetPrincipal(workspace_id=uuid.UUID(workspace_id), origin=token_origin or request_origin)

    def extract_request_origin(self, request: Request) -> str | None:
        origin = request.headers.get("Origin")
        if origin:
            return origin.rstrip("/")
        referer = request.headers.get("Referer")
        if not referer:
            return None
        parsed = urlparse(referer)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    def validate_origin(self, *, origin: str | None, allowed_origins: list[str]) -> None:
        if not allowed_origins:
            return
        if not origin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Widget origin is required.")
        try:
            normalized_origin = validate_origin_value(origin)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        origin_host = urlparse(normalized_origin).netloc.lower()
        for allowed_origin in allowed_origins:
            normalized = allowed_origin.strip().rstrip("/").lower()
            if not normalized:
                continue
            if normalized.startswith("*."):
                suffix = normalized[1:]
                if origin_host.endswith(suffix):
                    return
            elif normalized == normalized_origin.lower() or normalized == origin_host:
                return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin is not allowed for this widget.")
