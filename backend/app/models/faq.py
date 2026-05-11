import uuid

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class FAQ(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "faqs"
    __table_args__ = (
        Index("ix_faqs_workspace_status_category", "workspace_id", "status", "category"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    normalized_question: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    citations_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    workspace = relationship("Workspace")
