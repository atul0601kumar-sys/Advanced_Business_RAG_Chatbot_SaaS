from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.monitoring import configure_error_monitoring
from app.services.index_pipeline import run_indexing_job
from app.services.integration_queue import shared_integration_queue
from app.services.job_queue import shared_export_queue
from app.services.notification_queue import shared_notification_queue
from app.services.redis_queue import shared_task_queue
from app.services.reminder_service import ReminderService

settings = get_settings()
configure_logging(settings)
configure_error_monitoring(settings)
logger = logging.getLogger(__name__)


def run_worker() -> None:
    logger.info("Worker starting", extra={"queue_enabled": settings.task_queue_enabled})
    while True:
        _touch_heartbeat()
        task = shared_task_queue.dequeue()
        if task is not None:
            _process_task(task)
            continue
        _drain_database_backed_queues()
        time.sleep(0.5)


def _process_task(task: dict) -> None:
    task_type = task.get("type")
    payload = task.get("payload", {})
    try:
        if task_type == "document.index":
            run_indexing_job(uuid.UUID(payload["document_id"]))
        elif task_type == "website.index":
            from app.services.website_sources import run_website_indexing_job

            run_website_indexing_job(uuid.UUID(payload["source_id"]))
        elif task_type == "export.process":
            shared_export_queue.process_pending_jobs(limit=1)
        elif task_type == "notification.sweep":
            shared_notification_queue.process_pending_jobs(limit=10)
        elif task_type == "integration.sweep":
            shared_integration_queue.process_pending_jobs(limit=10)
        elif task_type == "reminder.sweep":
            ReminderService().process_due_reminders(limit=20)
        else:
            logger.warning("Unknown task type", extra={"task_type": task_type})
    except Exception:
        logger.exception("Worker task failed", extra={"task_type": task_type, "payload": payload})


def _drain_database_backed_queues() -> None:
    try:
        shared_notification_queue.process_pending_jobs(limit=5)
        shared_integration_queue.process_pending_jobs(limit=5)
        shared_export_queue.process_pending_jobs(limit=5)
        ReminderService().process_due_reminders(limit=20)
    except Exception:
        logger.exception("Worker sweep failed")


def _touch_heartbeat() -> None:
    if not settings.task_queue_enabled:
        return
    client = shared_task_queue._get_client()
    client.set(settings.worker_heartbeat_key, datetime.now(UTC).isoformat(), ex=settings.worker_heartbeat_ttl_seconds)


def is_worker_healthy() -> bool:
    if not settings.task_queue_enabled:
        return True
    value = shared_task_queue._get_client().get(settings.worker_heartbeat_key)
    if not value:
        return False
    heartbeat = datetime.fromisoformat(value)
    return (datetime.now(UTC) - heartbeat).total_seconds() <= settings.worker_heartbeat_ttl_seconds + 5


if __name__ == "__main__":
    run_worker()
