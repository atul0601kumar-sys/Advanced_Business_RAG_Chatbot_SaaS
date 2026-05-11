from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from app.core.input_validator import sanitize_json_payload, sanitize_text
from app.services.base_integration import IntegrationContext, IntegrationResult, IntegrationService


class GoogleSheetsIntegration(IntegrationService):
    integration_type = "google_sheets"

    def connect(self, context: IntegrationContext) -> IntegrationResult:
        self.validate_config(config=context.config, credentials=context.credentials)
        return IntegrationResult(status_code=200, response_body="Google Sheets integration configured.")

    def send_event(self, context: IntegrationContext, *, event_type: str, payload: dict[str, Any]) -> IntegrationResult:
        self.validate_config(config=context.config, credentials=context.credentials)
        spreadsheet_id = str(context.config["spreadsheet_id"])
        sheet_name = str(context.config.get("sheet_name") or "Sheet1")
        bearer_token = str(context.credentials["bearer_token"])
        row = self._build_row(event_type=event_type, payload=payload)
        encoded_range = urllib.parse.quote(f"{sheet_name}!A1", safe="!A1:")
        endpoint = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{urllib.parse.quote(spreadsheet_id)}"
            f"/values/{encoded_range}:append?valueInputOption=RAW"
        )
        body = json.dumps({"values": [row]}).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return IntegrationResult(
                status_code=getattr(response, "status", 200),
                response_body=response.read().decode("utf-8", errors="replace")[:5000],
            )

    def disconnect(self, context: IntegrationContext) -> IntegrationResult:
        return IntegrationResult(status_code=200, response_body="Google Sheets integration disconnected.")

    def validate_config(self, *, config: dict[str, Any], credentials: dict[str, Any]) -> None:
        if not sanitize_text(str(config.get("spreadsheet_id") or ""), max_length=255):
            raise ValueError("Google Sheets integration requires spreadsheet_id.")
        if not sanitize_text(str(credentials.get("bearer_token") or ""), max_length=4000):
            raise ValueError("Google Sheets integration requires a bearer_token.")

    def _build_row(self, *, event_type: str, payload: dict[str, Any]) -> list[str]:
        safe_payload = sanitize_json_payload(payload)
        data = safe_payload.get("data", {})
        return [
            str(safe_payload.get("timestamp") or ""),
            event_type,
            str(safe_payload.get("workspace_id") or ""),
            str((data or {}).get("lead_id") or (data or {}).get("message_id") or ""),
            json.dumps(data, ensure_ascii=True),
        ]
