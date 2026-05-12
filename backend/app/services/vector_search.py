from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentChunk
from app.services.retrieval_types import RetrievalFilters, SearchHit
from app.services.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    hits: list[SearchHit]


class VectorSearcher:
    def __init__(self, vector_store: QdrantVectorStore) -> None:
        self.vector_store = vector_store

    def search(
        self,
        db: Session,
        query_embedding: list[float],
        filters: RetrievalFilters,
        top_k: int = 20,
    ) -> VectorSearchResult:
        search_filter = {"filter": {"must": [{"key": "workspace_id", "match": {"value": str(filters.workspace_id)}}]}}
        if filters.document_ids:
            search_filter["filter"]["must"].append(
                {
                    "key": "document_id",
                    "match": {"any": [str(document_id) for document_id in filters.document_ids]},
                }
            )
        elif filters.document_id:
            search_filter["filter"]["must"].append({"key": "document_id", "match": {"value": str(filters.document_id)}})
        if filters.file_name:
            search_filter["filter"]["must"].append({"key": "file_name", "match": {"value": filters.file_name}})
        if filters.file_type:
            search_filter["filter"]["must"].append({"key": "content_type", "match": {"value": filters.file_type}})
        if filters.upload_date:
            search_filter["filter"]["must"].append({"key": "upload_date", "match": {"value": filters.upload_date.isoformat()}})

        raw_hits = self.vector_store.search_points(query_embedding, search_filter["filter"], top_k)
        logger.info(
            "Vector search completed",
            extra={"workspace_id": filters.workspace_id, "candidate_count": len(raw_hits)},
        )
        if not raw_hits:
            return VectorSearchResult(hits=[])

        point_ids = [hit["id"] for hit in raw_hits]
        db_chunks = db.scalars(
            select(DocumentChunk).where(DocumentChunk.qdrant_point_id.in_(point_ids))
        ).all()
        chunk_map = {chunk.qdrant_point_id: chunk for chunk in db_chunks}

        hits: list[SearchHit] = []
        for item in raw_hits:
            chunk = chunk_map.get(item["id"])
            if not chunk:
                continue
            hits.append(
                SearchHit(
                    chunk_id=item["id"],
                    text=chunk.content,
                    vector_score=float(item.get("score", 0.0)),
                    metadata=chunk.metadata_json or {},
                )
            )
        return VectorSearchResult(hits=hits)
