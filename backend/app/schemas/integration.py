import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.input_validator import sanitize_json_payload, sanitize_text, validate_webhook_url


IntegrationType = Literal[
    "google_sheets",
    "zapier",
    "make",
    "hubspot",
    "salesforce",
    "slack",
    "discord",
    "whatsapp",
    "telegram",
    "webhook",
]


class IntegrationCatalogItem(BaseModel):
    integration_type: IntegrationType
    label: str
    description: str
    implemented: bool
    supports_events: list[str]
    required_config_fields: list[str] = Field(default_factory=list)
    secret_fields: list[str] = Field(default_factory=list)


class IntegrationConnectionSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    integration_type: IntegrationType
    display_name: str
    status: str
    config: dict[str, Any] = Field(default_factory=dict)
    event_types: list[str] = Field(default_factory=list)
    last_error: str | None = None
    last_tested_at: str | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationDeliverySummary(BaseModel):
    id: uuid.UUID
    integration_id: uuid.UUID
    event_type: str
    status: str
    retry_count: int
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class IntegrationListResponse(BaseModel):
    available_integrations: list[IntegrationCatalogItem]
    connections: list[IntegrationConnectionSummary]
    recent_deliveries: list[IntegrationDeliverySummary]


class IntegrationConnectRequest(BaseModel):
    workspace_id: uuid.UUID
    integration_type: IntegrationType
    display_name: str = Field(min_length=2, max_length=255)
    credentials: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("display_name", mode="before")
    @classmethod
    def sanitize_display_name(cls, value: str) -> str:
        return sanitize_text(value, max_length=255) or ""

    @field_validator("credentials", "config", mode="before")
    @classmethod
    def sanitize_maps(cls, value: dict[str, Any]) -> dict[str, Any]:
        return sanitize_json_payload(value)


class IntegrationUpdateRequest(BaseModel):
    workspace_id: uuid.UUID
    integration_id: uuid.UUID
    display_name: str | None = Field(default=None, min_length=2, max_length=255)
    credentials: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    status: str | None = Field(default=None, max_length=30)

    @field_validator("display_name", "status", mode="before")
    @classmethod
    def sanitize_scalars(cls, value: str | None) -> str | None:
        return sanitize_text(value, max_length=255)

    @field_validator("credentials", "config", mode="before")
    @classmethod
    def sanitize_dicts(cls, value: dict[str, Any]) -> dict[str, Any]:
        return sanitize_json_payload(value)


class IntegrationDisconnectRequest(BaseModel):
    workspace_id: uuid.UUID
    integration_id: uuid.UUID


class IntegrationTestRequest(BaseModel):
    workspace_id: uuid.UUID
    integration_id: uuid.UUID
    event_type: str = Field(default="lead_created", min_length=3, max_length=100)

    @field_validator("event_type", mode="before")
    @classmethod
    def sanitize_event_type(cls, value: str) -> str:
        return sanitize_text(value, max_length=100) or ""


class IntegrationActionResponse(BaseModel):
    message: str
    connection: IntegrationConnectionSummary | None = None


class IntegrationTestResponse(BaseModel):
    message: str
    status: str
    connection: IntegrationConnectionSummary


def normalize_webhook_url_if_present(config: dict[str, Any]) -> dict[str, Any]:
    next_config = dict(config)
    if "webhook_url" in next_config and next_config["webhook_url"]:
        next_config["webhook_url"] = validate_webhook_url(str(next_config["webhook_url"]))
    return next_config
