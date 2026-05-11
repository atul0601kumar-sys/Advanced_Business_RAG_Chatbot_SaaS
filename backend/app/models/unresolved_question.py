import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UnresolvedQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "unresolved_questions"

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
    chat_message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace = relationship("Workspace", back_populates="unresolved_questions")
    chat_session = relationship("ChatSession", back_populates="unresolved_questions")
    chat_message = relationship("ChatMessage", back_populates="unresolved_questions")

