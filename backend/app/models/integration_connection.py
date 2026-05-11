import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class IntegrationConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "integration_type", "display_name", name="uq_integration_workspace_type_name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="inactive", nullable=False, index=True)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    workspace = relationship("Workspace", back_populates="integration_connections")
    deliveries = relationship("IntegrationDelivery", back_populates="integration", cascade="all, delete-orphan")
