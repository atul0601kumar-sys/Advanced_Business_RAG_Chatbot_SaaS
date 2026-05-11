from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.access_control import get_client_ip
from app.core.config import get_settings

settings = get_settings()


@dataclass(frozen=True)
class RateLimitRule:
    scope: str
    limit: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, deque[float]] = {}

    def enforce(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.time()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Retry in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)


shared_rate_limiter = InMemoryRateLimiter()


def build_rate_limit_key(scope: str, identifier: str) -> str:
    return f"{scope}:{identifier}"


def resolve_request_identifier(request: Request, *, fallback: str = "anonymous") -> str:
    return get_client_ip(request) or fallback


def enforce_rate_limit(
    request: Request,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
    identifier: str | None = None,
) -> None:
    key = build_rate_limit_key(scope, identifier or resolve_request_identifier(request))
    shared_rate_limiter.enforce(key, limit=limit, window_seconds=window_seconds)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, excluded_prefixes: Iterable[str] | None = None) -> None:  # noqa: ANN001
        super().__init__(app)
        self.excluded_prefixes = tuple(excluded_prefixes or ())

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/") and not request.url.path.startswith(self.excluded_prefixes):
            try:
                enforce_rate_limit(
                    request,
                    scope="api",
                    limit=settings.api_rate_limit_count,
                    window_seconds=settings.api_rate_limit_window_seconds,
                )
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)
        return await call_next(request)
