from __future__ import annotations

import hmac
import hashlib
import json
import urllib.request
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.input_validator import validate_webhook_url


@dataclass(frozen=True)
class WebhookDeliveryResult:
    status_code: int
    response_body: str


class WebhookService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate_url(self, url: str) -> str:
        return validate_webhook_url(url)

    def send(self, webhook_url: str, payload: dict) -> WebhookDeliveryResult:
        validated_url = self.validate_url(webhook_url)
        encoded = json.dumps(payload).encode("utf-8")
        signature = ""
        if self.settings.webhook_signing_secret:
            signature = hmac.new(
                self.settings.webhook_signing_secret.encode("utf-8"),
                encoded,
                hashlib.sha256,
            ).hexdigest()
        request = urllib.request.Request(
            validated_url,
            data=encoded,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
            },
            method="POST",
        )
        with urllib.request.urlopen(
            request,
            timeout=self.settings.notification_webhook_timeout_seconds,
        ) as response:
            status_code = getattr(response, "status", 200)
            response_body = response.read().decode("utf-8", errors="replace")
            return WebhookDeliveryResult(status_code=status_code, response_body=response_body[:5000])
