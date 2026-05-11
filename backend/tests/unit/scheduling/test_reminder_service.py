from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Booking, MeetingType
from app.services.reminder_service import ReminderService


def test_queue_due_reminders_marks_24h_and_1h_windows(db_session, seeded_workspace):
    meeting_type = MeetingType(
        workspace_id=seeded_workspace.workspace_id,
        title="Consultation",
        slug="consultation",
        duration_minutes=30,
        location_type="manual",
        assignment_mode="specific",
        booking_link_token="token-1",
    )
    db_session.add(meeting_type)
    db_session.flush()

    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    booking_24h = Booking(
        workspace_id=seeded_workspace.workspace_id,
        meeting_type_id=meeting_type.id,
        visitor_name="Avery",
        visitor_email="avery@example.com",
        start_time_utc=now + timedelta(hours=23),
        end_time_utc=now + timedelta(hours=23, minutes=30),
        timezone="UTC",
        status="confirmed",
        provider="internal",
        management_token_hash="hash-24h",
        reminder_state_json={},
    )
    booking_1h = Booking(
        workspace_id=seeded_workspace.workspace_id,
        meeting_type_id=meeting_type.id,
        visitor_name="Jordan",
        visitor_email="jordan@example.com",
        start_time_utc=now + timedelta(minutes=50),
        end_time_utc=now + timedelta(minutes=80),
        timezone="UTC",
        status="confirmed",
        provider="internal",
        management_token_hash="hash-1h",
        reminder_state_json={},
    )
    booking_not_due = Booking(
        workspace_id=seeded_workspace.workspace_id,
        meeting_type_id=meeting_type.id,
        visitor_name="Morgan",
        visitor_email="morgan@example.com",
        start_time_utc=now + timedelta(hours=30),
        end_time_utc=now + timedelta(hours=30, minutes=30),
        timezone="UTC",
        status="confirmed",
        provider="internal",
        management_token_hash="hash-later",
        reminder_state_json={},
    )
    booking_past = Booking(
        workspace_id=seeded_workspace.workspace_id,
        meeting_type_id=meeting_type.id,
        visitor_name="Taylor",
        visitor_email="taylor@example.com",
        start_time_utc=now - timedelta(hours=2),
        end_time_utc=now - timedelta(hours=1, minutes=30),
        timezone="UTC",
        status="confirmed",
        provider="internal",
        management_token_hash="hash-past",
        reminder_state_json={},
    )
    booking_cancelled = Booking(
        workspace_id=seeded_workspace.workspace_id,
        meeting_type_id=meeting_type.id,
        visitor_name="Casey",
        visitor_email="casey@example.com",
        start_time_utc=now + timedelta(minutes=45),
        end_time_utc=now + timedelta(minutes=75),
        timezone="UTC",
        status="cancelled",
        provider="internal",
        management_token_hash="hash-cancelled",
        reminder_state_json={},
    )
    db_session.add_all([booking_24h, booking_1h, booking_not_due, booking_past, booking_cancelled])
    db_session.commit()

    service = ReminderService(session_factory=lambda: db_session, notification_service=object())
    processed = service.process_due_reminders(now=now, limit=10)

    assert processed == 2
    assert booking_24h.reminder_state_json == {"24h": now.isoformat()}
    assert booking_1h.reminder_state_json == {"24h": now.isoformat(), "1h": now.isoformat()}
    assert booking_not_due.reminder_state_json == {}
    assert booking_past.reminder_state_json == {}
    assert booking_cancelled.reminder_state_json == {}


def test_queue_due_reminders_is_idempotent_for_existing_state(db_session, seeded_workspace):
    meeting_type = MeetingType(
        workspace_id=seeded_workspace.workspace_id,
        title="Support",
        slug="support",
        duration_minutes=30,
        location_type="manual",
        assignment_mode="specific",
        booking_link_token="token-2",
    )
    db_session.add(meeting_type)
    db_session.flush()

    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    booking = Booking(
        workspace_id=seeded_workspace.workspace_id,
        meeting_type_id=meeting_type.id,
        visitor_name="Riley",
        visitor_email="riley@example.com",
        start_time_utc=now + timedelta(minutes=30),
        end_time_utc=now + timedelta(hours=1),
        timezone="UTC",
        status="confirmed",
        provider="internal",
        management_token_hash="hash-riley",
        reminder_state_json={"24h": "2025-12-31T12:00:00+00:00", "1h": "2026-01-01T11:10:00+00:00"},
    )
    db_session.add(booking)
    db_session.commit()

    service = ReminderService(session_factory=lambda: db_session, notification_service=object())

    assert service._queue_due_reminders(db_session, booking, now) is False
    assert service.process_due_reminders(now=now, limit=10) == 0
    assert booking.reminder_state_json == {
        "24h": "2025-12-31T12:00:00+00:00",
        "1h": "2026-01-01T11:10:00+00:00",
    }
