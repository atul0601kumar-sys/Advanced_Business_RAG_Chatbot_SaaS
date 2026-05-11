from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any
import uuid


@dataclass
class RetrievalFilters:
    workspace_id: uuid.UUID
    document_id: uuid.UUID | None = None
    file_name: str | None = None
    file_type: str | None = None
    upload_date: date | None = None


@dataclass
class SearchHit:
    chunk_id: str
    text: str
    vector_score: float = 0.0
    keyword_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
