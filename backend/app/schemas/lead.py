import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.input_validator import sanitize_text, validate_webhook_url

LeadStatus = Literal["new", "contacted", "qualified", "converted", "closed"]
LeadPriority = Literal["low", "medium", "high"]
LeadTag = Literal["sales", "support", "general"]


class LeadCreateRequest(BaseModel):
    workspace_id: uuid.UUID
    chat_session_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=5, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    company: str | None = Field(default=None, max_length=255)
    use_case: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=4000)
    source: str = Field(default="chatbot", max_length=50)
    schedule_call_requested: bool = False

    @field_validator("name", "company", "use_case", "message", "source", mode="before")
    @classmethod
    def sanitize_string_fields(cls, value: str | None) -> str | None:
        return sanitize_text(value, max_length=4000)


class LeadUpdateRequest(BaseModel):
    status: LeadStatus | None = None
    priority: LeadPriority | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("notes", mode="before")
    @classmethod
    def sanitize_notes(cls, value: str | None) -> str | None:
        return sanitize_text(value, max_length=4000)


class LeadStatusUpdateRequest(BaseModel):
    workspace_id: uuid.UUID
    lead_id: uuid.UUID
    status: LeadStatus


class LeadNoteRequest(BaseModel):
    workspace_id: uuid.UUID
    lead_id: uuid.UUID
    notes: str = Field(min_length=1, max_length=4000)

    @field_validator("notes", mode="before")
    @classmethod
    def sanitize_note(cls, value: str) -> str:
        return sanitize_text(value, max_length=4000) or ""


class LeadSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    chat_session_id: uuid.UUID | None
    name: str | None
    email: str | None
    phone: str | None
    company: str | None
    use_case: str | None
    message: str | None
    source: str
    status: LeadStatus
    priority: LeadPriority
    tag: LeadTag
    high_intent: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime
    metadata_json: dict | None


class ConversationMessageSummary(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class LeadDetailResponse(BaseModel):
    lead: LeadSummary
    conversation: list[ConversationMessageSummary]
    bookings: list[dict] = Field(default_factory=list)


class LeadListResponse(BaseModel):
    items: list[LeadSummary]
    total: int


class LeadExportRequest(BaseModel):
    workspace_id: uuid.UUID
    status: LeadStatus | None = None
    priority: LeadPriority | None = None
    search: str | None = Field(default=None, max_length=255)
    date_from: datetime | None = None
    date_to: datetime | None = None


class LeadCapturePrompt(BaseModel):
    should_prompt: bool = False
    trigger: str | None = None
    message: str | None = None
    schedule_call_enabled: bool = False
    high_intent: bool = False
    scheduling_intent_detected: bool = False


class LeadCaptureResponse(BaseModel):
    message: str
    lead: LeadSummary


class HumanHandoffRequest(BaseModel):
    session_id: uuid.UUID
    workspace_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=4000)

    @field_validator("reason", "message", mode="before")
    @classmethod
    def sanitize_handoff_fields(cls, value: str | None) -> str | None:
        return sanitize_text(value, max_length=4000)


class HumanHandoffResponse(BaseModel):
    message: str
    needs_human_review: bool
    lead_prompt: LeadCapturePrompt


class NotificationTriggerRule(BaseModel):
    enabled: bool = True
    channels: list[str] = Field(default_factory=lambda: ["email", "webhook"])
    email_recipients: list[str] = Field(default_factory=list)
    webhook_urls: list[str] = Field(default_factory=list)


class NotificationTemplateOverride(BaseModel):
    subject: str | None = Field(default=None, max_length=255)
    text_body: str | None = Field(default=None, max_length=10000)
    html_body: str | None = Field(default=None, max_length=20000)


class LeadCaptureSettingsResponse(BaseModel):
    workspace_id: uuid.UUID
    lead_capture_enabled: bool
    lead_capture_on_first_message: bool
    lead_capture_after_message_count: int
    lead_capture_on_low_confidence: bool
    force_lead_before_chat: bool
    required_fields: list[str]
    schedule_call_enabled: bool
    lead_notifications_enabled: bool
    admin_notification_email: str | None
    notification_webhook_url: str | None
    auto_response_message: str | None
    notification_triggers: dict[str, NotificationTriggerRule] = Field(default_factory=dict)
    notification_template_overrides: dict[str, NotificationTemplateOverride] = Field(default_factory=dict)


class LeadCaptureSettingsUpdateRequest(BaseModel):
    workspace_id: uuid.UUID
    lead_capture_enabled: bool
    lead_capture_on_first_message: bool
    lead_capture_after_message_count: int = Field(ge=1, le=20)
    lead_capture_on_low_confidence: bool
    force_lead_before_chat: bool
    required_fields: list[str] = Field(default_factory=lambda: ["name", "email"])
    schedule_call_enabled: bool
    lead_notifications_enabled: bool
    admin_notification_email: str | None = Field(default=None, max_length=255)
    notification_webhook_url: str | None = Field(default=None, max_length=500)
    auto_response_message: str | None = Field(default=None, max_length=1000)
    notification_triggers: dict[str, NotificationTriggerRule] = Field(default_factory=dict)
    notification_template_overrides: dict[str, NotificationTemplateOverride] = Field(default_factory=dict)

    @field_validator("notification_webhook_url", mode="before")
    @classmethod
    def validate_notification_webhook(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_webhook_url(value)
