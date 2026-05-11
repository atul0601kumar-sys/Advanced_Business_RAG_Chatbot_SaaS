import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    owner = relationship("User", back_populates="owned_workspaces")
    members = relationship("WorkspaceMember", back_populates="workspace")
    documents = relationship("Document", back_populates="workspace")
    website_sources = relationship("WebsiteSource", back_populates="workspace")
    chat_sessions = relationship("ChatSession", back_populates="workspace")
    leads = relationship("Lead", back_populates="workspace")
    feedback_entries = relationship("Feedback", back_populates="workspace")
    analytics_events = relationship("AnalyticsEvent", back_populates="workspace")
    unresolved_questions = relationship("UnresolvedQuestion", back_populates="workspace")
    chatbot_setting = relationship("ChatbotSetting", back_populates="workspace", uselist=False)
    access_logs = relationship("AccessLog", back_populates="workspace")
    audit_logs = relationship("AuditLog", back_populates="workspace")
    integration_connections = relationship("IntegrationConnection", back_populates="workspace")
    integration_deliveries = relationship("IntegrationDelivery", back_populates="workspace")
    notification_jobs = relationship("NotificationJob", back_populates="workspace")
    notification_logs = relationship("NotificationLog", back_populates="workspace")
    export_jobs = relationship("ExportJob", back_populates="workspace")
