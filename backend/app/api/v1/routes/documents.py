import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_workspace_role
from app.models import User, WorkspaceMember
from app.schemas.auth import MessageResponse
from app.schemas.document import DocumentActionResponse, DocumentSummary, DocumentUploadRequest
from app.services.documents import (
    create_document_from_upload,
    delete_document,
    get_document_or_404,
    list_documents_for_workspace,
    mark_document_for_reindex,
    queue_document_indexing,
    serialize_document,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])


@router.get("", response_model=list[DocumentSummary])
def list_documents(
    workspace_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member", "viewer")),
    db: Session = Depends(get_db),
) -> list[DocumentSummary]:
    return list_documents_for_workspace(db, workspace_id)


@router.post("", response_model=DocumentActionResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    workspace_id: uuid.UUID,
    payload: DocumentUploadRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> DocumentActionResponse:
    document = create_document_from_upload(
        db=db,
        workspace_id=workspace_id,
        current_user=current_user,
        filename=payload.filename,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
        content_base64=payload.content_base64,
    )
    background_tasks.add_task(queue_document_indexing, document.id)
    return DocumentActionResponse(message="Document uploaded and queued for indexing.", document=document)


@router.get("/{document_id}", response_model=DocumentSummary)
def get_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member", "viewer")),
    db: Session = Depends(get_db),
) -> DocumentSummary:
    document = get_document_or_404(db, workspace_id, document_id)
    return serialize_document(document)


@router.post("/{document_id}/reindex", response_model=DocumentActionResponse)
def reindex_uploaded_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> DocumentActionResponse:
    document = mark_document_for_reindex(db, workspace_id, document_id)
    background_tasks.add_task(queue_document_indexing, document.id)
    return DocumentActionResponse(message="Document re-indexing has been queued.", document=document)


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_uploaded_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_document(db, workspace_id, document_id)
    return MessageResponse(message="Document deleted successfully.")
