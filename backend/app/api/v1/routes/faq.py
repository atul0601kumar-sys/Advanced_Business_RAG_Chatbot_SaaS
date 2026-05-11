import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import User
from app.schemas.faq import (
    FAQBulkApproveRequest,
    FAQBulkResponse,
    FAQExportRequest,
    FAQGenerationRequest,
    FAQGenerationResponse,
    FAQListResponse,
    FAQSummary,
    FAQUpdateRequest,
)
from app.services.faq_service import FAQService

router = APIRouter(prefix="/faq", tags=["faq"])


@router.post("/generate", response_model=FAQGenerationResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_faqs(
    payload: FAQGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FAQGenerationResponse:
    generation = FAQService().queue_generation(background_tasks, db, current_user, payload)
    return FAQGenerationResponse(message="FAQ generation queued successfully.", generation=generation)


@router.get("/list", response_model=FAQListResponse)
def list_faqs(
    workspace_id: uuid.UUID,
    category: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FAQListResponse:
    service = FAQService()
    items, total, categories, generation = service.list_faqs(
        db,
        current_user,
        workspace_id=workspace_id,
        category=category,
        status_filter=status_filter,
        search=search,
        page=page,
        page_size=page_size,
    )
    return FAQListResponse(
        items=[FAQSummary(**service.serialize_faq(item)) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        categories=categories,
        generation=generation,
    )


@router.put("/update", response_model=FAQSummary)
def update_faq(
    payload: FAQUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FAQSummary:
    service = FAQService()
    faq = service.update_faq(
        db,
        current_user,
        workspace_id=payload.workspace_id,
        faq_id=payload.faq_id,
        question=payload.question,
        answer=payload.answer,
        category=payload.category,
        status_value=payload.status,
    )
    return FAQSummary(**service.serialize_faq(faq))


@router.post("/approve", response_model=FAQBulkResponse)
def approve_or_reject_faqs(
    payload: FAQBulkApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FAQBulkResponse:
    faqs = FAQService().bulk_update_status(
        db,
        current_user,
        workspace_id=payload.workspace_id,
        faq_ids=payload.faq_ids,
        action=payload.action,
    )
    return FAQBulkResponse(
        message=f"{'Approved' if payload.action == 'approve' else 'Rejected'} {len(faqs)} FAQ(s).",
        updated_ids=[faq.id for faq in faqs],
    )


@router.delete("/delete", response_model=FAQBulkResponse)
def delete_faqs(
    workspace_id: uuid.UUID,
    faq_ids: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FAQBulkResponse:
    parsed_ids = [uuid.UUID(item.strip()) for item in faq_ids.split(",") if item.strip()]
    deleted = FAQService().delete_faqs(db, current_user, workspace_id=workspace_id, faq_ids=parsed_ids)
    return FAQBulkResponse(message=f"Deleted {deleted} FAQ(s).", updated_ids=parsed_ids[:deleted])


@router.post("/export")
def export_faqs(
    payload: FAQExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    content, media_type = FAQService().export_faqs(
        db,
        current_user,
        workspace_id=payload.workspace_id,
        export_format=payload.format,
        status_value=payload.status,
    )
    filename = f"faq-export.{payload.format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
