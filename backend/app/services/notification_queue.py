from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models import NotificationJob, NotificationLog
from app.services.email_service import EmailDeliveryRequest, EmailService
from app.services.template_engine import get_template
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)


class NotificationQueue:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        email_service: EmailService | None = None,
        webhook_service: WebhookService | None = None,
        session_factory=SessionLocal,
        sleep_fn=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.email_service = email_service or EmailService(settings=self.settings)
        self.webhook_service = webhook_service or WebhookService(settings=self.settings)
        self.session_factory = session_factory
        self.sleep_fn = sleep_fn or time.sleep
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.settings.notification_queue_enabled:
            logger.info("Notification queue worker is disabled by configuration.")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="notification-queue-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def enqueue_job(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        event_name: str,
        channel: str,
        payload: dict[str, Any],
        dedupe_key: str | None,
        max_retries: int,
        target: str | None,
        rate_limit_count: int,
        rate_limit_window_seconds: int,
    ) -> NotificationJob | None:
        now = datetime.now(UTC)
        if dedupe_key and self._has_duplicate(db, dedupe_key):
            logger.info("Notification job skipped as duplicate", extra={"dedupe_key": dedupe_key, "event": event_name})
            return None
        if self._is_rate_limited(
            db,
            workspace_id=workspace_id,
            event_name=event_name,
            rate_limit_count=rate_limit_count,
            rate_limit_window_seconds=rate_limit_window_seconds,
        ):
            logger.warning("Notification job rate limited", extra={"workspace_id": str(workspace_id), "event": event_name})
            return None

        job = NotificationJob(
            workspace_id=workspace_id,
            event_name=event_name,
            channel=channel,
            status="pending",
            payload_json=payload,
            dedupe_key=dedupe_key,
            retry_count=0,
            max_retries=max_retries,
            target=target,
            next_attempt_at=now,
        )
        db.add(job)
        db.flush()
        db.add(
            NotificationLog(
                notification_job_id=job.id,
                workspace_id=workspace_id,
                notification_id=str(job.id),
                type=event_name,
                channel=channel,
                status="pending",
                retry_count=0,
                target=target,
            )
        )
        return job

    def process_pending_jobs(self, *, limit: int | None = None) -> int:
        processed = 0
        with self.session_factory() as db:
            now = datetime.now(UTC)
            jobs = db.scalars(
                select(NotificationJob)
                .where(
                    NotificationJob.status.in_(["pending", "retrying"]),
                    NotificationJob.next_attempt_at <= now,
                )
                .order_by(NotificationJob.next_attempt_at.asc(), NotificationJob.created_at.asc())
                .limit(limit or self.settings.notification_queue_batch_size)
            ).all()
            for job in jobs:
                self._process_job(db, job)
                processed += 1
            db.commit()
        return processed

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.process_pending_jobs()
            except Exception:  # noqa: BLE001
                logger.exception("Notification queue worker iteration failed")
            self._stop_event.wait(self.settings.notification_queue_poll_interval_seconds)

    def _process_job(self, db: Session, job: NotificationJob) -> None:
        job.status = "processing"
        job.locked_at = datetime.now(UTC)
        job.retry_count += 1
        db.flush()
        try:
            if job.channel == "email":
                self._deliver_email(job.payload_json)
                self._mark_job_sent(db, job, response_code=202, response_body="email accepted")
            elif job.channel == "webhook":
                result = self.webhook_service.send(job.target or "", job.payload_json)
                self._mark_job_sent(db, job, response_code=result.status_code, response_body=result.response_body)
            elif job.channel == "in_app":
                self._mark_job_sent(db, job, response_code=200, response_body="in-app notification recorded")
            else:
                raise RuntimeError(f"Unsupported notification channel: {job.channel}")
        except Exception as exc:  # noqa: BLE001
            self._mark_job_failed(db, job, str(exc))
            logger.exception("Notification job delivery failed", extra={"job_id": str(job.id), "channel": job.channel})

    def _deliver_email(self, payload: dict[str, Any]) -> None:
        template = get_template(payload["template_id"])
        rendered = template.render(payload["context"], payload.get("template_override"))
        self.email_service.send(
            EmailDeliveryRequest(
                to_addresses=payload["to_addresses"],
                subject=rendered.subject,
                text_body=rendered.text_body,
                html_body=rendered.html_body,
                reply_to=payload.get("reply_to"),
            )
        )

    def _mark_job_sent(
        self,
        db: Session,
        job: NotificationJob,
        *,
        response_code: int,
        response_body: str,
    ) -> None:
        job.status = "sent"
        job.error_message = None
        job.completed_at = datetime.now(UTC)
        job.locked_at = None
        self._upsert_log(
            db,
            job=job,
            status="sent",
            error_message=None,
            response_code=response_code,
            response_body=response_body,
        )

    def _mark_job_failed(self, db: Session, job: NotificationJob, error_message: str) -> None:
        job.error_message = error_message[:5000]
        job.locked_at = None
        exhausted = job.retry_count >= job.max_retries
        if exhausted:
            job.status = "failed"
            job.completed_at = datetime.now(UTC)
        else:
            job.status = "retrying"
            backoff_seconds = (
                self.settings.notification_email_retry_backoff_seconds
                if job.channel == "email"
                else self.settings.notification_webhook_retry_backoff_seconds
            )
            job.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=backoff_seconds * job.retry_count
            )
        self._upsert_log(
            db,
            job=job,
            status="failed" if exhausted else "pending",
            error_message=job.error_message,
            response_code=None,
            response_body=None,
        )

    def _upsert_log(
        self,
        db: Session,
        *,
        job: NotificationJob,
        status: str,
        error_message: str | None,
        response_code: int | None,
        response_body: str | None,
    ) -> None:
        log = db.scalar(select(NotificationLog).where(NotificationLog.notification_job_id == job.id))
        if log is None:
            log = NotificationLog(
                notification_job_id=job.id,
                workspace_id=job.workspace_id,
                notification_id=str(job.id),
                type=job.event_name,
                channel=job.channel,
                status=status,
            )
            db.add(log)
        log.status = status
        log.error_message = error_message
        log.retry_count = job.retry_count
        log.response_code = response_code
        log.response_body = response_body[:5000] if response_body else None
        log.target = job.target

    def _has_duplicate(self, db: Session, dedupe_key: str) -> bool:
        existing = db.scalar(
            select(NotificationJob).where(
                NotificationJob.dedupe_key == dedupe_key,
                NotificationJob.status.in_(["pending", "processing", "retrying", "sent"]),
            )
        )
        return existing is not None

    def _is_rate_limited(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        event_name: str,
        rate_limit_count: int,
        rate_limit_window_seconds: int,
    ) -> bool:
        if rate_limit_count <= 0:
            return False
        window_start = datetime.now(UTC) - timedelta(seconds=rate_limit_window_seconds)
        recent = db.scalars(
            select(NotificationJob).where(
                NotificationJob.workspace_id == workspace_id,
                NotificationJob.event_name == event_name,
                NotificationJob.created_at >= window_start,
            )
        ).all()
        return len(recent) >= rate_limit_count


shared_notification_queue = NotificationQueue()
