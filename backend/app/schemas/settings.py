import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.input_validator import sanitize_text, validate_origin_value, validate_webhook_url
from app.schemas.lead import NotificationTemplateOverride, NotificationTriggerRule
from app.schemas.widget import WidgetEmbedMetadata


ToneOption = Literal["professional", "friendly", "concise", "detailed"]
ResponseStyleOption = Literal["paragraph", "bullet_points", "mixed"]
WidgetPositionOption = Literal["left", "right"]
WidgetSizeOption = Literal["compact", "comfortable", "expanded"]
WidgetThemeOption = Literal["light", "dark", "auto"]
ChatbotModeOption = Literal["public", "private"]


class ChatbotIdentitySettings(BaseModel):
    bot_name: str = Field(min_length=1, max_length=255)
    bot_avatar: str | None = Field(default=None, max_length=2_000_000)
    brand_color_primary: str = Field(min_length=4, max_length=20)
    brand_color_secondary: str = Field(min_length=4, max_length=20)
    logo: str | None = Field(default=None, max_length=2_000_000)
    tagline: str | None = Field(default=None, max_length=255)
    welcome_message: str = Field(min_length=1, max_length=2000)


class ChatBehaviorSettings(BaseModel):
    tone: ToneOption = "professional"
    response_style: ResponseStyleOption = "paragraph"
    max_response_length: int = Field(default=900, ge=120, le=4000)
    markdown_enabled: bool = True
    citations_enabled: bool = True
    confidence_score_enabled: bool = True


class PromptCustomizationSettings(BaseModel):
    custom_system_prompt: str | None = Field(default=None, max_length=8000)
    company_instructions: str | None = Field(default=None, max_length=4000)
    business_rules: str | None = Field(default=None, max_length=4000)

    @field_validator("custom_system_prompt", "company_instructions", "business_rules", mode="before")
    @classmethod
    def sanitize_prompt_fields(cls, value: str | None) -> str | None:
        return sanitize_text(value, max_length=8000)


class LeadCaptureCustomizationSettings(BaseModel):
    enabled: bool = False
    force_before_chat: bool = False
    trigger_on_first_message: bool = False
    trigger_on_low_confidence: bool = True
    trigger_after_n_messages: int = Field(default=4, ge=1, le=20)
    required_fields: list[str] = Field(default_factory=lambda: ["name", "email"])
    custom_form_message: str | None = Field(default=None, max_length=1000)
    auto_response_message: str | None = Field(default=None, max_length=1000)


class HumanHandoffSettings(BaseModel):
    enabled: bool = True
    custom_message: str | None = Field(default=None, max_length=1000)
    enable_scheduling: bool = False
    escalate_on_low_confidence: bool = True
    escalate_on_repeated_failures: bool = True


class VoiceSettings(BaseModel):
    voice_input_enabled: bool = False
    voice_output_enabled: bool = False
    voice_style: str | None = Field(default=None, max_length=100)
    transcript_preview_enabled: bool = True
    auto_read_assistant_responses: bool = False


class WidgetCustomizationSettings(BaseModel):
    position: WidgetPositionOption = "right"
    size: WidgetSizeOption = "comfortable"
    theme: WidgetThemeOption = "auto"
    welcome_popup_message: str | None = Field(default=None, max_length=500)
    launcher_icon: str | None = Field(default=None, max_length=2_000_000)
    show_branding: bool = True
    delay_before_appearance_seconds: int = Field(default=2, ge=0, le=120)
    allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def validate_allowed_origins(cls, value):
        return [validate_origin_value(item) for item in (value or [])]


class AccessControlSettings(BaseModel):
    restrict_to_logged_in_users: bool = False
    chatbot_mode: ChatbotModeOption = "public"
    allow_guest_access: bool = True
    rate_limit_per_user_per_minute: int = Field(default=30, ge=1, le=1000)


class KnowledgeBaseSettings(BaseModel):
    disabled_document_ids: list[uuid.UUID] = Field(default_factory=list)
    disabled_urls: list[str] = Field(default_factory=list)
    prioritized_document_ids: list[uuid.UUID] = Field(default_factory=list)
    prioritized_urls: list[str] = Field(default_factory=list)
    chunk_relevance_threshold: float = Field(default=0.15, ge=0.0, le=1.0)


class AnalyticsPreferencesSettings(BaseModel):
    tracking_enabled: bool = True
    feedback_collection_enabled: bool = True
    anonymize_user_data: bool = False


class NotificationChannelSettings(BaseModel):
    enabled: bool = True
    notification_types: list[str] = Field(default_factory=lambda: ["new_lead", "high_priority_lead", "handoff_requested", "negative_feedback"])
    email_recipients: list[str] = Field(default_factory=list)
    webhook_endpoints: list[str] = Field(default_factory=list)
    retry_attempts: int = Field(default=3, ge=1, le=10)
    triggers: dict[str, NotificationTriggerRule] = Field(default_factory=dict)
    template_overrides: dict[str, NotificationTemplateOverride] = Field(default_factory=dict)

    @field_validator("webhook_endpoints", mode="before")
    @classmethod
    def validate_webhook_endpoints(cls, value):
        return [validate_webhook_url(item) for item in (value or [])]


class ChatbotSettingsResponse(BaseModel):
    workspace_id: uuid.UUID
    identity: ChatbotIdentitySettings
    behavior: ChatBehaviorSettings
    prompt: PromptCustomizationSettings
    lead_capture: LeadCaptureCustomizationSettings
    handoff: HumanHandoffSettings
    voice: VoiceSettings
    widget: WidgetCustomizationSettings
    access_control: AccessControlSettings
    knowledge_base: KnowledgeBaseSettings
    analytics: AnalyticsPreferencesSettings
    notifications: NotificationChannelSettings
    updated_at: datetime


class ChatbotSettingsUpdateRequest(BaseModel):
    workspace_id: uuid.UUID
    identity: ChatbotIdentitySettings
    behavior: ChatBehaviorSettings
    prompt: PromptCustomizationSettings
    lead_capture: LeadCaptureCustomizationSettings
    handoff: HumanHandoffSettings
    voice: VoiceSettings
    widget: WidgetCustomizationSettings
    access_control: AccessControlSettings
    knowledge_base: KnowledgeBaseSettings
    analytics: AnalyticsPreferencesSettings
    notifications: NotificationChannelSettings


class PublicChatbotSettingsResponse(BaseModel):
    workspace_id: uuid.UUID
    identity: ChatbotIdentitySettings
    behavior: ChatBehaviorSettings
    lead_capture: LeadCaptureCustomizationSettings
    handoff: HumanHandoffSettings
    voice: VoiceSettings
    widget: WidgetCustomizationSettings
    access_control: AccessControlSettings
    analytics: AnalyticsPreferencesSettings
    embed: WidgetEmbedMetadata
