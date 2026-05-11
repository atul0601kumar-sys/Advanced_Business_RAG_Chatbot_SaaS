import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import User
from app.schemas.notification import (
    NotificationLogsResponse,
    NotificationQueueResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
    NotificationTestEmailRequest,
    NotificationWebhookRequest,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/settings", response_model=NotificationSettingsResponse)
def get_notification_settings(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationSettingsResponse:
    return NotificationService().get_settings(db, current_user, workspace_id)


@router.put("/settings", response_model=NotificationSettingsResponse)
def update_notification_settings(
    payload: NotificationSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationSettingsResponse:
    return NotificationService().update_settings(db, current_user, payload)


@router.post("/test-email", response_model=NotificationQueueResponse)
def queue_test_email(
    payload: NotificationTestEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationQueueResponse:
    queued = NotificationService().queue_test_email(db, current_user, payload)
    return NotificationQueueResponse(message="Test email queued successfully.", queued_jobs=queued)


@router.get("/logs", response_model=NotificationLogsResponse)
def list_notification_logs(
    workspace_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationLogsResponse:
    return NotificationService().list_logs(db, current_user, workspace_id=workspace_id, limit=limit)


@router.post("/webhook", response_model=NotificationQueueResponse)
def queue_webhook_dispatch(
    payload: NotificationWebhookRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationQueueResponse:
    queued = NotificationService().queue_manual_webhook(db, current_user, payload)
    return NotificationQueueResponse(message="Webhook jobs queued successfully.", queued_jobs=queued)
