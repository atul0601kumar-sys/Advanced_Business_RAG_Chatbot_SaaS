from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas.scheduling import AvailabilityResponse, AvailabilitySettingsInput, WeeklyAvailabilityRuleInput
from app.services.slot_generator import SlotGenerator


def test_slot_generator_respects_busy_windows_and_timezone_display():
    tomorrow = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    availability = AvailabilityResponse(
        workspace_id="00000000-0000-0000-0000-000000000001",
        meeting_type_id=None,
        user_id=None,
        rules=[
            WeeklyAvailabilityRuleInput(
                weekday=tomorrow.weekday(),
                start_time="09:00",
                end_time="12:00",
                is_enabled=True,
            )
        ],
        settings=AvailabilitySettingsInput(
            timezone="UTC",
            buffer_before_minutes=0,
            buffer_after_minutes=0,
            duration_options=[30],
            max_bookings_per_day=10,
            minimum_notice_minutes=0,
            future_booking_window_days=30,
        ),
    )
    busy_start = tomorrow.replace(hour=9, minute=30)
    busy_end = tomorrow.replace(hour=10, minute=0)

    slots = SlotGenerator().generate_slots(
        availability=availability,
        visitor_timezone="America/New_York",
        duration_minutes=30,
        range_start_utc=tomorrow,
        range_end_utc=tomorrow.replace(hour=23, minute=59),
        busy_windows=[(busy_start, busy_end)],
        blackout_windows=[],
        existing_booking_windows=[],
        max_bookings_per_day={},
    )

    assert slots
    assert all(slot.start_time_utc != busy_start for slot in slots)
    assert "AM" in slots[0].display_time or "PM" in slots[0].display_time
