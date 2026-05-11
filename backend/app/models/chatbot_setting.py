import uuid

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ChatbotSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chatbot_settings"
    __table_args__ = (UniqueConstraint("workspace_id", name="uq_chatbot_settings_workspace_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), default="gpt-4.1-mini", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    max_context_chunks: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    lead_capture_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lead_capture_on_first_message: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lead_capture_after_message_count: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    lead_capture_on_low_confidence: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    schedule_call_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    force_lead_before_chat: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lead_required_fields_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    lead_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lead_auto_response_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notification_webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notification_email_recipients_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    notification_webhook_urls_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    notification_retry_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    notification_rate_limit_count: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    notification_rate_limit_window_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    notification_triggers_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notification_template_overrides_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    allowed_domains_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    identity_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    behavior_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prompt_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lead_capture_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    handoff_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    voice_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    widget_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    access_control_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    knowledge_base_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analytics_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    workspace = relationship("Workspace", back_populates="chatbot_setting")
