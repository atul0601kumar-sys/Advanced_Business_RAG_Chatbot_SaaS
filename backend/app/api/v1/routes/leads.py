import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_optional_current_user
from app.models import ChatSession, User
from app.schemas.lead import (
    HumanHandoffRequest,
    HumanHandoffResponse,
    LeadCaptureResponse,
    LeadCaptureSettingsResponse,
    LeadCaptureSettingsUpdateRequest,
    LeadCreateRequest,
    LeadDetailResponse,
    LeadExportRequest,
    LeadListResponse,
    LeadNoteRequest,
    LeadSummary,
    LeadStatusUpdateRequest,
    LeadUpdateRequest,
)
from app.services.lead_service import LeadService
from app.services.widget_auth import WidgetAuthService

router = APIRouter(prefix="/leads", tags=["leads"])
handoff_router = APIRouter(prefix="/chat", tags=["chat"])


def _resolve_lead_actor(
    request: Request,
    db: Session,
    *,
    workspace_id: uuid.UUID,
    session_id: uuid.UUID | None = None,
) -> User | None:
    current_user = get_optional_current_user(request, db)
    if current_user is not None:
        return current_user
    principal = WidgetAuthService().authenticate(request)
    if principal.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Widget workspace mismatch.")
    if session_id is not None:
        session = db.scalar(select(ChatSession).where(ChatSession.id == session_id))
        if not session or session.workspace_id != workspace_id or session.channel != "widget":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    return None


@router.post("/capture", response_model=LeadCaptureResponse)
def capture_lead(
    payload: LeadCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> LeadCaptureResponse:
    service = LeadService()
    current_user = _resolve_lead_actor(
        request,
        db,
        workspace_id=payload.workspace_id,
        session_id=payload.chat_session_id,
    )
    lead = service.create_lead(db, current_user, payload, background_tasks)
    return LeadCaptureResponse(
        message=(lead.metadata_json or {}).get("auto_response_message") or "Lead captured successfully.",
        lead=service.serialize_lead(lead),
    )


@router.post("/create", response_model=LeadCaptureResponse)
def create_lead_alias(
    payload: LeadCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> LeadCaptureResponse:
    return capture_lead(payload, background_tasks, request, db)


@router.get("", response_model=LeadListResponse)
def list_leads(
    workspace_id: uuid.UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    return LeadService().list_leads(
        db,
        current_user,
        workspace_id=workspace_id,
        status_filter=status_filter,
        priority_filter=priority,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/list", response_model=LeadListResponse)
def list_leads_alias(
    workspace_id: uuid.UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    return list_leads(workspace_id, status_filter, priority, search, date_from, date_to, current_user, db)


@router.get("/{lead_id}", response_model=LeadDetailResponse)
def get_lead_detail(
    lead_id: uuid.UUID,
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadDetailResponse:
    return LeadService().get_lead_detail(db, current_user, workspace_id=workspace_id, lead_id=lead_id)


@router.patch("/{lead_id}", response_model=LeadSummary)
def update_lead(
    lead_id: uuid.UUID,
    workspace_id: uuid.UUID,
    payload: LeadUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadSummary:
    return LeadService().update_lead(db, current_user, workspace_id=workspace_id, lead_id=lead_id, payload=payload)


@router.put("/update-status", response_model=LeadSummary)
def update_lead_status(
    payload: LeadStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadSummary:
    return LeadService().update_lead_status(db, current_user, payload)


@router.post("/assign-note", response_model=LeadSummary)
def assign_lead_note(
    payload: LeadNoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadSummary:
    return LeadService().assign_note(db, current_user, payload)


@router.post("/export")
def export_leads(
    payload: LeadExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    csv_text = LeadService().export_leads_csv(db, current_user, payload)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads-export.csv"},
    )


@router.get("/settings", response_model=LeadCaptureSettingsResponse)
def get_lead_capture_settings(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadCaptureSettingsResponse:
    return LeadService().get_settings(db, current_user, workspace_id)


@router.put("/settings", response_model=LeadCaptureSettingsResponse)
def update_lead_capture_settings(
    payload: LeadCaptureSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadCaptureSettingsResponse:
    return LeadService().update_settings(db, current_user, payload)


@handoff_router.post("/handoff", response_model=HumanHandoffResponse)
def request_human_handoff(
    payload: HumanHandoffRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HumanHandoffResponse:
    service = LeadService()
    response = service.register_handoff(
        db,
        current_user,
        workspace_id=payload.workspace_id,
        session_id=payload.session_id,
        reason=payload.reason,
        message=payload.message,
        background_tasks=background_tasks,
    )
    return response
