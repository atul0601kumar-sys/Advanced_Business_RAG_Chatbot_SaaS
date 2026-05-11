from __future__ import annotations

from typing import Any

from app.core.input_validator import validate_webhook_url
from app.services.base_integration import IntegrationContext, IntegrationResult, IntegrationService
from app.services.webhook_handler import WebhookHandler


class WebhookIntegration(IntegrationService):
    integration_type = "webhook"

    def __init__(self, webhook_handler: WebhookHandler | None = None) -> None:
        self.webhook_handler = webhook_handler or WebhookHandler()

    def connect(self, context: IntegrationContext) -> IntegrationResult:
        self.validate_config(config=context.config, credentials=context.credentials)
        return IntegrationResult(status_code=200, response_body="Webhook integration configured.")

    def send_event(self, context: IntegrationContext, *, event_type: str, payload: dict[str, Any]) -> IntegrationResult:
        self.validate_config(config=context.config, credentials=context.credentials)
        response = self.webhook_handler.post_json(
            str(context.config["webhook_url"]),
            {
                "event_type": event_type,
                "data": payload.get("data", {}),
                "timestamp": payload.get("timestamp"),
                "workspace_id": payload.get("workspace_id"),
                "integration_id": payload.get("integration_id"),
            },
            timeout_seconds=int(context.config.get("timeout_seconds") or 15),
        )
        return IntegrationResult(status_code=response.status_code, response_body=response.response_body)

    def disconnect(self, context: IntegrationContext) -> IntegrationResult:
        return IntegrationResult(status_code=200, response_body="Webhook integration disconnected.")

    def validate_config(self, *, config: dict[str, Any], credentials: dict[str, Any]) -> None:
        if not config.get("webhook_url"):
            raise ValueError("Webhook integration requires webhook_url.")
        validate_webhook_url(str(config["webhook_url"]))
