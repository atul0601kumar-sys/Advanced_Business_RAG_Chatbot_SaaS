from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.core.input_validator import validate_webhook_url


@dataclass(frozen=True)
class WebhookResponse:
    status_code: int
    response_body: str


class WebhookHandler:
    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 15,
    ) -> WebhookResponse:
        validated_url = validate_webhook_url(url)
        request = urllib.request.Request(
            validated_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = getattr(response, "status", 200)
            response_body = response.read().decode("utf-8", errors="replace")
            return WebhookResponse(status_code=status_code, response_body=response_body[:5000])
