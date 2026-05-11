import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import User
from app.schemas.export import (
    AnalyticsExportRequest,
    ChatExportRequest,
    ExportJobResponse,
    FAQExportRequest,
    LeadExportRequest,
)
from app.services.export_service import ExportService
from app.services.job_queue import shared_export_queue

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/chat", response_model=ExportJobResponse, status_code=202)
def export_chat(
    payload: ChatExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportJobResponse:
    response = ExportService().create_job(db, current_user, job_type="chat", payload=payload.model_dump(mode="json"))
    shared_export_queue.enqueue(response.job_id)
    return response


@router.post("/leads", response_model=ExportJobResponse, status_code=202)
def export_leads(
    payload: LeadExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportJobResponse:
    response = ExportService().create_job(db, current_user, job_type="lead", payload=payload.model_dump(mode="json"))
    shared_export_queue.enqueue(response.job_id)
    return response


@router.post("/analytics", response_model=ExportJobResponse, status_code=202)
def export_analytics(
    payload: AnalyticsExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportJobResponse:
    response = ExportService().create_job(db, current_user, job_type="analytics", payload=payload.model_dump(mode="json"))
    shared_export_queue.enqueue(response.job_id)
    return response


@router.post("/faq", response_model=ExportJobResponse, status_code=202)
def export_faq(
    payload: FAQExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportJobResponse:
    response = ExportService().create_job(db, current_user, job_type="faq", payload=payload.model_dump(mode="json"))
    shared_export_queue.enqueue(response.job_id)
    return response


@router.get("/status/{job_id}", response_model=ExportJobResponse)
def get_export_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportJobResponse:
    return ExportService().get_status(db, current_user, job_id)


@router.get("/download/{job_id}")
def download_export(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service = ExportService()
    job = service.get_job(db, current_user, job_id)
    if job.file_url and job.file_url.startswith("http"):
        return RedirectResponse(job.file_url, status_code=307)
    job, file_bytes = service.get_download_payload(db, current_user, job_id)
    return Response(
        content=file_bytes,
        media_type=job.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{job.file_name or "export"}"'},
    )
