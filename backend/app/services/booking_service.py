from __future__ import annotations

import hashlib
import secrets
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.dependencies.auth import get_workspace_member
from app.models import (
    BlackoutDate,
    Booking,
    BookingAttendee,
    BookingEventLog,
    CalendarConnection,
    ChatSession,
    Lead,
    MeetingType,
    User,
    Workspace,
    WorkspaceMember,
)
from app.schemas.lead import LeadUpdateRequest
from app.schemas.scheduling import (
    AvailabilityResponse,
    BlackoutDateCreateRequest,
    BlackoutDateSummary,
    BookingCancelRequest,
    BookingCreateRequest,
    BookingListResponse,
    BookingRescheduleRequest,
    BookingSlotsRequest,
    BookingSlotsResponse,
    BookingSummary,
    CalendarConnectionSummary,
    CalendarConnectRequest,
    CalendarDisconnectRequest,
    CalendarProviderDescriptor,
    CalendarStatusResponse,
    MeetingTypeCreateRequest,
    MeetingTypeListResponse,
    MeetingTypeSummary,
    PublicBookingWorkspaceResponse,
)
from app.services.availability_service import AvailabilityService
from app.services.calcom_provider import CalComProvider
from app.services.calendar_provider_base import CalendarProviderBase
from app.services.event_tracker import EventTracker
from app.services.google_calendar_provider import GoogleCalendarProvider
from app.services.lead_service import LeadService
from app.services.notification_service import NotificationService
from app.services.outlook_calendar_provider import OutlookCalendarProvider
from app.services.scheduling_crypto import SchedulingCryptoService
from app.services.slot_generator import SlotGenerator

ACTIVE_BOOKING_STATUSES = {"pending", "confirmed", "rescheduled"}


class BookingService:
    def __init__(
        self,
        *,
        availability_service: AvailabilityService | None = None,
        notification_service: NotificationService | None = None,
        event_tracker: EventTracker | None = None,
        lead_service: LeadService | None = None,
        slot_generator: SlotGenerator | None = None,
        crypto_service: SchedulingCryptoService | None = None,
    ) -> None:
        self.settings = get_settings()
        self.availability_service = availability_service or AvailabilityService()
        self.notification_service = notification_service or NotificationService()
        self.event_tracker = event_tracker or EventTracker()
        self.lead_service = lead_service or LeadService()
        self.slot_generator = slot_generator or SlotGenerator()
        self.crypto_service = crypto_service or SchedulingCryptoService()
        self.providers: dict[str, CalendarProviderBase] = {
            "google": GoogleCalendarProvider(),
            "outlook": OutlookCalendarProvider(),
            "calcom": CalComProvider(),
        }

    def list_providers(self) -> list[CalendarProviderDescriptor]:
        return [
            CalendarProviderDescriptor(provider="google", label="Google Calendar", auth_type="oauth", supports_busy_lookup=True, supports_event_creation=True, supports_video_link=True, supports_oauth=True),
            CalendarProviderDescriptor(provider="outlook", label="Outlook Calendar", auth_type="oauth", supports_busy_lookup=True, supports_event_creation=True, supports_video_link=True, supports_oauth=True),
            CalendarProviderDescriptor(provider="calcom", label="Cal.com", auth_type="api_key", supports_busy_lookup=True, supports_event_creation=True, supports_video_link=True, supports_oauth=False),
            CalendarProviderDescriptor(provider="external_link", label="External booking link", auth_type="link", supports_busy_lookup=False, supports_event_creation=False, supports_video_link=False, supports_oauth=False),
        ]

    def connect_calendar(self, db: Session, current_user: User, payload: CalendarConnectRequest) -> CalendarConnectionSummary:
        membership = get_workspace_member(payload.workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        connection = db.scalar(
            select(CalendarConnection).where(
                CalendarConnection.workspace_id == payload.workspace_id,
                CalendarConnection.provider == payload.provider,
                CalendarConnection.user_id == payload.user_id,
            )
        )
        metadata = payload.metadata or {}
        if payload.provider == "calcom":
            metadata["access_token"] = payload.api_key or payload.access_token
            metadata.setdefault("base_url", "https://api.cal.com")
        elif payload.provider == "external_link":
            metadata["external_booking_url"] = payload.external_booking_url
        if connection is None:
            connection = CalendarConnection(
                workspace_id=payload.workspace_id,
                user_id=payload.user_id,
                provider=payload.provider,
                status="connected",
            )
            db.add(connection)
        connection.status = "connected"
        connection.access_token_encrypted = self.crypto_service.encrypt(payload.access_token or payload.api_key)
        connection.refresh_token_encrypted = self.crypto_service.encrypt(payload.refresh_token)
        connection.external_account_id = payload.external_account_id
        connection.external_account_email = payload.external_account_email
        connection.metadata_json = metadata
        db.commit()
        db.refresh(connection)
        return self._serialize_connection(connection)

    def disconnect_calendar(self, db: Session, current_user: User, payload: CalendarDisconnectRequest) -> dict[str, str]:
        membership = get_workspace_member(payload.workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        connection = db.scalar(
            select(CalendarConnection).where(
                CalendarConnection.workspace_id == payload.workspace_id,
                CalendarConnection.provider == payload.provider,
                CalendarConnection.user_id == payload.user_id,
            )
        )
        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar connection not found.")
        db.delete(connection)
        db.commit()
        return {"message": "Calendar disconnected successfully."}

    def get_calendar_status(self, db: Session, current_user: User, workspace_id: uuid.UUID) -> CalendarStatusResponse:
        get_workspace_member(workspace_id, current_user, db)
        items = db.scalars(select(CalendarConnection).where(CalendarConnection.workspace_id == workspace_id).order_by(CalendarConnection.created_at.desc())).all()
        return CalendarStatusResponse(workspace_id=workspace_id, items=[self._serialize_connection(item) for item in items])

    def create_meeting_type(self, db: Session, current_user: User, payload: MeetingTypeCreateRequest) -> MeetingTypeSummary:
        membership = get_workspace_member(payload.workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        meeting_type = MeetingType(
            workspace_id=payload.workspace_id,
            title=payload.title.strip(),
            slug=self._slugify(payload.title),
            description=payload.description,
            duration_minutes=payload.duration_minutes,
            location_type=payload.location_type,
            assigned_user_id=payload.assigned_user_id,
            assignment_mode=payload.assignment_mode,
            provider_preference=payload.provider_preference,
            external_location_url=payload.external_location_url,
            manual_location_text=payload.manual_location_text,
            booking_link_token=secrets.token_urlsafe(16),
            availability_rules_json=payload.availability_rules,
            metadata_json=payload.metadata,
            is_active=True,
        )
        db.add(meeting_type)
        db.commit()
        db.refresh(meeting_type)
        return self._serialize_meeting_type(meeting_type, workspace_slug=self._workspace_slug(db, payload.workspace_id))

    def update_meeting_type(self, db: Session, current_user: User, meeting_type_id: uuid.UUID, payload: MeetingTypeCreateRequest) -> MeetingTypeSummary:
        membership = get_workspace_member(payload.workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        meeting_type = self._get_meeting_type(db, payload.workspace_id, meeting_type_id)
        meeting_type.title = payload.title.strip()
        meeting_type.slug = self._slugify(payload.title)
        meeting_type.description = payload.description
        meeting_type.duration_minutes = payload.duration_minutes
        meeting_type.location_type = payload.location_type
        meeting_type.assigned_user_id = payload.assigned_user_id
        meeting_type.assignment_mode = payload.assignment_mode
        meeting_type.provider_preference = payload.provider_preference
        meeting_type.external_location_url = payload.external_location_url
        meeting_type.manual_location_text = payload.manual_location_text
        meeting_type.availability_rules_json = payload.availability_rules
        meeting_type.metadata_json = payload.metadata
        db.commit()
        db.refresh(meeting_type)
        return self._serialize_meeting_type(meeting_type, workspace_slug=self._workspace_slug(db, payload.workspace_id))

    def delete_meeting_type(self, db: Session, current_user: User, workspace_id: uuid.UUID, meeting_type_id: uuid.UUID) -> dict[str, str]:
        membership = get_workspace_member(workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        meeting_type = self._get_meeting_type(db, workspace_id, meeting_type_id)
        db.delete(meeting_type)
        db.commit()
        return {"message": "Meeting type deleted successfully."}

    def list_meeting_types(self, db: Session, current_user: User, workspace_id: uuid.UUID) -> MeetingTypeListResponse:
        get_workspace_member(workspace_id, current_user, db)
        items = db.scalars(select(MeetingType).where(MeetingType.workspace_id == workspace_id).order_by(MeetingType.created_at.desc())).all()
        slug = self._workspace_slug(db, workspace_id)
        return MeetingTypeListResponse(items=[self._serialize_meeting_type(item, workspace_slug=slug) for item in items])

    def create_blackout(self, db: Session, current_user: User, payload: BlackoutDateCreateRequest) -> BlackoutDateSummary:
        membership = get_workspace_member(payload.workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        blackout = BlackoutDate(
            workspace_id=payload.workspace_id,
            meeting_type_id=payload.meeting_type_id,
            user_id=payload.user_id,
            title=payload.title,
            reason=payload.reason,
            start_time_utc=payload.start_time.astimezone(UTC),
            end_time_utc=payload.end_time.astimezone(UTC),
            timezone=payload.timezone,
        )
        db.add(blackout)
        db.commit()
        db.refresh(blackout)
        return self._serialize_blackout(blackout)

    def delete_blackout(self, db: Session, current_user: User, workspace_id: uuid.UUID, blackout_id: uuid.UUID) -> dict[str, str]:
        membership = get_workspace_member(workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        blackout = db.scalar(select(BlackoutDate).where(BlackoutDate.id == blackout_id, BlackoutDate.workspace_id == workspace_id))
        if not blackout:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blackout date not found.")
        db.delete(blackout)
        db.commit()
        return {"message": "Blackout date deleted successfully."}

    def list_blackouts(self, db: Session, current_user: User, workspace_id: uuid.UUID) -> list[BlackoutDateSummary]:
        get_workspace_member(workspace_id, current_user, db)
        items = db.scalars(select(BlackoutDate).where(BlackoutDate.workspace_id == workspace_id).order_by(BlackoutDate.start_time_utc.asc())).all()
        return [self._serialize_blackout(item) for item in items]

    def get_booking_slots(self, db: Session, actor: User | None, payload: BookingSlotsRequest) -> BookingSlotsResponse:
        if actor is not None:
            get_workspace_member(payload.workspace_id, actor, db)
        meeting_type = self._get_meeting_type(db, payload.workspace_id, payload.meeting_type_id)
        assigned_user_id = self._select_assignee(db, payload.workspace_id, meeting_type, desired_start=None)
        availability = self.availability_service.get_runtime_config(db, workspace_id=payload.workspace_id, meeting_type_id=meeting_type.id, user_id=assigned_user_id)
        now_utc = datetime.now(UTC)
        range_start_utc = (payload.start_date or now_utc).astimezone(UTC)
        range_end_utc = (payload.end_date or (range_start_utc + timedelta(days=availability.settings.future_booking_window_days))).astimezone(UTC)
        busy_windows = self._load_busy_windows(db, payload.workspace_id, assigned_user_id, range_start_utc, range_end_utc, exclude_booking_id=payload.reschedule_booking_id)
        blackout_windows = self._load_blackout_windows(db, payload.workspace_id, meeting_type.id, assigned_user_id, range_start_utc, range_end_utc)
        existing_counts = self._load_daily_booking_counts(db, payload.workspace_id, assigned_user_id, range_start_utc, range_end_utc)
        provider_connection = self._pick_calendar_connection(db, payload.workspace_id, assigned_user_id, meeting_type.provider_preference)
        if provider_connection and provider_connection.provider == "calcom":
            provider = self.providers["calcom"]
            provider_slots = provider.get_available_slots(  # type: ignore[attr-defined]
                connection_metadata=self._connection_runtime_metadata(provider_connection),
                start_time_utc=range_start_utc,
                end_time_utc=range_end_utc,
                timezone=payload.timezone,
                meeting_type_metadata=meeting_type.metadata_json,
            )
            for slot in provider_slots:
                slot.assigned_user_id = assigned_user_id
            return BookingSlotsResponse(workspace_id=payload.workspace_id, meeting_type_id=meeting_type.id, timezone=payload.timezone, slots=provider_slots)
        if provider_connection and meeting_type.provider_preference in self.providers:
            provider_busy = self.providers[meeting_type.provider_preference].get_busy_slots(
                connection_metadata=self._connection_runtime_metadata(provider_connection),
                start_time_utc=range_start_utc,
                end_time_utc=range_end_utc,
                timezone=payload.timezone,
                meeting_type_metadata=meeting_type.metadata_json,
            )
            busy_windows.extend((item.start_time_utc, item.end_time_utc) for item in provider_busy)
        slots = self.slot_generator.generate_slots(
            availability=availability,
            visitor_timezone=payload.timezone,
            duration_minutes=meeting_type.duration_minutes,
            range_start_utc=range_start_utc,
            range_end_utc=range_end_utc,
            busy_windows=busy_windows,
            blackout_windows=blackout_windows,
            existing_booking_windows=[],
            max_bookings_per_day=existing_counts,
        )
        for slot in slots:
            slot.assigned_user_id = assigned_user_id
            slot.provider = meeting_type.provider_preference or "internal"
        return BookingSlotsResponse(workspace_id=payload.workspace_id, meeting_type_id=meeting_type.id, timezone=payload.timezone, slots=slots)

    def create_booking(
        self,
        db: Session,
        actor: User | None,
        payload: BookingCreateRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> BookingSummary:
        if actor is not None:
            get_workspace_member(payload.workspace_id, actor, db)
        meeting_type = self._get_meeting_type(db, payload.workspace_id, payload.meeting_type_id)
        assigned_user_id = self._select_assignee(db, payload.workspace_id, meeting_type, desired_start=payload.start_time_utc)
        availability = self.availability_service.get_runtime_config(db, workspace_id=payload.workspace_id, meeting_type_id=meeting_type.id, user_id=assigned_user_id)
        start_time_utc = payload.start_time_utc.astimezone(UTC)
        end_time_utc = start_time_utc + timedelta(minutes=meeting_type.duration_minutes)
        self._assert_slot_available(db, payload.workspace_id, meeting_type, assigned_user_id, start_time_utc, end_time_utc, payload.timezone, availability)
        management_token = secrets.token_urlsafe(24)
        booking = Booking(
            workspace_id=payload.workspace_id,
            lead_id=payload.lead_id,
            chat_session_id=payload.chat_session_id,
            meeting_type_id=meeting_type.id,
            assigned_user_id=assigned_user_id,
            visitor_name=payload.visitor_name.strip(),
            visitor_email=payload.visitor_email.strip().lower(),
            visitor_phone=payload.visitor_phone.strip() if payload.visitor_phone else None,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            timezone=payload.timezone,
            status="confirmed",
            provider=meeting_type.provider_preference or "internal",
            management_token_hash=self._hash_management_token(management_token),
            metadata_json={
                "preferred_location_type": payload.preferred_location_type,
                "preferred_date_note": payload.preferred_date_note,
            },
            reminder_state_json={},
        )
        db.add(booking)
        db.flush()
        db.add(
            BookingAttendee(
                booking_id=booking.id,
                name=booking.visitor_name,
                email=booking.visitor_email,
                phone=booking.visitor_phone,
                timezone=payload.timezone,
                is_primary=True,
            )
        )
        self._log_event(db, booking, "booking.created", actor_type="user" if actor else "visitor", actor_id=str(actor.id) if actor else booking.visitor_email)
        self._sync_external_calendar(db, booking, meeting_type, action="create")
        if booking.lead_id:
            lead = db.get(Lead, booking.lead_id)
            if lead:
                lead.status = "qualified"
        self.event_tracker.track_event(
            db,
            workspace_id=booking.workspace_id,
            user_id=assigned_user_id,
            session_id=booking.chat_session_id,
            event_type="booking_created",
            metadata={"booking_id": booking.id, "meeting_type_id": booking.meeting_type_id, "status": booking.status},
        )
        db.commit()
        db.refresh(booking)
        self._queue_booking_notifications(db, booking, background_tasks, "booking.created")
        return self._serialize_booking(db, booking, management_token=management_token)

    def reschedule_booking(
        self,
        db: Session,
        actor: User | None,
        payload: BookingRescheduleRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> BookingSummary:
        booking, management_token = self._resolve_manageable_booking(db, actor, payload.workspace_id, payload.booking_id, payload.token)
        meeting_type = self._get_meeting_type(db, payload.workspace_id, booking.meeting_type_id)
        new_start = payload.start_time_utc.astimezone(UTC)
        new_end = new_start + timedelta(minutes=meeting_type.duration_minutes)
        availability = self.availability_service.get_runtime_config(db, workspace_id=payload.workspace_id, meeting_type_id=meeting_type.id, user_id=booking.assigned_user_id)
        self._assert_slot_available(db, payload.workspace_id, meeting_type, booking.assigned_user_id, new_start, new_end, payload.timezone, availability, exclude_booking_id=booking.id)
        booking.status = "rescheduled"
        booking.start_time_utc = new_start
        booking.end_time_utc = new_end
        booking.timezone = payload.timezone
        self._log_event(db, booking, "booking.rescheduled", actor_type="user" if actor else "visitor", actor_id=str(actor.id) if actor else booking.visitor_email)
        self._sync_external_calendar(db, booking, meeting_type, action="reschedule")
        self.event_tracker.track_event(
            db,
            workspace_id=booking.workspace_id,
            user_id=booking.assigned_user_id,
            session_id=booking.chat_session_id,
            event_type="booking_rescheduled",
            metadata={"booking_id": booking.id, "meeting_type_id": booking.meeting_type_id},
        )
        db.commit()
        db.refresh(booking)
        self._queue_booking_notifications(db, booking, background_tasks, "booking.rescheduled")
        return self._serialize_booking(db, booking, management_token=management_token)

    def cancel_booking(
        self,
        db: Session,
        actor: User | None,
        payload: BookingCancelRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, str]:
        booking, _ = self._resolve_manageable_booking(db, actor, payload.workspace_id, payload.booking_id, payload.token)
        meeting_type = self._get_meeting_type(db, payload.workspace_id, booking.meeting_type_id)
        booking.status = "cancelled"
        booking.cancelled_at = datetime.now(UTC)
        self._log_event(db, booking, "booking.cancelled", actor_type="user" if actor else "visitor", actor_id=str(actor.id) if actor else booking.visitor_email, message=payload.reason)
        self._sync_external_calendar(db, booking, meeting_type, action="cancel", reason=payload.reason)
        self.event_tracker.track_event(
            db,
            workspace_id=booking.workspace_id,
            user_id=booking.assigned_user_id,
            session_id=booking.chat_session_id,
            event_type="booking_cancelled",
            metadata={"booking_id": booking.id, "meeting_type_id": booking.meeting_type_id},
        )
        db.commit()
        self._queue_booking_notifications(db, booking, background_tasks, "booking.cancelled")
        return {"message": "Booking cancelled successfully."}

    def list_bookings(self, db: Session, current_user: User, *, workspace_id: uuid.UUID, status_filter: str | None, date_from: datetime | None, date_to: datetime | None, assigned_user_id: uuid.UUID | None) -> BookingListResponse:
        get_workspace_member(workspace_id, current_user, db)
        query = select(Booking).where(Booking.workspace_id == workspace_id)
        if status_filter:
            query = query.where(Booking.status == status_filter)
        if date_from:
            query = query.where(Booking.start_time_utc >= date_from)
        if date_to:
            query = query.where(Booking.end_time_utc <= date_to)
        if assigned_user_id:
            query = query.where(Booking.assigned_user_id == assigned_user_id)
        items = db.scalars(query.order_by(Booking.start_time_utc.desc())).all()
        return BookingListResponse(items=[self._serialize_booking(db, item) for item in items], total=len(items))

    def get_booking(self, db: Session, actor: User | None, workspace_id: uuid.UUID, booking_id: uuid.UUID | None = None, token: str | None = None) -> BookingSummary:
        booking, management_token = self._resolve_manageable_booking(db, actor, workspace_id, booking_id, token)
        return self._serialize_booking(db, booking, management_token=management_token)

    def get_booking_by_token(self, db: Session, token: str) -> BookingSummary:
        token_hash = self._hash_management_token(token)
        booking = db.scalar(select(Booking).where(Booking.management_token_hash == token_hash))
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
        return self._serialize_booking(db, booking, management_token=token)

    def get_public_booking_workspace(self, db: Session, workspace_slug: str) -> PublicBookingWorkspaceResponse:
        workspace = db.scalar(select(Workspace).where(Workspace.slug == workspace_slug))
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        availability = self.availability_service.get_runtime_config(db, workspace_id=workspace.id)
        meeting_types = db.scalars(select(MeetingType).where(MeetingType.workspace_id == workspace.id, MeetingType.is_active.is_(True)).order_by(MeetingType.title.asc())).all()
        return PublicBookingWorkspaceResponse(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            workspace_slug=workspace.slug,
            admin_timezone=availability.settings.timezone,
            meeting_types=[self._serialize_meeting_type(item, workspace_slug=workspace.slug) for item in meeting_types],
        )

    def _serialize_connection(self, connection: CalendarConnection) -> CalendarConnectionSummary:
        return CalendarConnectionSummary(
            id=connection.id,
            workspace_id=connection.workspace_id,
            user_id=connection.user_id,
            provider=connection.provider,  # type: ignore[arg-type]
            status=connection.status,
            external_account_id=connection.external_account_id,
            external_account_email=connection.external_account_email,
            metadata={k: v for k, v in (connection.metadata_json or {}).items() if k not in {"access_token"}},
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )

    def _serialize_meeting_type(self, meeting_type: MeetingType, *, workspace_slug: str) -> MeetingTypeSummary:
        return MeetingTypeSummary(
            id=meeting_type.id,
            workspace_id=meeting_type.workspace_id,
            title=meeting_type.title,
            slug=meeting_type.slug,
            description=meeting_type.description,
            duration_minutes=meeting_type.duration_minutes,
            location_type=meeting_type.location_type,  # type: ignore[arg-type]
            assigned_user_id=meeting_type.assigned_user_id,
            assignment_mode=meeting_type.assignment_mode,  # type: ignore[arg-type]
            provider_preference=meeting_type.provider_preference,  # type: ignore[arg-type]
            external_location_url=meeting_type.external_location_url,
            manual_location_text=meeting_type.manual_location_text,
            booking_link=f"{self.settings.frontend_url.rstrip('/')}/book/{workspace_slug}?meeting={meeting_type.slug}",
            availability_rules=meeting_type.availability_rules_json,
            metadata=meeting_type.metadata_json,
            is_active=meeting_type.is_active,
            created_at=meeting_type.created_at,
            updated_at=meeting_type.updated_at,
        )

    def _serialize_blackout(self, blackout: BlackoutDate) -> BlackoutDateSummary:
        return BlackoutDateSummary(
            id=blackout.id,
            workspace_id=blackout.workspace_id,
            meeting_type_id=blackout.meeting_type_id,
            user_id=blackout.user_id,
            title=blackout.title,
            reason=blackout.reason,
            start_time_utc=blackout.start_time_utc,
            end_time_utc=blackout.end_time_utc,
            timezone=blackout.timezone,
            created_at=blackout.created_at,
        )

    def _serialize_booking(self, db: Session, booking: Booking, *, management_token: str | None = None) -> BookingSummary:
        meeting_type = db.get(MeetingType, booking.meeting_type_id)
        user = db.get(User, booking.assigned_user_id) if booking.assigned_user_id else None
        attendees = db.scalars(select(BookingAttendee).where(BookingAttendee.booking_id == booking.id).order_by(BookingAttendee.created_at.asc())).all()
        token = management_token or ""
        base_url = self.settings.frontend_url.rstrip("/")
        manage_url = f"{base_url}/book/manage/{token}" if token else f"{base_url}/dashboard/scheduling?booking={booking.id}"
        return BookingSummary(
            id=booking.id,
            workspace_id=booking.workspace_id,
            lead_id=booking.lead_id,
            chat_session_id=booking.chat_session_id,
            meeting_type_id=booking.meeting_type_id,
            meeting_type_title=meeting_type.title if meeting_type else "Meeting",
            assigned_user_id=booking.assigned_user_id,
            assigned_user_name=user.full_name if user else None,
            visitor_name=booking.visitor_name,
            visitor_email=booking.visitor_email,
            visitor_phone=booking.visitor_phone,
            start_time_utc=booking.start_time_utc,
            end_time_utc=booking.end_time_utc,
            timezone=booking.timezone,
            status=booking.status,  # type: ignore[arg-type]
            provider=booking.provider,
            external_event_id=booking.external_event_id,
            meeting_link=booking.meeting_link,
            management_url=manage_url,
            public_reschedule_url=f"{manage_url}?action=reschedule",
            public_cancel_url=f"{manage_url}?action=cancel",
            attendees=[
                {
                    "id": attendee.id,
                    "name": attendee.name,
                    "email": attendee.email,
                    "phone": attendee.phone,
                    "timezone": attendee.timezone,
                    "is_primary": attendee.is_primary,
                }
                for attendee in attendees
            ],
            metadata=booking.metadata_json,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
        )

    def _get_meeting_type(self, db: Session, workspace_id: uuid.UUID, meeting_type_id: uuid.UUID) -> MeetingType:
        meeting_type = db.scalar(select(MeetingType).where(MeetingType.id == meeting_type_id, MeetingType.workspace_id == workspace_id))
        if not meeting_type:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting type not found.")
        return meeting_type

    def _workspace_slug(self, db: Session, workspace_id: uuid.UUID) -> str:
        workspace = db.get(Workspace, workspace_id)
        return workspace.slug if workspace else "workspace"

    def _slugify(self, value: str) -> str:
        base = "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())
        return base[:100] or f"meeting-{secrets.token_hex(4)}"

    def _load_busy_windows(self, db: Session, workspace_id: uuid.UUID, assigned_user_id: uuid.UUID | None, start: datetime, end: datetime, *, exclude_booking_id: uuid.UUID | None = None) -> list[tuple[datetime, datetime]]:
        query = select(Booking).where(
            Booking.workspace_id == workspace_id,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            Booking.start_time_utc < end,
            Booking.end_time_utc > start,
        )
        if assigned_user_id:
            query = query.where(Booking.assigned_user_id == assigned_user_id)
        if exclude_booking_id:
            query = query.where(Booking.id != exclude_booking_id)
        bookings = db.scalars(query.with_for_update()).all()
        return [(self._ensure_utc(booking.start_time_utc), self._ensure_utc(booking.end_time_utc)) for booking in bookings]

    def _load_blackout_windows(self, db: Session, workspace_id: uuid.UUID, meeting_type_id: uuid.UUID | None, assigned_user_id: uuid.UUID | None, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        query = select(BlackoutDate).where(
            BlackoutDate.workspace_id == workspace_id,
            BlackoutDate.start_time_utc < end,
            BlackoutDate.end_time_utc > start,
            or_(BlackoutDate.meeting_type_id.is_(None), BlackoutDate.meeting_type_id == meeting_type_id),
            or_(BlackoutDate.user_id.is_(None), BlackoutDate.user_id == assigned_user_id),
        )
        items = db.scalars(query).all()
        return [(self._ensure_utc(item.start_time_utc), self._ensure_utc(item.end_time_utc)) for item in items]

    def _load_daily_booking_counts(self, db: Session, workspace_id: uuid.UUID, assigned_user_id: uuid.UUID | None, start: datetime, end: datetime) -> dict[str, int]:
        query = select(Booking).where(
            Booking.workspace_id == workspace_id,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            Booking.start_time_utc >= start,
            Booking.start_time_utc <= end,
        )
        if assigned_user_id:
            query = query.where(Booking.assigned_user_id == assigned_user_id)
        bookings = db.scalars(query).all()
        counter = Counter(booking.start_time_utc.date().isoformat() for booking in bookings)
        return dict(counter)

    def _pick_calendar_connection(self, db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID | None, preferred_provider: str | None) -> CalendarConnection | None:
        query = select(CalendarConnection).where(CalendarConnection.workspace_id == workspace_id, CalendarConnection.status == "connected")
        if user_id:
            query = query.where(or_(CalendarConnection.user_id == user_id, CalendarConnection.user_id.is_(None)))
        if preferred_provider:
            query = query.where(CalendarConnection.provider == preferred_provider)
        connection = db.scalar(query.order_by(CalendarConnection.user_id.desc().nullslast(), CalendarConnection.created_at.asc()))
        if connection:
            return connection
        if preferred_provider:
            return db.scalar(select(CalendarConnection).where(CalendarConnection.workspace_id == workspace_id, CalendarConnection.provider == preferred_provider))
        return None

    def _connection_runtime_metadata(self, connection: CalendarConnection) -> dict:
        metadata = dict(connection.metadata_json or {})
        decrypted = self.crypto_service.decrypt(connection.access_token_encrypted)
        if decrypted:
            metadata["access_token"] = decrypted
        return metadata

    def _select_assignee(self, db: Session, workspace_id: uuid.UUID, meeting_type: MeetingType, desired_start: datetime | None) -> uuid.UUID | None:
        if meeting_type.assignment_mode == "specific" and meeting_type.assigned_user_id:
            return meeting_type.assigned_user_id
        members = db.scalars(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.role.in_(["admin", "team_member"]))
        ).all()
        candidate_user_ids = [member.user_id for member in members]
        if not candidate_user_ids:
            workspace = db.get(Workspace, workspace_id)
            return workspace.owner_user_id if workspace else None
        counts = {
            user_id: db.scalar(
                select(func.count(Booking.id)).where(
                    Booking.workspace_id == workspace_id,
                    Booking.assigned_user_id == user_id,
                    Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                    Booking.start_time_utc >= datetime.now(UTC),
                )
            ) or 0
            for user_id in candidate_user_ids
        }
        return sorted(counts.items(), key=lambda item: (item[1], str(item[0])))[0][0]

    def _assert_slot_available(self, db: Session, workspace_id: uuid.UUID, meeting_type: MeetingType, assigned_user_id: uuid.UUID | None, start: datetime, end: datetime, timezone: str, availability: AvailabilityResponse, *, exclude_booking_id: uuid.UUID | None = None) -> None:
        visitor_tz = ZoneInfo(timezone)
        slots = self.get_booking_slots(
            db,
            None,
            BookingSlotsRequest(
                workspace_id=workspace_id,
                meeting_type_id=meeting_type.id,
                start_date=start,
                end_date=end + timedelta(minutes=1),
                timezone=visitor_tz.key,
                reschedule_booking_id=exclude_booking_id,
            ),
        )
        if not any(slot.start_time_utc == start and slot.end_time_utc == end for slot in slots.slots):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That slot is no longer available.")
        conflicts = self._load_busy_windows(db, workspace_id, assigned_user_id, start, end, exclude_booking_id=exclude_booking_id)
        if any(start < window_end and end > window_start for window_start, window_end in conflicts):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That slot was booked by someone else.")

    def _sync_external_calendar(self, db: Session, booking: Booking, meeting_type: MeetingType, *, action: str, reason: str | None = None) -> None:
        connection = self._pick_calendar_connection(db, booking.workspace_id, booking.assigned_user_id, meeting_type.provider_preference)
        if not connection or connection.provider not in self.providers:
            booking.meeting_link = self._resolve_meeting_link(meeting_type, booking)
            return
        provider = self.providers[connection.provider]
        connection_metadata = self._connection_runtime_metadata(connection)
        booking_payload = self._provider_booking_payload(booking, meeting_type)
        if action == "create":
            result = provider.create_booking(connection_metadata=connection_metadata, booking_payload=booking_payload)
            booking.external_event_id = result.external_event_id
            booking.meeting_link = result.meeting_link or self._resolve_meeting_link(meeting_type, booking)
        elif action == "reschedule" and booking.external_event_id:
            result = provider.reschedule_booking(connection_metadata=connection_metadata, external_event_id=booking.external_event_id, booking_payload=booking_payload)
            booking.external_event_id = result.external_event_id or booking.external_event_id
            booking.meeting_link = result.meeting_link or booking.meeting_link or self._resolve_meeting_link(meeting_type, booking)
        elif action == "cancel" and booking.external_event_id:
            provider.cancel_booking(connection_metadata=connection_metadata, external_event_id=booking.external_event_id, reason=reason)
        else:
            booking.meeting_link = self._resolve_meeting_link(meeting_type, booking)

    def _provider_booking_payload(self, booking: Booking, meeting_type: MeetingType) -> dict:
        payload = {
            "start": booking.start_time_utc.isoformat().replace("+00:00", "Z"),
            "attendee": {
                "name": booking.visitor_name,
                "email": booking.visitor_email,
                "timeZone": booking.timezone,
                "phoneNumber": booking.visitor_phone,
            },
            "metadata": {
                "workspaceId": str(booking.workspace_id),
                "bookingId": str(booking.id),
                "leadId": str(booking.lead_id) if booking.lead_id else None,
            },
            "lengthInMinutes": meeting_type.duration_minutes,
            "meetingUrl": self._resolve_meeting_link(meeting_type, booking),
        }
        metadata = meeting_type.metadata_json or {}
        if metadata.get("calcom_event_type_id"):
            payload["eventTypeId"] = metadata["calcom_event_type_id"]
        if metadata.get("calcom_event_type_slug"):
            payload["eventTypeSlug"] = metadata["calcom_event_type_slug"]
        if metadata.get("calcom_username"):
            payload["username"] = metadata["calcom_username"]
        if metadata.get("calcom_team_slug"):
            payload["teamSlug"] = metadata["calcom_team_slug"]
        if metadata.get("calcom_organization_slug"):
            payload["organizationSlug"] = metadata["calcom_organization_slug"]
        return payload

    def _resolve_meeting_link(self, meeting_type: MeetingType, booking: Booking) -> str | None:
        if meeting_type.location_type == "external_url":
            return meeting_type.external_location_url
        if meeting_type.location_type == "manual":
            return meeting_type.manual_location_text
        if meeting_type.location_type == "phone":
            return booking.visitor_phone or "Phone call"
        return meeting_type.external_location_url or meeting_type.manual_location_text

    def _log_event(self, db: Session, booking: Booking, event_type: str, *, actor_type: str, actor_id: str | None, message: str | None = None) -> None:
        db.add(
            BookingEventLog(
                booking_id=booking.id,
                workspace_id=booking.workspace_id,
                event_type=event_type,
                actor_type=actor_type,
                actor_id=actor_id,
                message=message,
                details_json={"status": booking.status},
            )
        )

    def _queue_booking_notifications(self, db: Session, booking: Booking, background_tasks: BackgroundTasks | None, trigger_name: str) -> None:
        if background_tasks is None:
            return
        workspace = db.get(Workspace, booking.workspace_id)
        if workspace is None:
            return
        summary = f"{booking.visitor_name} booked {booking.start_time_utc.isoformat()}"
        detail = f"Meeting link: {booking.meeting_link or 'TBD'} | Timezone: {booking.timezone} | Status: {booking.status}"
        self.notification_service.queue_custom_trigger(
            background_tasks,
            workspace=workspace,
            chatbot_setting=workspace.chatbot_setting,
            trigger_name=trigger_name,
            summary=summary,
            details=detail,
            payload={
                "booking_id": str(booking.id),
                "meeting_link": booking.meeting_link,
                "start_time_utc": booking.start_time_utc.isoformat(),
                "end_time_utc": booking.end_time_utc.isoformat(),
                "visitor_name": booking.visitor_name,
                "visitor_email": booking.visitor_email,
                "timezone": booking.timezone,
            },
        )

    def _resolve_manageable_booking(self, db: Session, actor: User | None, workspace_id: uuid.UUID, booking_id: uuid.UUID | None, token: str | None) -> tuple[Booking, str | None]:
        if actor is not None:
            get_workspace_member(workspace_id, actor, db)
            if not booking_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="booking_id is required.")
            booking = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.workspace_id == workspace_id))
            if not booking:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
            return booking, None
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A valid booking token is required.")
        token_hash = self._hash_management_token(token)
        booking = db.scalar(select(Booking).where(Booking.workspace_id == workspace_id, Booking.management_token_hash == token_hash))
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
        return booking, token

    def _hash_management_token(self, token: str) -> str:
        secret = self.settings.jwt_secret_key.encode("utf-8")
        return hashlib.sha256(secret + token.encode("utf-8")).hexdigest()

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
