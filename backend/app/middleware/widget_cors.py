from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class WidgetCorsMiddleware(BaseHTTPMiddleware):
    def _is_widget_request(self, request) -> bool:
        if request.headers.get("X-Widget-Request") == "1":
            return True
        if request.method == "OPTIONS":
            requested_headers = request.headers.get("Access-Control-Request-Headers", "").lower()
            return "x-widget-request" in requested_headers
        return False

    async def dispatch(self, request, call_next):
        if not self._is_widget_request(request):
            return await call_next(request)

        origin = request.headers.get("Origin")
        if request.method == "OPTIONS":
            response = Response(status_code=204)
        else:
            response = await call_next(request)

        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Widget-Token, X-Widget-Request"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        return response

