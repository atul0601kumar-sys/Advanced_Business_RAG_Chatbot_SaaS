import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class AnalyticsEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_analytics_events_workspace_type_occurred_at", "workspace_id", "event_type", "occurred_at"),
        Index("ix_analytics_events_workspace_name_occurred_at", "workspace_id", "event_name", "occurred_at"),
    )

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chat_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    properties_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    workspace = relationship("Workspace", back_populates="analytics_events")
    user = relationship("User", back_populates="analytics_events")
    chat_session = relationship("ChatSession", back_populates="analytics_events")
