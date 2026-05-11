import uuid

from sqlalchemy import BIGINT, JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="upload", nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ingestion_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    workspace = relationship("Workspace", back_populates="documents")
    uploaded_by = relationship("User", back_populates="uploaded_documents")
    chunks = relationship("DocumentChunk", back_populates="document")
    website_sources = relationship("WebsiteSource", back_populates="document")

