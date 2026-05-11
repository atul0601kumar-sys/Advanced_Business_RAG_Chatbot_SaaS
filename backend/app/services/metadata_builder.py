from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models import Document
from app.services.chunker import ChunkDraft


@dataclass
class ChunkRecordPayload:
    point_id: str
    chunk_index: int
    content: str
    token_count: int
    metadata_json: dict[str, Any]


class MetadataBuilder:
    def build_chunk_payloads(self, document: Document, chunks: list[ChunkDraft]) -> list[ChunkRecordPayload]:
        payloads: list[ChunkRecordPayload] = []
        for chunk in chunks:
            point_id = str(uuid.uuid4())
            metadata = self._build_metadata(document, chunk, point_id)
            payloads.append(
                ChunkRecordPayload(
                    point_id=point_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.text,
                    token_count=chunk.token_count,
                    metadata_json=metadata,
                )
            )
        return payloads

    def _build_metadata(self, document: Document, chunk: ChunkDraft, point_id: str) -> dict[str, Any]:
        upload_date = document.created_at.isoformat() if isinstance(document.created_at, datetime) else None
        content_type = (document.title.rsplit(".", 1)[-1].lower() if "." in document.title else "file")
        metadata = {
            "document_id": str(document.id),
            "file_name": document.title,
            "page_number": chunk.page_number,
            "chunk_id": point_id,
            "chunk_index": chunk.chunk_index,
            "workspace_id": str(document.workspace_id),
            "upload_date": upload_date,
            "content_type": content_type,
            "source": document.source_type,
            "source_location": document.storage_path,
            "page_numbers": chunk.page_numbers,
            "section_orders": chunk.section_orders,
            **chunk.metadata,
        }
        return metadata

