from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.schemas.settings import PublicChatbotSettingsResponse

settings = get_settings()


class WidgetConfigurator:
    def build_public_payload(self, payload, *, auth_token: str, expires_in_seconds: int) -> PublicChatbotSettingsResponse:
        return PublicChatbotSettingsResponse(
            workspace_id=payload.workspace_id,
            identity=payload.identity,
            behavior=payload.behavior,
            lead_capture=payload.lead_capture,
            handoff=payload.handoff,
            voice=payload.voice,
            widget=payload.widget,
            access_control=payload.access_control,
            analytics=payload.analytics,
            embed={
                "auth_token": auth_token,
                "auth_expires_at": datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
                "api_base_url": settings.widget_public_api_base_url.rstrip("/"),
                "script_url": settings.widget_script_url,
                "version": settings.widget_sdk_version,
                "allowed_origins": payload.widget.allowed_origins,
            },
        )
