from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.input_validator import sanitize_text, validate_webhook_url

CalendarProviderName = Literal["google", "outlook", "calcom", "external_link"]
BookingStatus = Literal["pending", "confirmed", "cancelled", "rescheduled", "completed", "no_show"]
LocationType = Literal["google_meet", "external_url", "manual", "phone", "in_person"]
AssignmentMode = Literal["specific", "round_robin"]


class CalendarProviderDescriptor(BaseModel):
    provider: CalendarProviderName
    label: str
    auth_type: str
    supports_busy_lookup: bool
    supports_event_creation: bool
    supports_video_link: bool
    supports_oauth: bool


class CalendarConnectRequest(BaseModel):
    workspace_id: uuid.UUID
    provider: CalendarProviderName
    user_id: uuid.UUID | None = None
    access_token: str | None = Field(default=None, max_length=5000)
    refresh_token: str | None = Field(default=None, max_length=5000)
    api_key: str | None = Field(default=None, max_length=5000)
    external_account_id: str | None = Field(default=None, max_length=255)
    external_account_email: str | None = Field(default=None, max_length=255)
    external_booking_url: str | None = Field(default=None, max_length=2000)
    metadata: dict | None = None


class CalendarDisconnectRequest(BaseModel):
    workspace_id: uuid.UUID
    provider: CalendarProviderName
    user_id: uuid.UUID | None = None


class CalendarConnectionSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID | None
    provider: CalendarProviderName
    status: str
    external_account_id: str | None
    external_account_email: str | None
    metadata: dict | None
    created_at: datetime
    updated_at: datetime


class CalendarStatusResponse(BaseModel):
    workspace_id: uuid.UUID
    items: list[CalendarConnectionSummary]


class MeetingTypeCreateRequest(BaseModel):
    workspace_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    duration_minutes: int = Field(ge=15, le=60)
    location_type: LocationType
    assigned_user_id: uuid.UUID | None = None
    assignment_mode: AssignmentMode = "specific"
    provider_preference: CalendarProviderName | None = None
    external_location_url: str | None = Field(default=None, max_length=2000)
    manual_location_text: str | None = Field(default=None, max_length=1000)
    availability_rules: dict | None = None
    metadata: dict | None = None

    @field_validator("title", "description", "manual_location_text", mode="before")
    @classmethod
    def sanitize_text_fields(cls, value: str | None) -> str | None:
        return sanitize_text(value, max_length=4000)


class MeetingTypeUpdateRequest(MeetingTypeCreateRequest):
    pass


class MeetingTypeSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    slug: str
    description: str | None
    duration_minutes: int
    location_type: LocationType
    assigned_user_id: uuid.UUID | None
    assignment_mode: AssignmentMode
    provider_preference: CalendarProviderName | None
    external_location_url: str | None
    manual_location_text: str | None
    booking_link: str
    availability_rules: dict | None
    metadata: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MeetingTypeListResponse(BaseModel):
    items: list[MeetingTypeSummary]


class WeeklyAvailabilityRuleInput(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    is_enabled: bool = True


class AvailabilitySettingsInput(BaseModel):
    timezone: str = Field(min_length=1, max_length=100)
    buffer_before_minutes: int = Field(default=0, ge=0, le=180)
    buffer_after_minutes: int = Field(default=0, ge=0, le=180)
    duration_options: list[int] = Field(default_factory=lambda: [15, 30, 45, 60])
    max_bookings_per_day: int = Field(default=20, ge=1, le=200)
    minimum_notice_minutes: int = Field(default=60, ge=0, le=60 * 24 * 14)
    future_booking_window_days: int = Field(default=30, ge=1, le=365)
    fallback_owner_user_id: uuid.UUID | None = None
    reminder_in_app_enabled: bool = False


class AvailabilitySetRequest(BaseModel):
    workspace_id: uuid.UUID
    meeting_type_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    rules: list[WeeklyAvailabilityRuleInput]
    settings: AvailabilitySettingsInput


class AvailabilityResponse(BaseModel):
    workspace_id: uuid.UUID
    meeting_type_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    rules: list[WeeklyAvailabilityRuleInput]
    settings: AvailabilitySettingsInput


class BlackoutDateCreateRequest(BaseModel):
    workspace_id: uuid.UUID
    meeting_type_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=2000)
    start_time: datetime
    end_time: datetime
    timezone: str = Field(min_length=1, max_length=100)


class BlackoutDateSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    meeting_type_id: uuid.UUID | None
    user_id: uuid.UUID | None
    title: str | None
    reason: str | None
    start_time_utc: datetime
    end_time_utc: datetime
    timezone: str
    created_at: datetime


class AvailableSlot(BaseModel):
    start_time_utc: datetime
    end_time_utc: datetime
    display_time: str
    timezone: str
    provider: CalendarProviderName | Literal["internal"]
    assigned_user_id: uuid.UUID | None


class BookingSlotsRequest(BaseModel):
    workspace_id: uuid.UUID
    meeting_type_id: uuid.UUID
    start_date: datetime | None = None
    end_date: datetime | None = None
    timezone: str = Field(min_length=1, max_length=100)
    lead_id: uuid.UUID | None = None
    chat_session_id: uuid.UUID | None = None
    reschedule_booking_id: uuid.UUID | None = None


class BookingSlotsResponse(BaseModel):
    workspace_id: uuid.UUID
    meeting_type_id: uuid.UUID
    timezone: str
    slots: list[AvailableSlot]


class BookingCreateRequest(BaseModel):
    workspace_id: uuid.UUID
    meeting_type_id: uuid.UUID
    lead_id: uuid.UUID | None = None
    chat_session_id: uuid.UUID | None = None
    visitor_name: str = Field(min_length=1, max_length=255)
    visitor_email: str = Field(min_length=5, max_length=255)
    visitor_phone: str | None = Field(default=None, max_length=50)
    start_time_utc: datetime
    timezone: str = Field(min_length=1, max_length=100)
    preferred_location_type: LocationType | None = None
    preferred_date_note: str | None = Field(default=None, max_length=1000)

    @field_validator("visitor_name", "preferred_date_note", mode="before")
    @classmethod
    def sanitize_booking_fields(cls, value: str | None) -> str | None:
        return sanitize_text(value, max_length=1000)


class BookingRescheduleRequest(BaseModel):
    workspace_id: uuid.UUID
    booking_id: uuid.UUID | None = None
    token: str | None = Field(default=None, max_length=255)
    start_time_utc: datetime
    timezone: str = Field(min_length=1, max_length=100)


class BookingCancelRequest(BaseModel):
    workspace_id: uuid.UUID
    booking_id: uuid.UUID | None = None
    token: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=1000)


class BookingListRequest(BaseModel):
    workspace_id: uuid.UUID
    status: BookingStatus | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    assigned_user_id: uuid.UUID | None = None


class BookingAttendeeSummary(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    timezone: str | None
    is_primary: bool


class BookingSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    lead_id: uuid.UUID | None
    chat_session_id: uuid.UUID | None
    meeting_type_id: uuid.UUID
    meeting_type_title: str
    assigned_user_id: uuid.UUID | None
    assigned_user_name: str | None
    visitor_name: str
    visitor_email: str
    visitor_phone: str | None
    start_time_utc: datetime
    end_time_utc: datetime
    timezone: str
    status: BookingStatus
    provider: str
    external_event_id: str | None
    meeting_link: str | None
    management_url: str
    public_reschedule_url: str
    public_cancel_url: str
    attendees: list[BookingAttendeeSummary]
    metadata: dict | None
    created_at: datetime
    updated_at: datetime


class BookingListResponse(BaseModel):
    items: list[BookingSummary]
    total: int


class PublicBookingWorkspaceResponse(BaseModel):
    workspace_id: uuid.UUID
    workspace_name: str
    workspace_slug: str
    admin_timezone: str
    meeting_types: list[MeetingTypeSummary]


class SchedulingIntentResponse(BaseModel):
    detected: bool
    reason: str | None = None
    should_prompt_for_booking: bool = False
    suggested_meeting_type_id: uuid.UUID | None = None

