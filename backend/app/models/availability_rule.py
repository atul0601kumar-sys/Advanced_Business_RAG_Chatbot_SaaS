import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AvailabilityRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "availability_rules"

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_type_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("meeting_types.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(30), nullable=False, default="workspace")
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False, default="weekly")
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    workspace = relationship("Workspace")
    meeting_type = relationship("MeetingType")
    user = relationship("User")
