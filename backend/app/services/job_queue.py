from __future__ import annotations

import logging
import queue
import threading
import uuid

from sqlalchemy import select

logger = logging.getLogger(__name__)


class ExportJobQueue:
    def __init__(self) -> None:
        from app.core.config import get_settings

        self.settings = get_settings()
        self._queue: queue.Queue[uuid.UUID] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.settings.worker_mode != "inline":
            logger.info("Inline export worker skipped", extra={"worker_mode": self.settings.worker_mode})
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="export-job-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

    def enqueue(self, job_id: uuid.UUID) -> None:
        from app.services.redis_queue import shared_task_queue

        if shared_task_queue.enqueue("export.process", {"job_id": str(job_id)}):
            return
        self._queue.put(job_id)

    def process_pending_jobs(self, *, limit: int = 10) -> int:
        from app.db.session import SessionLocal
        from app.models import ExportJob
        from app.services.export_service import ExportService

        processed = 0
        with SessionLocal() as db:
            jobs = db.scalars(
                select(ExportJob)
                .where(ExportJob.status == "pending")
                .order_by(ExportJob.created_at.asc())
                .limit(limit)
            ).all()
            service = ExportService()
            for job in jobs:
                service.process_job(job.id)
                processed += 1
        return processed

    def _run(self) -> None:
        from app.services.export_service import ExportService

        service = ExportService()
        while not self._stop_event.is_set():
            try:
                job_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                should_retry = service.process_job(job_id)
                if should_retry:
                    self._queue.put(job_id)
            except Exception:
                logger.exception("Unhandled export job worker error", extra={"job_id": str(job_id)})
            finally:
                self._queue.task_done()


shared_export_queue = ExportJobQueue()
