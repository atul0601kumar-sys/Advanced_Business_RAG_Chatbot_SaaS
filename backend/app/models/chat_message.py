import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"

    chat_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    token_usage_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chat_session = relationship("ChatSession", back_populates="messages")
    feedback_entries = relationship("Feedback", back_populates="chat_message")
    unresolved_questions = relationship("UnresolvedQuestion", back_populates="chat_message")

