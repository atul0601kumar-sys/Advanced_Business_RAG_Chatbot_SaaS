from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from cryptography.fernet import Fernet
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import ensure_workspace_role
from app.core.config import Settings, get_settings
from app.core.input_validator import sanitize_json_payload, sanitize_text
from app.models import IntegrationConnection, IntegrationDelivery, User
from app.schemas.integration import (
    IntegrationActionResponse,
    IntegrationCatalogItem,
    IntegrationConnectRequest,
    IntegrationConnectionSummary,
    IntegrationDeliverySummary,
    IntegrationDisconnectRequest,
    IntegrationListResponse,
    IntegrationTestRequest,
    IntegrationTestResponse,
    IntegrationUpdateRequest,
)
from app.services.base_integration import IntegrationContext, IntegrationResult, IntegrationService
from app.services.integrations import GoogleSheetsIntegration, SlackIntegration, WebhookIntegration

logger = logging.getLogger(__name__)

SUPPORTED_EVENTS = [
    "lead_created",
    "high_priority_lead",
    "chat_started",
    "message_sent",
    "feedback_submitted",
]


class UnsupportedIntegration(IntegrationService):
    def __init__(self, integration_type: str) -> None:
        self.integration_type = integration_type

    def connect(self, context: IntegrationContext):
        raise RuntimeError(f"{self.integration_type} is not implemented yet.")

    def send_event(self, context: IntegrationContext, *, event_type: str, payload: dict[str, Any]):
        raise RuntimeError(f"{self.integration_type} is not implemented yet.")

    def disconnect(self, context: IntegrationContext):
        return IntegrationResult(status_code=200, response_body=f"{self.integration_type} disconnected.")

    def validate_config(self, *, config: dict[str, Any], credentials: dict[str, Any]) -> None:
        raise ValueError(f"{self.integration_type} is not implemented yet.")


class CredentialsCipher:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._fernet = Fernet(self._resolve_key())

    def encrypt(self, payload: dict[str, Any]) -> str:
        encoded = json.dumps(sanitize_json_payload(payload), separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(encoded).decode("utf-8")

    def decrypt(self, token: str | None) -> dict[str, Any]:
        if not token:
            return {}
        decoded = self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        return json.loads(decoded)

    def _resolve_key(self) -> bytes:
        seed = hashlib.sha256(self.settings.resolved_integration_encryption_secret().encode("utf-8")).digest()
        return base64.urlsafe_b64encode(seed)


class IntegrationRegistry:
    def __init__(self) -> None:
        self._catalog: dict[str, IntegrationCatalogItem] = {
            "google_sheets": IntegrationCatalogItem(
                integration_type="google_sheets",
                label="Google Sheets",
                description="Append lead and chat events into a workspace-specific spreadsheet.",
                implemented=True,
                supports_events=SUPPORTED_EVENTS,
                required_config_fields=["spreadsheet_id", "sheet_name"],
                secret_fields=["bearer_token"],
            ),
            "slack": IntegrationCatalogItem(
                integration_type="slack",
                label="Slack",
                description="Send workspace events into a Slack channel.",
                implemented=True,
                supports_events=SUPPORTED_EVENTS,
                required_config_fields=["channel_id"],
                secret_fields=["bot_token"],
            ),
            "webhook": IntegrationCatalogItem(
                integration_type="webhook",
                label="Webhook",
                description="Trigger external automation systems with signed JSON payloads.",
                implemented=True,
                supports_events=SUPPORTED_EVENTS,
                required_config_fields=["webhook_url"],
                secret_fields=[],
            ),
            "zapier": IntegrationCatalogItem(
                integration_type="zapier",
                label="Zapier",
                description="Prepare Zapier automation entrypoints for workspace events.",
                implemented=False,
                supports_events=SUPPORTED_EVENTS,
            ),
            "make": IntegrationCatalogItem(
                integration_type="make",
                label="Make",
                description="Prepare Make scenarios for workspace automations.",
                implemented=False,
                supports_events=SUPPORTED_EVENTS,
            ),
            "hubspot": IntegrationCatalogItem(
                integration_type="hubspot",
                label="HubSpot",
                description="Prepare HubSpot CRM syncing for lead and chat workflows.",
                implemented=False,
                supports_events=SUPPORTED_EVENTS,
            ),
            "salesforce": IntegrationCatalogItem(
                integration_type="salesforce",
                label="Salesforce",
                description="Prepare Salesforce CRM syncing for lead and chat workflows.",
                implemented=False,
                supports_events=SUPPORTED_EVENTS,
            ),
            "discord": IntegrationCatalogItem(
                integration_type="discord",
                label="Discord",
                description="Prepare Discord notifications and workflow hooks.",
                implemented=False,
                supports_events=SUPPORTED_EVENTS,
            ),
            "whatsapp": IntegrationCatalogItem(
                integration_type="whatsapp",
                label="WhatsApp",
                description="Prepare WhatsApp business messaging workflows.",
                implemented=False,
                supports_events=SUPPORTED_EVENTS,
            ),
            "telegram": IntegrationCatalogItem(
                integration_type="telegram",
                label="Telegram",
                description="Prepare Telegram notifications and bot workflows.",
                implemented=False,
                supports_events=SUPPORTED_EVENTS,
            ),
        }
        self._providers: dict[str, IntegrationService] = {
            "google_sheets": GoogleSheetsIntegration(),
            "slack": SlackIntegration(),
            "webhook": WebhookIntegration(),
        }

    def list_catalog(self) -> list[IntegrationCatalogItem]:
        return list(self._catalog.values())

    def get_catalog_item(self, integration_type: str) -> IntegrationCatalogItem:
        item = self._catalog.get(integration_type)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration type is not supported.")
        return item

    def get_provider(self, integration_type: str) -> IntegrationService:
        if integration_type in self._providers:
            return self._providers[integration_type]
        return UnsupportedIntegration(integration_type)


class IntegrationManager:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        registry: IntegrationRegistry | None = None,
        cipher: CredentialsCipher | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.registry = registry or IntegrationRegistry()
        self.cipher = cipher or CredentialsCipher(self.settings)

    def list_integrations(self, db: Session, current_user: User, workspace_id: uuid.UUID) -> IntegrationListResponse:
        ensure_workspace_role(workspace_id, current_user, db, "admin", "team_member", "viewer")
        connections = db.scalars(
            select(IntegrationConnection)
            .where(IntegrationConnection.workspace_id == workspace_id)
            .order_by(IntegrationConnection.created_at.asc())
        ).all()
        recent_deliveries = db.scalars(
            select(IntegrationDelivery)
            .where(IntegrationDelivery.workspace_id == workspace_id)
            .order_by(IntegrationDelivery.created_at.desc())
            .limit(20)
        ).all()
        return IntegrationListResponse(
            available_integrations=self.registry.list_catalog(),
            connections=[self.serialize_connection(item) for item in connections],
            recent_deliveries=[
                IntegrationDeliverySummary(
                    id=item.id,
                    integration_id=item.integration_id,
                    event_type=item.event_type,
                    status=item.status,
                    retry_count=item.retry_count,
                    error_message=item.error_message,
                    created_at=item.created_at,
                    completed_at=item.completed_at,
                )
                for item in recent_deliveries
            ],
        )

    def connect_integration(
        self,
        db: Session,
        current_user: User,
        payload: IntegrationConnectRequest,
    ) -> IntegrationActionResponse:
        ensure_workspace_role(payload.workspace_id, current_user, db, "admin", "team_member")
        catalog = self.registry.get_catalog_item(payload.integration_type)
        if not catalog.implemented:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This integration type is not implemented yet.")
        provider = self.registry.get_provider(payload.integration_type)
        provider.validate_config(config=payload.config, credentials=payload.credentials)
        connection = IntegrationConnection(
            workspace_id=payload.workspace_id,
            integration_type=payload.integration_type,
            display_name=payload.display_name,
            status="active",
            encrypted_credentials=self.cipher.encrypt(payload.credentials),
            config_json=self._normalize_config(payload.config),
            last_error=None,
        )
        provider.connect(self._build_context(connection, payload.credentials))
        db.add(connection)
        db.commit()
        db.refresh(connection)
        return IntegrationActionResponse(message="Integration connected successfully.", connection=self.serialize_connection(connection))

    def update_integration(
        self,
        db: Session,
        current_user: User,
        payload: IntegrationUpdateRequest,
    ) -> IntegrationActionResponse:
        ensure_workspace_role(payload.workspace_id, current_user, db, "admin", "team_member")
        connection = self._get_workspace_connection(db, payload.workspace_id, payload.integration_id)
        credentials = self.cipher.decrypt(connection.encrypted_credentials)
        credentials.update(payload.credentials or {})
        config = dict(connection.config_json or {})
        config.update(payload.config or {})
        provider = self.registry.get_provider(connection.integration_type)
        provider.validate_config(config=config, credentials=credentials)
        if payload.display_name:
            connection.display_name = payload.display_name
        if payload.status:
            connection.status = sanitize_text(payload.status, max_length=30) or connection.status
        connection.encrypted_credentials = self.cipher.encrypt(credentials)
        connection.config_json = self._normalize_config(config)
        connection.last_error = None
        db.commit()
        db.refresh(connection)
        return IntegrationActionResponse(message="Integration updated successfully.", connection=self.serialize_connection(connection))

    def disconnect_integration(
        self,
        db: Session,
        current_user: User,
        payload: IntegrationDisconnectRequest,
    ) -> IntegrationActionResponse:
        ensure_workspace_role(payload.workspace_id, current_user, db, "admin", "team_member")
        connection = self._get_workspace_connection(db, payload.workspace_id, payload.integration_id)
        provider = self.registry.get_provider(connection.integration_type)
        provider.disconnect(self._build_context(connection))
        connection.status = "inactive"
        db.commit()
        db.refresh(connection)
        return IntegrationActionResponse(message="Integration disconnected successfully.", connection=self.serialize_connection(connection))

    def test_integration(
        self,
        db: Session,
        current_user: User,
        payload: IntegrationTestRequest,
    ) -> IntegrationTestResponse:
        ensure_workspace_role(payload.workspace_id, current_user, db, "admin", "team_member")
        connection = self._get_workspace_connection(db, payload.workspace_id, payload.integration_id)
        provider = self.registry.get_provider(connection.integration_type)
        sample_payload = {
            "event_type": payload.event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "workspace_id": str(connection.workspace_id),
            "integration_id": str(connection.id),
            "data": {
                "message": "Integration connectivity test",
                "lead_id": "test-lead",
                "name": "Integration Test",
            },
        }
        provider.send_event(self._build_context(connection), event_type=payload.event_type, payload=sample_payload)
        connection.last_tested_at = datetime.now(UTC).isoformat()
        connection.last_error = None
        connection.status = "active"
        db.commit()
        db.refresh(connection)
        return IntegrationTestResponse(
            message="Integration test completed successfully.",
            status="success",
            connection=self.serialize_connection(connection),
        )

    def serialize_connection(self, connection: IntegrationConnection) -> IntegrationConnectionSummary:
        catalog = self.registry.get_catalog_item(connection.integration_type)
        config = dict(connection.config_json or {})
        return IntegrationConnectionSummary(
            id=connection.id,
            workspace_id=connection.workspace_id,
            integration_type=connection.integration_type,
            display_name=connection.display_name,
            status=connection.status,
            config=config,
            event_types=list(config.get("event_types") or catalog.supports_events),
            last_error=connection.last_error,
            last_tested_at=connection.last_tested_at,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )

    def decrypt_credentials(self, connection: IntegrationConnection) -> dict[str, Any]:
        return self.cipher.decrypt(connection.encrypted_credentials)

    def build_provider_context(self, connection: IntegrationConnection) -> IntegrationContext:
        return self._build_context(connection)

    def _get_workspace_connection(self, db: Session, workspace_id: uuid.UUID, integration_id: uuid.UUID) -> IntegrationConnection:
        connection = db.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.workspace_id == workspace_id,
                IntegrationConnection.id == integration_id,
            )
        )
        if connection is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration connection not found.")
        return connection

    def _build_context(self, connection: IntegrationConnection, credentials_override: dict[str, Any] | None = None) -> IntegrationContext:
        return IntegrationContext(
            workspace_id=str(connection.workspace_id),
            integration_id=str(connection.id),
            display_name=connection.display_name,
            config=dict(connection.config_json or {}),
            credentials=credentials_override if credentials_override is not None else self.decrypt_credentials(connection),
        )

    def _normalize_config(self, config: dict[str, Any]) -> dict[str, Any]:
        next_config = sanitize_json_payload(config)
        events = next_config.get("event_types") or SUPPORTED_EVENTS
        next_config["event_types"] = [sanitize_text(str(item), max_length=100) or "" for item in events if str(item).strip()]
        next_config["rate_limit_count"] = int(next_config.get("rate_limit_count") or self.settings.integration_default_rate_limit_count)
        next_config["rate_limit_window_seconds"] = int(
            next_config.get("rate_limit_window_seconds") or self.settings.integration_default_rate_limit_window_seconds
        )
        next_config["max_retries"] = int(next_config.get("max_retries") or 3)
        return next_config
