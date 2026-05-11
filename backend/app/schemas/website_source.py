import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WebsiteSourceCreateRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    domain_root: str | None = Field(default=None, max_length=2048)
    max_depth: int | None = Field(default=None, ge=0, le=5)
    max_pages: int | None = Field(default=None, ge=1, le=100)


class WebsiteSourceSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID | None
    url: str
    domain: str | None
    page_title: str | None
    title: str | None
    crawl_status: str
    crawl_date: datetime | None
    last_crawled_at: datetime | None
    checksum: str | None
    chunk_count: int = 0
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime


class WebsiteSourceActionResponse(BaseModel):
    message: str
    source: WebsiteSourceSummary | None = None


class WebsiteSourceCommandRequest(WebsiteSourceCreateRequest):
    workspace_id: uuid.UUID


class WebsiteSourceQueueRequest(BaseModel):
    workspace_id: uuid.UUID
    source_id: uuid.UUID
