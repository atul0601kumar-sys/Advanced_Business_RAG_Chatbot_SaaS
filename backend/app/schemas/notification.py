import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.input_validator import sanitize_json_payload, sanitize_text, validate_webhook_url
from app.schemas.lead import NotificationTemplateOverride, NotificationTriggerRule


class NotificationSettingsResponse(BaseModel):
    workspace_id: uuid.UUID
    notifications_enabled: bool
    email_recipients: list[str]
    webhook_urls: list[str]
    retry_attempts: int
    rate_limit_count: int
    rate_limit_window_seconds: int
    event_rules: dict[str, NotificationTriggerRule]
    template_overrides: dict[str, NotificationTemplateOverride]


class NotificationSettingsUpdateRequest(BaseModel):
    workspace_id: uuid.UUID
    notifications_enabled: bool
    email_recipients: list[str] = Field(default_factory=list)
    webhook_urls: list[str] = Field(default_factory=list)
    retry_attempts: int = Field(default=3, ge=1, le=10)
    rate_limit_count: int = Field(default=20, ge=1, le=500)
    rate_limit_window_seconds: int = Field(default=60, ge=10, le=3600)
    event_rules: dict[str, NotificationTriggerRule] = Field(default_factory=dict)
    template_overrides: dict[str, NotificationTemplateOverride] = Field(default_factory=dict)

    @field_validator("webhook_urls", mode="before")
    @classmethod
    def validate_webhook_targets(cls, value):
        return [validate_webhook_url(item) for item in (value or [])]


class NotificationTestEmailRequest(BaseModel):
    workspace_id: uuid.UUID
    to_addresses: list[str] = Field(default_factory=list)


class NotificationWebhookRequest(BaseModel):
    workspace_id: uuid.UUID
    event_name: str = Field(min_length=3, max_length=100)
    payload: dict = Field(default_factory=dict)
    webhook_urls: list[str] = Field(default_factory=list)

    @field_validator("event_name", mode="before")
    @classmethod
    def sanitize_event_name(cls, value: str) -> str:
        return sanitize_text(value, max_length=100) or ""

    @field_validator("webhook_urls", mode="before")
    @classmethod
    def validate_webhook_urls(cls, value):
        return [validate_webhook_url(item) for item in (value or [])]

    @field_validator("payload", mode="before")
    @classmethod
    def sanitize_payload(cls, value: dict) -> dict:
        return sanitize_json_payload(value)


class NotificationQueueResponse(BaseModel):
    message: str
    queued_jobs: int


class NotificationLogItem(BaseModel):
    id: uuid.UUID
    notification_id: str
    type: str
    channel: str
    status: str
    error_message: str | None
    retry_count: int
    response_code: int | None
    response_body: str | None
    target: str | None
    timestamp: datetime


class NotificationLogsResponse(BaseModel):
    items: list[NotificationLogItem]
    total: int
