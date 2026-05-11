from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.schemas.scheduling import AvailabilityResponse, AvailableSlot


class SlotGenerator:
    def generate_slots(
        self,
        *,
        availability: AvailabilityResponse,
        visitor_timezone: str,
        duration_minutes: int,
        range_start_utc: datetime,
        range_end_utc: datetime,
        busy_windows: list[tuple[datetime, datetime]],
        blackout_windows: list[tuple[datetime, datetime]],
        existing_booking_windows: list[tuple[datetime, datetime]],
        max_bookings_per_day: dict[str, int],
    ) -> list[AvailableSlot]:
        admin_tz = ZoneInfo(availability.settings.timezone)
        visitor_tz = ZoneInfo(visitor_timezone)
        range_start_local = range_start_utc.astimezone(admin_tz).date()
        range_end_local = range_end_utc.astimezone(admin_tz).date()
        active_rules = {rule.weekday: rule for rule in availability.rules if rule.is_enabled}
        slots: list[AvailableSlot] = []
        cursor = range_start_local
        while cursor <= range_end_local:
            rule = active_rules.get(cursor.weekday())
            if rule is None:
                cursor += timedelta(days=1)
                continue
            start_hour, start_minute = map(int, rule.start_time.split(":"))
            end_hour, end_minute = map(int, rule.end_time.split(":"))
            day_start_local = datetime.combine(cursor, time(start_hour, start_minute), admin_tz)
            day_end_local = datetime.combine(cursor, time(end_hour, end_minute), admin_tz)
            step_minutes = duration_minutes
            slot_start_local = day_start_local
            created_today = 0
            daily_cap = availability.settings.max_bookings_per_day
            while slot_start_local + timedelta(minutes=duration_minutes) <= day_end_local:
                slot_end_local = slot_start_local + timedelta(minutes=duration_minutes)
                slot_start_utc = slot_start_local.astimezone(UTC)
                slot_end_utc = slot_end_local.astimezone(UTC)
                effective_start = slot_start_utc - timedelta(minutes=availability.settings.buffer_before_minutes)
                effective_end = slot_end_utc + timedelta(minutes=availability.settings.buffer_after_minutes)
                if slot_start_utc < range_start_utc or slot_end_utc > range_end_utc:
                    slot_start_local += timedelta(minutes=step_minutes)
                    continue
                if slot_start_utc < datetime.now(UTC) + timedelta(minutes=availability.settings.minimum_notice_minutes):
                    slot_start_local += timedelta(minutes=step_minutes)
                    continue
                if created_today >= daily_cap:
                    break
                overlaps = busy_windows + blackout_windows + existing_booking_windows
                if any(effective_start < window_end and effective_end > window_start for window_start, window_end in overlaps):
                    slot_start_local += timedelta(minutes=step_minutes)
                    continue
                day_key = cursor.isoformat()
                if max_bookings_per_day.get(day_key, 0) >= daily_cap:
                    break
                local_label = slot_start_utc.astimezone(visitor_tz).strftime("%a, %b %d at %I:%M %p")
                slots.append(
                    AvailableSlot(
                        start_time_utc=slot_start_utc,
                        end_time_utc=slot_end_utc,
                        display_time=local_label,
                        timezone=visitor_timezone,
                        provider="internal",
                        assigned_user_id=None,
                    )
                )
                created_today += 1
                slot_start_local += timedelta(minutes=step_minutes)
            cursor += timedelta(days=1)
        return slots
