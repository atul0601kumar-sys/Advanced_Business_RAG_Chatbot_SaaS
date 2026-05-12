from __future__ import annotations

from datetime import date

from sqlalchemy import Select, func

from app.models import Document, DocumentChunk
from app.services.retrieval_types import RetrievalFilters


class FilterEngine:
    def build_filters(self, workspace_id: str, request_filters) -> RetrievalFilters:
        document_ids: list = []
        if request_filters:
            for document_id in request_filters.document_ids or []:
                if document_id not in document_ids:
                    document_ids.append(document_id)
            if request_filters.document_id and request_filters.document_id not in document_ids:
                document_ids.append(request_filters.document_id)

        return RetrievalFilters(
            workspace_id=workspace_id,
            document_id=document_ids[0] if len(document_ids) == 1 else None,
            document_ids=document_ids,
            file_name=request_filters.file_name if request_filters else None,
            file_type=request_filters.file_type.lower().lstrip(".") if request_filters and request_filters.file_type else None,
            upload_date=request_filters.upload_date if request_filters else None,
        )

    def apply_sql_filters(self, statement: Select, filters: RetrievalFilters) -> Select:
        statement = statement.join(Document, Document.id == DocumentChunk.document_id).where(
            Document.workspace_id == filters.workspace_id
        )
        if filters.document_ids:
            statement = statement.where(Document.id.in_(filters.document_ids))
        elif filters.document_id:
            statement = statement.where(Document.id == filters.document_id)
        if filters.file_name:
            statement = statement.where(Document.title.ilike(f"%{filters.file_name}%"))
        if filters.file_type:
            statement = statement.where(func.lower(Document.title).like(f"%.{filters.file_type}"))
        if filters.upload_date:
            statement = statement.where(func.date(Document.created_at) == filters.upload_date.isoformat())
        return statement

    def build_qdrant_filter(self, filters: RetrievalFilters) -> dict:
        must_filters: list[dict] = [{"key": "workspace_id", "match": {"value": str(filters.workspace_id)}}]
        if filters.document_ids:
            must_filters.append(
                {
                    "key": "document_id",
                    "match": {"any": [str(document_id) for document_id in filters.document_ids]},
                }
            )
        elif filters.document_id:
            must_filters.append({"key": "document_id", "match": {"value": str(filters.document_id)}})
        if filters.file_name:
            must_filters.append({"key": "file_name", "match": {"value": filters.file_name}})
        if filters.file_type:
            must_filters.append({"key": "content_type", "match": {"value": filters.file_type}})
        if filters.upload_date:
            must_filters.append({"key": "upload_date", "match": {"value": filters.upload_date.isoformat()}})
        return {"must": must_filters}
