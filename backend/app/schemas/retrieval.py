import uuid
from datetime import date

from pydantic import BaseModel, Field


class RetrievalFiltersRequest(BaseModel):
    document_id: uuid.UUID | None = None
    file_name: str | None = None
    file_type: str | None = None
    upload_date: date | None = None
    workspace_id: uuid.UUID | None = None


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    filters: RetrievalFiltersRequest | None = None


class RetrievalResultMetadata(BaseModel):
    document_id: str | None = None
    file_name: str | None = None
    page_number: int | None = None
    url: str | None = None
    workspace_id: str | None = None


class RetrievalResultItem(BaseModel):
    chunk_id: str
    text: str
    vector_score: float
    keyword_score: float
    hybrid_score: float
    rerank_score: float
    metadata: RetrievalResultMetadata


class RetrievalResponse(BaseModel):
    query: str
    results: list[RetrievalResultItem]
    final_chunks_count: int

