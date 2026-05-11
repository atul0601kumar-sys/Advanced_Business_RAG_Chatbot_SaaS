import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Feedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

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
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    workspace = relationship("Workspace", back_populates="feedback_entries")
    user = relationship("User", back_populates="feedback_entries")
    chat_message = relationship("ChatMessage", back_populates="feedback_entries")

