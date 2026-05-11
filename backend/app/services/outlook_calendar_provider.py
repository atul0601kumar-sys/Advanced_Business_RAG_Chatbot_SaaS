from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.calendar_provider_base import CalendarProviderBase, ProviderBookingResult, ProviderBusySlot


class OutlookCalendarProvider(CalendarProviderBase):
    provider_name = "outlook"

    def get_busy_slots(
        self,
        *,
        connection_metadata: dict[str, Any],
        start_time_utc: datetime,
        end_time_utc: datetime,
        timezone: str,
        meeting_type_metadata: dict[str, Any] | None = None,
    ) -> list[ProviderBusySlot]:
        return []

    def create_booking(self, *, connection_metadata: dict[str, Any], booking_payload: dict[str, Any]) -> ProviderBookingResult:
        return ProviderBookingResult(external_event_id=None, meeting_link=booking_payload.get("meeting_link"))

    def reschedule_booking(
        self,
        *,
        connection_metadata: dict[str, Any],
        external_event_id: str,
        booking_payload: dict[str, Any],
    ) -> ProviderBookingResult:
        return ProviderBookingResult(external_event_id=external_event_id, meeting_link=booking_payload.get("meeting_link"))

    def cancel_booking(
        self,
        *,
        connection_metadata: dict[str, Any],
        external_event_id: str,
        reason: str | None = None,
    ) -> None:
        return None
