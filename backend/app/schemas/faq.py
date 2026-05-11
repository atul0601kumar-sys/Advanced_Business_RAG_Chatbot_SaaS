import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.chat import CitationItem

FAQStatus = Literal["draft", "approved", "rejected"]
FAQBulkAction = Literal["approve", "reject"]
FAQExportFormat = Literal["csv", "json"]


class FAQSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    question: str
    answer: str
    category: str
    source: str
    status: FAQStatus
    confidence_score: float
    created_at: datetime
    updated_at: datetime
    source_type: str | None = None
    source_id: str | None = None
    citations: list[CitationItem] = Field(default_factory=list)


class FAQGenerationRequest(BaseModel):
    workspace_id: uuid.UUID
    document_ids: list[uuid.UUID] = Field(default_factory=list)
    website_source_ids: list[uuid.UUID] = Field(default_factory=list)
    force: bool = False
    max_faqs_per_source: int = Field(default=5, ge=1, le=10)


class FAQGenerationState(BaseModel):
    status: str
    message: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    rejected_count: int = 0


class FAQGenerationResponse(BaseModel):
    message: str
    generation: FAQGenerationState


class FAQListResponse(BaseModel):
    items: list[FAQSummary]
    total: int
    page: int
    page_size: int
    categories: list[str] = Field(default_factory=list)
    generation: FAQGenerationState | None = None


class FAQUpdateRequest(BaseModel):
    workspace_id: uuid.UUID
    faq_id: uuid.UUID
    question: str = Field(min_length=5, max_length=500)
    answer: str = Field(min_length=5, max_length=4000)
    category: str = Field(min_length=2, max_length=255)
    status: FAQStatus | None = None


class FAQBulkApproveRequest(BaseModel):
    workspace_id: uuid.UUID
    faq_ids: list[uuid.UUID] = Field(min_length=1)
    action: FAQBulkAction = "approve"


class FAQBulkResponse(BaseModel):
    message: str
    updated_ids: list[uuid.UUID] = Field(default_factory=list)


class FAQExportRequest(BaseModel):
    workspace_id: uuid.UUID
    format: FAQExportFormat = "csv"
    status: FAQStatus = "approved"
