import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Booking(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bookings"

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    chat_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    meeting_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("meeting_types.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    visitor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    visitor_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    visitor_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    start_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="confirmed", index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="internal")
    external_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    meeting_link: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    management_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    reminder_state_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace = relationship("Workspace")
    lead = relationship("Lead")
    chat_session = relationship("ChatSession")
    meeting_type = relationship("MeetingType")
    assigned_user = relationship("User")
    attendees = relationship("BookingAttendee", back_populates="booking")
    events = relationship("BookingEventLog", back_populates="booking")
