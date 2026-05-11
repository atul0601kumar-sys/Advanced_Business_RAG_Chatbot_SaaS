from __future__ import annotations

import json
import urllib.request
from typing import Any

from app.core.input_validator import sanitize_text
from app.services.base_integration import IntegrationContext, IntegrationResult, IntegrationService


class SlackIntegration(IntegrationService):
    integration_type = "slack"

    def connect(self, context: IntegrationContext) -> IntegrationResult:
        self.validate_config(config=context.config, credentials=context.credentials)
        return IntegrationResult(status_code=200, response_body="Slack integration configured.")

    def send_event(self, context: IntegrationContext, *, event_type: str, payload: dict[str, Any]) -> IntegrationResult:
        self.validate_config(config=context.config, credentials=context.credentials)
        body = {
            "channel": context.config["channel_id"],
            "text": self._render_text(event_type=event_type, payload=payload),
            "unfurl_links": False,
            "unfurl_media": False,
        }
        request = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {context.credentials['bot_token']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return IntegrationResult(
                status_code=getattr(response, "status", 200),
                response_body=response.read().decode("utf-8", errors="replace")[:5000],
            )

    def disconnect(self, context: IntegrationContext) -> IntegrationResult:
        return IntegrationResult(status_code=200, response_body="Slack integration disconnected.")

    def validate_config(self, *, config: dict[str, Any], credentials: dict[str, Any]) -> None:
        if not sanitize_text(str(config.get("channel_id") or ""), max_length=255):
            raise ValueError("Slack integration requires channel_id.")
        if not sanitize_text(str(credentials.get("bot_token") or ""), max_length=4000):
            raise ValueError("Slack integration requires bot_token.")

    def _render_text(self, *, event_type: str, payload: dict[str, Any]) -> str:
        data = payload.get("data") or {}
        title = event_type.replace("_", " ").title()
        lead_name = data.get("name") or data.get("email") or "Unknown lead"
        message = data.get("message") or data.get("query") or "No details provided."
        return f"{title}\nWorkspace: {payload.get('workspace_id')}\nSubject: {lead_name}\nDetails: {message}"
