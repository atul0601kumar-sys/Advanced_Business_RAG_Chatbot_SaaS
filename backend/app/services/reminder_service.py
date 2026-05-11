from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Booking
from app.services.notification_service import NotificationService


class ReminderService:
    def __init__(self, session_factory=SessionLocal, notification_service: NotificationService | None = None) -> None:
        self.session_factory = session_factory
        self.notification_service = notification_service or NotificationService()

    def process_due_reminders(self, *, now: datetime | None = None, limit: int = 20) -> int:
        current_time = now or datetime.now(UTC)
        processed = 0
        with self.session_factory() as db:
            candidates = db.scalars(
                select(Booking)
                .where(Booking.status == "confirmed", Booking.start_time_utc >= current_time)
                .order_by(Booking.start_time_utc.asc())
                .limit(limit * 5)
            ).all()
            for booking in candidates:
                if self._queue_due_reminders(db, booking, current_time):
                    processed += 1
                    if processed >= limit:
                        break
            db.commit()
        return processed

    def _queue_due_reminders(self, db: Session, booking: Booking, now: datetime) -> bool:
        reminder_state = booking.reminder_state_json or {}
        queued = False
        for key, delta in {"24h": timedelta(hours=24), "1h": timedelta(hours=1)}.items():
            if reminder_state.get(key):
                continue
            if booking.start_time_utc - delta <= now:
                reminder_state[key] = now.isoformat()
                booking.reminder_state_json = reminder_state
                queued = True
        return queued
