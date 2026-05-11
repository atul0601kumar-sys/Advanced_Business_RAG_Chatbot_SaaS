from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

settings = get_settings()


def _request_scheme(request: Request) -> str:
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower()
    return request.url.scheme.lower()


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.app_env == "production" and settings.enforce_https_in_production and _request_scheme(request) != "https":
            secure_url = request.url.replace(scheme="https")
            return RedirectResponse(str(secure_url), status_code=307)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
            "connect-src 'self' https:; form-action 'self';",
        )
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.app_env == "production" and _request_scheme(request) == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.security_hsts_seconds}; includeSubDomains",
            )
        return response
