import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WebsiteSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "website_sources"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    page_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    crawl_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    crawl_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    workspace = relationship("Workspace", back_populates="website_sources")
    document = relationship("Document", back_populates="website_sources")
