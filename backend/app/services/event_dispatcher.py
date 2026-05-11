from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import IntegrationConnection, IntegrationDelivery

logger = logging.getLogger(__name__)

INTEGRATION_EVENTS = {
    "lead_created",
    "high_priority_lead",
    "chat_started",
    "message_sent",
    "feedback_submitted",
}


class EventDispatcher:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def dispatch(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        if event_type not in INTEGRATION_EVENTS:
            return 0
        integrations = db.scalars(
            select(IntegrationConnection).where(
                IntegrationConnection.workspace_id == workspace_id,
                IntegrationConnection.status == "active",
            )
        ).all()
        queued = 0
        timestamp = datetime.now(UTC)
        for integration in integrations:
            config = integration.config_json or {}
            event_types = set(config.get("event_types") or [])
            if event_types and event_type not in event_types:
                continue
            rate_limit_count = int(config.get("rate_limit_count") or self.settings.integration_default_rate_limit_count)
            rate_limit_window_seconds = int(
                config.get("rate_limit_window_seconds") or self.settings.integration_default_rate_limit_window_seconds
            )
            if self._is_rate_limited(
                db,
                integration_id=integration.id,
                event_type=event_type,
                rate_limit_count=rate_limit_count,
                rate_limit_window_seconds=rate_limit_window_seconds,
            ):
                logger.warning("Integration event rate limited", extra={"integration_id": str(integration.id), "event_type": event_type})
                continue
            db.add(
                IntegrationDelivery(
                    workspace_id=workspace_id,
                    integration_id=integration.id,
                    event_type=event_type,
                    status="pending",
                    payload_json={
                        "event_type": event_type,
                        "timestamp": timestamp.isoformat(),
                        "workspace_id": str(workspace_id),
                        "integration_id": str(integration.id),
                        "data": data,
                    },
                    retry_count=0,
                    max_retries=int(config.get("max_retries") or 3),
                    next_attempt_at=timestamp,
                )
            )
            queued += 1
        return queued

    def _is_rate_limited(
        self,
        db: Session,
        *,
        integration_id: uuid.UUID,
        event_type: str,
        rate_limit_count: int,
        rate_limit_window_seconds: int,
    ) -> bool:
        if rate_limit_count <= 0:
            return False
        window_start = datetime.now(UTC) - timedelta(seconds=rate_limit_window_seconds)
        recent = db.scalars(
            select(IntegrationDelivery).where(
                IntegrationDelivery.integration_id == integration_id,
                IntegrationDelivery.event_type == event_type,
                IntegrationDelivery.created_at >= window_start,
            )
        ).all()
        return len(recent) >= rate_limit_count
