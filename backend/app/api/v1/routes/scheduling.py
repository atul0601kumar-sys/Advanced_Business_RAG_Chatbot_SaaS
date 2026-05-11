import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limiter import enforce_rate_limit
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_optional_current_user
from app.models import User
from app.schemas.scheduling import (
    AvailabilityResponse,
    AvailabilitySetRequest,
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
from app.services.booking_service import BookingService

router = APIRouter(tags=["scheduling"])
settings = get_settings()


@router.get("/calendar/providers", response_model=list[CalendarProviderDescriptor])
def get_calendar_providers() -> list[CalendarProviderDescriptor]:
    return BookingService().list_providers()


@router.post("/calendar/connect", response_model=CalendarConnectionSummary)
def connect_calendar(
    payload: CalendarConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BookingService().connect_calendar(db, current_user, payload)


@router.delete("/calendar/disconnect", response_model=dict[str, str])
def disconnect_calendar(
    payload: CalendarDisconnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return BookingService().disconnect_calendar(db, current_user, payload)


@router.get("/calendar/status", response_model=CalendarStatusResponse)
def calendar_status(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarStatusResponse:
    return BookingService().get_calendar_status(db, current_user, workspace_id)


@router.post("/meeting-types/create", response_model=MeetingTypeSummary)
def create_meeting_type(
    payload: MeetingTypeCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingTypeSummary:
    return BookingService().create_meeting_type(db, current_user, payload)


@router.get("/meeting-types/list", response_model=MeetingTypeListResponse)
def list_meeting_types(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingTypeListResponse:
    return BookingService().list_meeting_types(db, current_user, workspace_id)


@router.put("/meeting-types/{meeting_type_id}", response_model=MeetingTypeSummary)
def update_meeting_type(
    meeting_type_id: uuid.UUID,
    payload: MeetingTypeCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingTypeSummary:
    return BookingService().update_meeting_type(db, current_user, meeting_type_id, payload)


@router.delete("/meeting-types/{meeting_type_id}", response_model=dict[str, str])
def delete_meeting_type(
    meeting_type_id: uuid.UUID,
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return BookingService().delete_meeting_type(db, current_user, workspace_id, meeting_type_id)


@router.post("/availability/set", response_model=AvailabilityResponse)
def set_availability(
    payload: AvailabilitySetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AvailabilityResponse:
    from app.services.availability_service import AvailabilityService

    return AvailabilityService().set_availability(db, current_user, payload)


@router.get("/availability/get", response_model=AvailabilityResponse)
def get_availability(
    workspace_id: uuid.UUID,
    meeting_type_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AvailabilityResponse:
    from app.services.availability_service import AvailabilityService

    return AvailabilityService().get_availability(db, current_user, workspace_id=workspace_id, meeting_type_id=meeting_type_id, user_id=user_id)


@router.post("/availability/blackout", response_model=BlackoutDateSummary)
def create_blackout(
    payload: BlackoutDateCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BlackoutDateSummary:
    return BookingService().create_blackout(db, current_user, payload)


@router.delete("/availability/blackout/{blackout_id}", response_model=dict[str, str])
def delete_blackout(
    blackout_id: uuid.UUID,
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return BookingService().delete_blackout(db, current_user, workspace_id, blackout_id)


@router.get("/availability/blackout/list", response_model=list[BlackoutDateSummary])
def list_blackouts(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BlackoutDateSummary]:
    return BookingService().list_blackouts(db, current_user, workspace_id)


@router.get("/booking/slots", response_model=BookingSlotsResponse)
def get_booking_slots(
    workspace_id: uuid.UUID,
    meeting_type_id: uuid.UUID,
    timezone: str,
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    lead_id: uuid.UUID | None = None,
    chat_session_id: uuid.UUID | None = None,
    reschedule_booking_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> BookingSlotsResponse:
    enforce_rate_limit(
        request,
        scope="booking-slots",
        limit=settings.api_rate_limit_count,
        window_seconds=settings.api_rate_limit_window_seconds,
    )
    actor = get_optional_current_user(request, db)
    return BookingService().get_booking_slots(
        db,
        actor,
        BookingSlotsRequest(
            workspace_id=workspace_id,
            meeting_type_id=meeting_type_id,
            timezone=timezone,
            start_date=start_date,
            end_date=end_date,
            lead_id=lead_id,
            chat_session_id=chat_session_id,
            reschedule_booking_id=reschedule_booking_id,
        ),
    )


@router.post("/booking/create", response_model=BookingSummary)
def create_booking(
    payload: BookingCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> BookingSummary:
    enforce_rate_limit(
        request,
        scope="booking-create",
        limit=settings.api_rate_limit_count,
        window_seconds=settings.api_rate_limit_window_seconds,
    )
    actor = get_optional_current_user(request, db)
    return BookingService().create_booking(db, actor, payload, background_tasks)


@router.post("/booking/reschedule", response_model=BookingSummary)
def reschedule_booking(
    payload: BookingRescheduleRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> BookingSummary:
    enforce_rate_limit(
        request,
        scope="booking-reschedule",
        limit=settings.api_rate_limit_count,
        window_seconds=settings.api_rate_limit_window_seconds,
    )
    actor = get_optional_current_user(request, db)
    return BookingService().reschedule_booking(db, actor, payload, background_tasks)


@router.post("/booking/cancel", response_model=dict[str, str])
def cancel_booking(
    payload: BookingCancelRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    enforce_rate_limit(
        request,
        scope="booking-cancel",
        limit=settings.api_rate_limit_count,
        window_seconds=settings.api_rate_limit_window_seconds,
    )
    actor = get_optional_current_user(request, db)
    return BookingService().cancel_booking(db, actor, payload, background_tasks)


@router.get("/booking/list", response_model=BookingListResponse)
def list_bookings(
    workspace_id: uuid.UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    assigned_user_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookingListResponse:
    return BookingService().list_bookings(db, current_user, workspace_id=workspace_id, status_filter=status_filter, date_from=date_from, date_to=date_to, assigned_user_id=assigned_user_id)


@router.get("/booking/{booking_id}", response_model=BookingSummary)
def get_booking(
    booking_id: uuid.UUID,
    workspace_id: uuid.UUID,
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> BookingSummary:
    actor = get_optional_current_user(request, db)
    return BookingService().get_booking(db, actor, workspace_id, booking_id=booking_id, token=token)


@router.get("/booking/manage/{token}", response_model=BookingSummary)
def get_booking_by_token(token: str, db: Session = Depends(get_db)) -> BookingSummary:
    return BookingService().get_booking_by_token(db, token)


@router.get("/booking/public/{workspace_slug}", response_model=PublicBookingWorkspaceResponse)
def get_public_booking_workspace(workspace_slug: str, db: Session = Depends(get_db)) -> PublicBookingWorkspaceResponse:
    return BookingService().get_public_booking_workspace(db, workspace_slug)
