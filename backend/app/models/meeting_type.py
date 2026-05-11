import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MeetingType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meeting_types"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_meeting_types_workspace_slug"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(nullable=False, default=30)
    location_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assignment_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="specific")
    provider_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_location_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    manual_location_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_link_token: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    availability_rules_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    workspace = relationship("Workspace")
    assigned_user = relationship("User")
