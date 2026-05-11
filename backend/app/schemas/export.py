import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ExportJobType = Literal["chat", "lead", "analytics", "faq"]
ExportFormat = Literal["csv", "json", "pdf"]
ExportJobStatus = Literal["pending", "processing", "completed", "failed"]


class ExportBaseRequest(BaseModel):
    workspace_id: uuid.UUID
    format: ExportFormat = "csv"
    date_from: datetime | None = None
    date_to: datetime | None = None
    source: str | None = Field(default=None, max_length=255)


class ChatExportRequest(ExportBaseRequest):
    session_ids: list[uuid.UUID] = Field(default_factory=list)
    user_id: uuid.UUID | None = None


class LeadExportRequest(ExportBaseRequest):
    status: str | None = Field(default=None, max_length=50)
    priority: str | None = Field(default=None, max_length=20)


class AnalyticsExportRequest(ExportBaseRequest):
    user_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None


class FAQExportRequest(ExportBaseRequest):
    status: str | None = Field(default="approved", max_length=50)
    category: str | None = Field(default=None, max_length=255)


class ExportJobResponse(BaseModel):
    job_id: uuid.UUID
    workspace_id: uuid.UUID
    type: ExportJobType
    format: ExportFormat
    status: ExportJobStatus
    file_url: str | None = None
    file_name: str | None = None
    content_type: str | None = None
    row_count: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

