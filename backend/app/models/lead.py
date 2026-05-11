import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chat_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    use_case: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="chatbot", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="low", nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(50), default="general", nullable=False, index=True)
    high_intent: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    workspace = relationship("Workspace", back_populates="leads")
    chat_session = relationship("ChatSession", back_populates="leads")
