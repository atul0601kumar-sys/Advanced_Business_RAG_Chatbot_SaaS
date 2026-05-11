import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_workspace_member
from app.models import User
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    ChatAnalyticsResponse,
    FeedbackAnalyticsResponse,
    LeadAnalyticsResponse,
    PerformanceAnalyticsResponse,
    QueryAnalyticsResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _ensure_workspace_access(db: Session, current_user: User, workspace_id: uuid.UUID) -> None:
    get_workspace_member(workspace_id, current_user, db)


def _maybe_export(service: AnalyticsService, payload, export_format: str | None):
    if export_format == "csv":
        return Response(
            content=service.export_csv(payload.model_dump(mode="json")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=analytics-report.csv"},
        )
    return payload


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    workspace_id: uuid.UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    source: str | None = None,
    format: str | None = Query(default=None, alias="export"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_workspace_access(db, current_user, workspace_id)
    service = AnalyticsService()
    payload = service.get_overview(
        db,
        workspace_id=workspace_id,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        document_id=document_id,
        source=source,
    )
    return _maybe_export(service, payload, format)


@router.get("/chats", response_model=ChatAnalyticsResponse)
def get_chat_analytics(
    workspace_id: uuid.UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    source: str | None = None,
    format: str | None = Query(default=None, alias="export"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_workspace_access(db, current_user, workspace_id)
    service = AnalyticsService()
    payload = service.get_chat_analytics(
        db,
        workspace_id=workspace_id,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        document_id=document_id,
        source=source,
    )
    return _maybe_export(service, payload, format)


@router.get("/leads", response_model=LeadAnalyticsResponse)
def get_lead_analytics(
    workspace_id: uuid.UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    source: str | None = None,
    format: str | None = Query(default=None, alias="export"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_workspace_access(db, current_user, workspace_id)
    service = AnalyticsService()
    payload = service.get_lead_analytics(
        db,
        workspace_id=workspace_id,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        document_id=document_id,
        source=source,
    )
    return _maybe_export(service, payload, format)


@router.get("/performance", response_model=PerformanceAnalyticsResponse)
def get_performance_analytics(
    workspace_id: uuid.UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    source: str | None = None,
    format: str | None = Query(default=None, alias="export"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_workspace_access(db, current_user, workspace_id)
    service = AnalyticsService()
    payload = service.get_performance_analytics(
        db,
        workspace_id=workspace_id,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        document_id=document_id,
        source=source,
    )
    return _maybe_export(service, payload, format)


@router.get("/queries", response_model=QueryAnalyticsResponse)
def get_query_analytics(
    workspace_id: uuid.UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    source: str | None = None,
    format: str | None = Query(default=None, alias="export"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_workspace_access(db, current_user, workspace_id)
    service = AnalyticsService()
    payload = service.get_query_analytics(
        db,
        workspace_id=workspace_id,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        document_id=document_id,
        source=source,
    )
    return _maybe_export(service, payload, format)


@router.get("/feedback", response_model=FeedbackAnalyticsResponse)
def get_feedback_analytics(
    workspace_id: uuid.UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    source: str | None = None,
    format: str | None = Query(default=None, alias="export"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_workspace_access(db, current_user, workspace_id)
    service = AnalyticsService()
    payload = service.get_feedback_analytics(
        db,
        workspace_id=workspace_id,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        document_id=document_id,
        source=source,
    )
    return _maybe_export(service, payload, format)
