from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Document, DocumentChunk, User
from app.schemas.document import DocumentSummary
from app.services.event_tracker import EventTracker
from app.services.document_processing import (
    calculate_checksum,
    decode_content,
    remove_original_file,
    store_original_file,
    stored_file_exists,
    validate_upload,
)
from app.core.input_validator import validate_file_signature
from app.services.index_pipeline import IndexPipeline, run_indexing_job


def _is_benign_qdrant_delete_error(exc: Exception) -> bool:
    message = str(exc)
    return "Qdrant request failed with HTTP 404" in message or "Not found: Collection" in message


def serialize_document(document: Document) -> DocumentSummary:
    return DocumentSummary(
        id=document.id,
        workspace_id=document.workspace_id,
        title=document.title,
        source_type=document.source_type,
        storage_path=document.storage_path,
        mime_type=document.mime_type,
        file_size=document.file_size,
        checksum=document.checksum,
        ingestion_status=document.ingestion_status,
        summary=document.summary,
        metadata_json=document.metadata_json,
        created_at=document.created_at,
        updated_at=document.updated_at,
        chunk_count=len(document.chunks),
    )


def list_documents_for_workspace(db: Session, workspace_id: uuid.UUID) -> list[DocumentSummary]:
    documents = db.scalars(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.workspace_id == workspace_id)
        .order_by(Document.created_at.desc())
    ).all()
    return [serialize_document(document) for document in documents]


def get_document_or_404(db: Session, workspace_id: uuid.UUID, document_id: uuid.UUID) -> Document:
    document = db.scalar(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == document_id, Document.workspace_id == workspace_id)
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


def create_document_from_upload(
    db: Session,
    workspace_id: uuid.UUID,
    current_user: User,
    filename: str,
    mime_type: str,
    file_size: int,
    content_base64: str,
) -> DocumentSummary:
    validate_upload(filename, mime_type, file_size)
    file_bytes = decode_content(content_base64)
    validate_file_signature(filename, mime_type, file_bytes)
    if len(file_bytes) != file_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file size does not match the provided metadata.",
        )

    document = Document(
        workspace_id=workspace_id,
        uploaded_by_user_id=current_user.id,
        title=filename,
        source_type="file",
        mime_type=mime_type,
        file_size=file_size,
        ingestion_status="pending",
        metadata_json={"original_filename": filename, "source": "file"},
    )
    db.add(document)
    db.flush()

    storage_path = store_original_file(str(workspace_id), str(document.id), filename, file_bytes)
    document.storage_path = storage_path
    document.checksum = calculate_checksum(file_bytes)
    EventTracker().track_document_uploaded(db, document=document, current_user=current_user)
    db.commit()
    db.refresh(document)
    return serialize_document(document)


def mark_document_for_reindex(db: Session, workspace_id: uuid.UUID, document_id: uuid.UUID) -> DocumentSummary:
    document = get_document_or_404(db, workspace_id, document_id)
    if not document.storage_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document storage path is missing.")
    if not stored_file_exists(document.storage_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored document file was not found.")
    document.ingestion_status = "pending"
    document.metadata_json = {
        **(document.metadata_json or {}),
        "processing_error": None,
    }
    db.commit()
    db.refresh(document)
    return serialize_document(document)


def delete_document(
    db: Session,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    pipeline: IndexPipeline | None = None,
) -> None:
    document = get_document_or_404(db, workspace_id, document_id)
    try:
        (pipeline or IndexPipeline()).remove_document_index(document)
    except Exception as exc:  # noqa: BLE001
        if not _is_benign_qdrant_delete_error(exc):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to delete document vectors from Qdrant: {exc}",
            ) from exc
    remove_original_file(document.storage_path)
    for chunk in list(document.chunks):
        db.delete(chunk)
    db.flush()
    db.delete(document)
    db.commit()


def queue_document_indexing(document_id: uuid.UUID) -> None:
    from app.services.redis_queue import shared_task_queue

    if shared_task_queue.enqueue("document.index", {"document_id": str(document_id)}):
        return
    run_indexing_job(document_id)
