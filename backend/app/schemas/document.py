import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.input_validator import sanitize_text


class DocumentUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    file_size: int = Field(gt=0)

    @field_validator("filename", "mime_type", mode="before")
    @classmethod
    def sanitize_upload_fields(cls, value: str) -> str:
        return sanitize_text(value, max_length=255) or ""


class DocumentChunkSummary(BaseModel):
    id: uuid.UUID
    chunk_index: int
    token_count: int | None
    metadata_json: dict | None


class DocumentSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    source_type: str
    storage_path: str | None
    mime_type: str | None
    file_size: int | None
    checksum: str | None
    ingestion_status: str
    summary: str | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0


class DocumentActionResponse(BaseModel):
    message: str
    document: DocumentSummary | None = None
