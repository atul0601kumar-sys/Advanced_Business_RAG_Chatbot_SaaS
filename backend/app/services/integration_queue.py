from __future__ import annotations

import logging
import threading
import urllib.error
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models import IntegrationConnection, IntegrationDelivery
from app.services.integration_manager import IntegrationManager

logger = logging.getLogger(__name__)


class IntegrationQueue:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        manager: IntegrationManager | None = None,
        session_factory=SessionLocal,
    ) -> None:
        self.settings = settings or get_settings()
        self.manager = manager or IntegrationManager(settings=self.settings)
        self.session_factory = session_factory
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.settings.integration_queue_enabled:
            logger.info("Integration queue worker is disabled by configuration.")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="integration-queue-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

    def process_pending_jobs(self, *, limit: int | None = None) -> int:
        processed = 0
        with self.session_factory() as db:
            now = datetime.now(UTC)
            jobs = db.scalars(
                select(IntegrationDelivery)
                .where(
                    IntegrationDelivery.status.in_(["pending", "retrying"]),
                    IntegrationDelivery.next_attempt_at <= now,
                )
                .order_by(IntegrationDelivery.next_attempt_at.asc(), IntegrationDelivery.created_at.asc())
                .limit(limit or self.settings.integration_queue_batch_size)
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
                logger.exception("Integration queue worker iteration failed")
            self._stop_event.wait(self.settings.integration_queue_poll_interval_seconds)

    def _process_job(self, db, job: IntegrationDelivery) -> None:  # noqa: ANN001
        job.status = "processing"
        job.retry_count += 1
        job.locked_at = datetime.now(UTC)
        connection = db.get(IntegrationConnection, job.integration_id)
        if connection is None or connection.status != "active":
            job.status = "failed"
            job.error_message = "Integration connection is not active."
            job.completed_at = datetime.now(UTC)
            return
        provider = self.manager.registry.get_provider(connection.integration_type)
        try:
            result = provider.send_event(
                self.manager.build_provider_context(connection),
                event_type=job.event_type,
                payload=job.payload_json,
            )
            job.status = "success"
            job.error_message = None
            job.response_code = result.status_code
            job.response_body = result.response_body[:5000]
            job.completed_at = datetime.now(UTC)
            job.locked_at = None
            connection.last_error = None
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, ValueError) as exc:
            self._mark_failed(job, connection, str(exc))
        except Exception as exc:  # noqa: BLE001
            self._mark_failed(job, connection, str(exc))
            logger.exception("Unhandled integration delivery error", extra={"delivery_id": str(job.id)})

    def _mark_failed(self, job: IntegrationDelivery, connection: IntegrationConnection, message: str) -> None:
        job.error_message = message[:5000]
        connection.last_error = job.error_message
        job.locked_at = None
        exhausted = job.retry_count >= job.max_retries
        if exhausted:
            job.status = "failed"
            job.completed_at = datetime.now(UTC)
            connection.status = "error"
        else:
            job.status = "retrying"
            job.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=self.settings.integration_retry_backoff_seconds * job.retry_count
            )


shared_integration_queue = IntegrationQueue()
