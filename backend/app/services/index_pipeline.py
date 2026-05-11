from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Document, DocumentChunk
from app.services.chunker import SmartChunker
from app.services.embedder import OpenAIEmbedder
from app.services.faq_service import FAQService
from app.services.metadata_builder import MetadataBuilder
from app.services.text_extractor import extract_text, read_stored_file
from app.services.vector_store import QdrantVectorStore, VectorPoint

settings = get_settings()


@dataclass
class IndexResult:
    chunk_count: int
    vector_count: int
    summary: str
    metadata: dict


class IndexPipeline:
    def __init__(
        self,
        chunker: SmartChunker | None = None,
        metadata_builder: MetadataBuilder | None = None,
        embedder: OpenAIEmbedder | None = None,
        vector_store: QdrantVectorStore | None = None,
    ) -> None:
        self.chunker = chunker or SmartChunker()
        self.metadata_builder = metadata_builder or MetadataBuilder()
        self.embedder = embedder or OpenAIEmbedder(api_key=settings.openai_api_key)
        self.vector_store = vector_store or QdrantVectorStore()

    def index_document(self, db: Session, document: Document, file_bytes: bytes) -> IndexResult:
        old_point_ids = [chunk.qdrant_point_id for chunk in document.chunks if chunk.qdrant_point_id]
        document.ingestion_status = "processing"
        db.flush()

        extracted = extract_text(document.title, document.mime_type or "application/octet-stream", file_bytes)
        chunk_drafts = self.chunker.chunk_document(extracted)
        payloads = self.metadata_builder.build_chunk_payloads(document, chunk_drafts)
        embeddings = self.embedder.embed_texts([payload.content for payload in payloads])

        if embeddings and len(embeddings) != len(payloads):
            raise RuntimeError("Embedding count does not match chunk count.")

        created_points: list[str] = []
        try:
            if embeddings:
                self.vector_store.ensure_collection(len(embeddings[0]))
                points = [
                    VectorPoint(id=payload.point_id, vector=vector, payload=payload.metadata_json)
                    for payload, vector in zip(payloads, embeddings, strict=False)
                ]
                self.vector_store.upsert_points(points)
                created_points = [point.id for point in points]

            if old_point_ids:
                self.vector_store.delete_points([point_id for point_id in old_point_ids if point_id])

            for existing_chunk in list(document.chunks):
                db.delete(existing_chunk)
            db.flush()

            for payload in payloads:
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=payload.chunk_index,
                        content=payload.content,
                        token_count=payload.token_count,
                        embedding_model=self.embedder.model,
                        qdrant_point_id=payload.point_id,
                        metadata_json=payload.metadata_json,
                    )
                )

            summary = self._build_summary(extracted.cleaned_text)
            document.summary = summary
            document.metadata_json = {
                **(document.metadata_json or {}),
                **extracted.metadata,
                "text_length": len(extracted.cleaned_text),
                "chunk_count": len(payloads),
                "embedding_model": self.embedder.model,
                "indexing_strategy": {
                    "target_chunk_tokens": self.chunker.target_chunk_tokens,
                    "overlap_tokens": self.chunker.overlap_tokens,
                    "deduplicated": True,
                },
            }
            document.ingestion_status = "indexed"
            db.commit()
            db.refresh(document)
            db.expire(document, ["chunks"])

            return IndexResult(
                chunk_count=len(payloads),
                vector_count=len(created_points),
                summary=summary,
                metadata=document.metadata_json or {},
            )
        except Exception:
            if created_points:
                try:
                    self.vector_store.delete_points(created_points)
                except Exception:  # noqa: BLE001
                    pass
            raise

    def remove_document_index(self, document: Document) -> None:
        self.vector_store.delete_document_points(str(document.workspace_id), str(document.id))

    def _build_summary(self, text: str, limit: int = 240) -> str:
        normalized = " ".join(text.split())
        return normalized[:limit] + ("..." if len(normalized) > limit else "")


def run_indexing_job(document_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        if not document:
            return
        if not document.storage_path:
            document.ingestion_status = "failed"
            document.metadata_json = {
                **(document.metadata_json or {}),
                "processing_error": "Document storage path is missing.",
            }
            db.commit()
            return
        try:
            file_bytes = read_stored_file(document.storage_path)
            document = db.get(Document, document_id)
            pipeline = IndexPipeline()
            pipeline.index_document(db, document, file_bytes)
            FAQService().generate_faqs_for_workspace(db, workspace_id=document.workspace_id, document_ids=[document.id])
        except Exception as exc:  # noqa: BLE001
            document = db.get(Document, document_id)
            if not document:
                return
            document.ingestion_status = "failed"
            document.metadata_json = {
                **(document.metadata_json or {}),
                "processing_error": str(exc),
            }
            db.commit()
