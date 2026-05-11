from __future__ import annotations

import logging
import urllib.parse
from datetime import UTC, datetime
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, WebsiteSource
from app.services.metadata_builder import MetadataBuilder
from app.services.text_extractor import remove_original_file, store_original_file, stored_file_exists
from app.services.vector_store import QdrantVectorStore, VectorPoint
from app.services.website.chunker import WebsiteChunker
from app.services.website.embedder import WebsiteEmbedder
from app.services.website.html_parser import ExtractedWebPage, build_document_from_pages

logger = logging.getLogger(__name__)


class WebsiteIndexer:
    def __init__(
        self,
        *,
        chunker: WebsiteChunker | None = None,
        metadata_builder: MetadataBuilder | None = None,
        embedder: WebsiteEmbedder | None = None,
        vector_store: QdrantVectorStore | None = None,
    ) -> None:
        self.chunker = chunker or WebsiteChunker()
        self.metadata_builder = metadata_builder or MetadataBuilder()
        self.embedder = embedder
        self.vector_store = vector_store or QdrantVectorStore()

    def deduplicate_pages(self, pages: list[ExtractedWebPage], similarity_threshold: float = 0.96) -> list[ExtractedWebPage]:
        unique_pages: list[ExtractedWebPage] = []
        seen_urls: set[str] = set()
        seen_hashes: set[str] = set()

        for page in pages:
            if page.url in seen_urls:
                continue
            seen_urls.add(page.url)
            content_hash = page.metadata.get("content_hash")
            if content_hash and content_hash in seen_hashes:
                continue
            if any(
                SequenceMatcher(None, page.cleaned_text, existing.cleaned_text).ratio() >= similarity_threshold
                for existing in unique_pages
            ):
                continue
            if content_hash:
                seen_hashes.add(content_hash)
            unique_pages.append(page)
        return unique_pages

    def index_pages(
        self,
        db: Session,
        source: WebsiteSource,
        pages: list[ExtractedWebPage],
        *,
        synthetic_filename: str,
        checksum: str,
    ) -> None:
        if not source.document:
            raise RuntimeError("Linked document is not available.")
        if not self.embedder:
            raise RuntimeError("Website embedder is required for indexing.")

        document = source.document
        old_point_ids = [chunk.qdrant_point_id for chunk in document.chunks if chunk.qdrant_point_id]
        combined_document = build_document_from_pages(source.title or source.url, pages)
        all_chunk_drafts = []
        chunk_index_offset = 0
        crawl_date = datetime.now(UTC).isoformat()

        for page in pages:
            page_document = build_document_from_pages(page.title, [page])
            section_heading_by_order = {
                section.order: section.metadata.get("section_heading")
                for section in page_document.sections
            }
            page_chunks = self.chunker.chunk_document(page_document)
            for page_chunk in page_chunks:
                page_chunk.chunk_index = chunk_index_offset
                section_headings = [
                    heading
                    for order in page_chunk.section_orders
                    if (heading := section_heading_by_order.get(order))
                ]
                page_chunk.metadata.update(
                    {
                        "url": page.url,
                        "source_location": page.url,
                        "content_type": "url",
                        "page_title": page.title,
                        "domain": page.metadata.get("domain"),
                        "crawl_date": crawl_date,
                        "section_heading": section_headings[0] if section_headings else page.title,
                    }
                )
                chunk_index_offset += 1
            all_chunk_drafts.extend(page_chunks)

        payloads = self.metadata_builder.build_chunk_payloads(document, all_chunk_drafts)
        for payload in payloads:
            source_location = payload.metadata_json.get("source_location")
            if source_location:
                payload.metadata_json["url"] = source_location
            payload.metadata_json["content_type"] = "url"
            payload.metadata_json["source"] = "url"
            payload.metadata_json["domain"] = payload.metadata_json.get("domain") or urllib.parse.urlsplit(source.url).hostname
            payload.metadata_json["crawl_date"] = crawl_date
            payload.metadata_json["section_heading"] = payload.metadata_json.get("section_heading") or payload.metadata_json.get("page_title")

        embeddings = self.embedder.embed_texts([payload.content for payload in payloads])
        if embeddings and len(embeddings) != len(payloads):
            raise RuntimeError("Embedding count does not match crawled chunk count.")

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

            for chunk in list(document.chunks):
                db.delete(chunk)
            db.flush()

            for payload in payloads:
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        website_source_id=source.id,
                        chunk_index=payload.chunk_index,
                        content=payload.content,
                        token_count=payload.token_count,
                        embedding_model=self.embedder.model,
                        qdrant_point_id=payload.point_id,
                        metadata_json=payload.metadata_json,
                    )
                )

            combined_text = "\n\n".join(page.cleaned_text for page in pages)
            website_bytes = combined_text.encode("utf-8")
            storage_path = store_original_file(
                str(document.workspace_id),
                str(document.id),
                synthetic_filename,
                website_bytes,
            )
            if stored_file_exists(document.storage_path):
                remove_original_file(document.storage_path)
            document.storage_path = storage_path
            document.title = synthetic_filename
            document.mime_type = "text/plain"
            document.file_size = len(website_bytes)
            document.checksum = checksum
            document.summary = " ".join(combined_document.cleaned_text.split())[:240]
            document.ingestion_status = "indexed"
            document.metadata_json = {
                **(document.metadata_json or {}),
                **combined_document.metadata,
                "url": source.url,
                "domain_root": source.metadata_json.get("domain_root") if source.metadata_json else source.url,
                "page_count": len(pages),
                "crawled_urls": [page.url for page in pages],
            }

            crawl_timestamp = datetime.now(UTC)
            source.domain = urllib.parse.urlsplit(source.url).hostname
            source.page_title = pages[0].title
            source.title = pages[0].title
            source.crawl_status = "indexed"
            source.crawl_date = crawl_timestamp
            source.last_crawled_at = crawl_timestamp
            source.checksum = checksum
            source.content_snapshot = combined_text[:10000]
            source.metadata_json = {
                **(source.metadata_json or {}),
                "page_count": len(pages),
                "deduplicated_page_count": len(pages),
                "failure_reason": None,
                "processing_error": None,
                "crawl_date": crawl_date,
                "pages": [
                    {"url": page.url, "title": page.title, "author": page.metadata.get("author"), "date": page.metadata.get("date")}
                    for page in pages
                ],
            }
            logger.info(
                "Website source indexed",
                extra={
                    "source_id": str(source.id),
                    "workspace_id": str(source.workspace_id),
                    "page_count": len(pages),
                    "chunk_count": len(payloads),
                },
            )
            db.commit()
            db.refresh(source)
        except Exception:
            if created_points:
                try:
                    self.vector_store.delete_points(created_points)
                except Exception:  # noqa: BLE001
                    pass
            raise
