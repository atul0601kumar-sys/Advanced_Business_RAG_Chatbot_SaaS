from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    session_nonce: Mapped[str] = mapped_column(String(64), default="bootstrap-session", nullable=False)
    account_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    owned_workspaces = relationship("Workspace", back_populates="owner")
    workspace_memberships = relationship("WorkspaceMember", back_populates="user")
    uploaded_documents = relationship("Document", back_populates="uploaded_by")
    chat_sessions = relationship("ChatSession", back_populates="user")
    feedback_entries = relationship("Feedback", back_populates="user")
    analytics_events = relationship("AnalyticsEvent", back_populates="user")
    access_logs = relationship("AccessLog", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    export_jobs = relationship("ExportJob", back_populates="requested_by")
