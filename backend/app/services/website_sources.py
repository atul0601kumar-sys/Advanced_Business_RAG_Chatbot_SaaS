from __future__ import annotations

import logging
import uuid
import urllib.parse

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Document, User, WebsiteSource
from app.schemas.website_source import WebsiteSourceSummary
from app.services.event_tracker import EventTracker
from app.services.embedder import EmbeddingClient, get_default_embedder
from app.services.text_extractor import remove_original_file
from app.services.vector_store import QdrantVectorStore
from app.services.website.chunker import WebsiteChunker
from app.services.website.website_indexer import WebsiteIndexer
from app.services.faq_service import FAQService
from app.services.website_crawler import (
    CrawlError,
    CrawlRequest,
    WebsiteCrawler,
    UrlValidationService,
    combined_checksum,
    synthetic_website_filename,
)

settings = get_settings()
logger = logging.getLogger(__name__)


def serialize_website_source(source: WebsiteSource) -> WebsiteSourceSummary:
    chunk_count = len(source.document.chunks) if source.document else 0
    return WebsiteSourceSummary(
        id=source.id,
        workspace_id=source.workspace_id,
        document_id=source.document_id,
        url=source.url,
        domain=source.domain,
        page_title=source.page_title,
        title=source.title,
        crawl_status=source.crawl_status,
        crawl_date=source.crawl_date,
        last_crawled_at=source.last_crawled_at,
        checksum=source.checksum,
        chunk_count=chunk_count,
        metadata_json=source.metadata_json,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def list_website_sources(db: Session, workspace_id: uuid.UUID) -> list[WebsiteSourceSummary]:
    sources = db.scalars(
        select(WebsiteSource)
        .options(selectinload(WebsiteSource.document).selectinload(Document.chunks))
        .where(WebsiteSource.workspace_id == workspace_id)
        .order_by(WebsiteSource.created_at.desc())
    ).all()
    return [serialize_website_source(source) for source in sources]


def get_website_source_or_404(db: Session, workspace_id: uuid.UUID, source_id: uuid.UUID) -> WebsiteSource:
    source = db.scalar(
        select(WebsiteSource)
        .options(selectinload(WebsiteSource.document).selectinload(Document.chunks))
        .where(WebsiteSource.id == source_id, WebsiteSource.workspace_id == workspace_id)
    )
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Website source not found.")
    return source


def create_website_source(
    db: Session,
    workspace_id: uuid.UUID,
    current_user: User,
    *,
    url: str,
    domain_root: str | None,
    max_depth: int | None,
    max_pages: int | None,
) -> WebsiteSourceSummary:
    validator = UrlValidationService()
    normalized_url = validator.validate_and_normalize(url)
    normalized_root = validator.validate_and_normalize(domain_root or url)
    validator.assert_within_domain_root(normalized_url, normalized_root)
    domain = urllib.parse.urlsplit(normalized_url).hostname

    existing = db.scalar(
        select(WebsiteSource).where(
            WebsiteSource.workspace_id == workspace_id,
            WebsiteSource.url == normalized_url,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This website URL has already been added to the workspace.",
        )

    document = Document(
        workspace_id=workspace_id,
        uploaded_by_user_id=current_user.id,
        title=synthetic_website_filename(normalized_url),
        source_type="url",
        mime_type="text/plain",
        ingestion_status="pending",
        metadata_json={
            "source": "url",
            "url": normalized_url,
            "domain_root": normalized_root,
        },
    )
    db.add(document)
    db.flush()

    source = WebsiteSource(
        workspace_id=workspace_id,
        document_id=document.id,
        url=normalized_url,
        domain=domain,
        page_title=None,
        title=None,
        crawl_status="pending",
        crawl_date=None,
        metadata_json={
            "domain_root": normalized_root,
            "max_depth": max_depth if max_depth is not None else settings.website_crawler_max_depth,
            "max_pages": max_pages if max_pages is not None else settings.website_crawler_max_pages,
            "normalized_url": normalized_url,
        },
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    logger.info("Website source added for crawl", extra={"workspace_id": str(workspace_id), "url": normalized_url})
    return serialize_website_source(source)


def queue_existing_website_source(db: Session, workspace_id: uuid.UUID, source_id: uuid.UUID) -> WebsiteSourceSummary:
    source = get_website_source_or_404(db, workspace_id, source_id)
    if source.crawl_status == "crawling":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This website source is already crawling.")
    source.crawl_status = "pending"
    source.metadata_json = {
        **(source.metadata_json or {}),
        "failure_reason": None,
        "processing_error": None,
    }
    if source.document:
        source.document.ingestion_status = "pending"
        source.document.metadata_json = {
            **(source.document.metadata_json or {}),
            "failure_reason": None,
            "processing_error": None,
        }
    db.commit()
    db.refresh(source)
    return serialize_website_source(source)


def mark_website_source_for_reindex(db: Session, workspace_id: uuid.UUID, source_id: uuid.UUID) -> WebsiteSourceSummary:
    source = get_website_source_or_404(db, workspace_id, source_id)
    source.crawl_status = "pending"
    if source.document:
        source.document.ingestion_status = "pending"
        source.document.metadata_json = {
            **(source.document.metadata_json or {}),
            "failure_reason": None,
            "processing_error": None,
        }
    source.metadata_json = {
        **(source.metadata_json or {}),
        "failure_reason": None,
        "processing_error": None,
    }
    db.commit()
    db.refresh(source)
    return serialize_website_source(source)


def delete_website_source(db: Session, workspace_id: uuid.UUID, source_id: uuid.UUID) -> None:
    source = get_website_source_or_404(db, workspace_id, source_id)
    document = source.document
    if document:
        _remove_document_index(document)
        remove_original_file(document.storage_path)
        for chunk in list(document.chunks):
            db.delete(chunk)
        db.flush()
        db.delete(document)
    db.delete(source)
    db.commit()
    logger.info("Website source deleted", extra={"workspace_id": str(workspace_id), "source_id": str(source_id)})


def queue_website_source_indexing(background_tasks: BackgroundTasks, source_id: uuid.UUID) -> None:
    from app.services.redis_queue import shared_task_queue

    if shared_task_queue.enqueue("website.index", {"source_id": str(source_id)}):
        return
    background_tasks.add_task(run_website_indexing_job, source_id)


def run_website_indexing_job(source_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        source = db.scalar(
            select(WebsiteSource)
            .options(selectinload(WebsiteSource.document).selectinload(Document.chunks))
            .where(WebsiteSource.id == source_id)
        )
        if not source or not source.document:
            return
        try:
            _crawl_and_index_source(db, source)
        except Exception as exc:  # noqa: BLE001
            source = db.get(WebsiteSource, source_id)
            if not source:
                return
            failure_reason = exc.reason if isinstance(exc, CrawlError) else "indexing_failed"
            logger.exception("Website source crawl failed", extra={"source_id": str(source_id), "failure_reason": failure_reason})
            source.crawl_status = "failed"
            source.metadata_json = {
                **(source.metadata_json or {}),
                "failure_reason": failure_reason,
                "processing_error": str(exc),
            }
            if source.document:
                source.document.ingestion_status = "failed"
                source.document.metadata_json = {
                    **(source.document.metadata_json or {}),
                    "failure_reason": failure_reason,
                    "processing_error": str(exc),
                }
            db.commit()


def _crawl_and_index_source(
    db: Session,
    source: WebsiteSource,
    *,
    crawler: WebsiteCrawler | None = None,
    chunker: WebsiteChunker | None = None,
    metadata_builder: object | None = None,
    embedder: EmbeddingClient | None = None,
    vector_store: QdrantVectorStore | None = None,
) -> None:
    if not source.document:
        raise RuntimeError("Website source is missing its linked document.")

    source.crawl_status = "crawling"
    source.document.ingestion_status = "processing"
    source.metadata_json = {
        **(source.metadata_json or {}),
        "failure_reason": None,
        "processing_error": None,
    }
    source.document.metadata_json = {
        **(source.document.metadata_json or {}),
        "failure_reason": None,
        "processing_error": None,
    }
    db.flush()

    crawl_metadata = source.metadata_json or {}
    crawled = (crawler or WebsiteCrawler()).crawl(
        CrawlRequest(
            url=source.url,
            domain_root=crawl_metadata.get("domain_root"),
            max_depth=int(crawl_metadata.get("max_depth") or settings.website_crawler_max_depth),
            max_pages=int(crawl_metadata.get("max_pages") or settings.website_crawler_max_pages),
        )
    )
    if not crawled.pages:
        raise RuntimeError("No readable pages were extracted from the provided URL.")
    indexer = WebsiteIndexer(
        chunker=chunker or WebsiteChunker(),
        embedder=embedder or get_default_embedder(),
        vector_store=vector_store or QdrantVectorStore(),
    )
    crawled.pages = indexer.deduplicate_pages(crawled.pages)
    if not crawled.pages:
        raise RuntimeError("Only duplicate or boilerplate pages were found for the provided URL.")

    _index_crawled_pages(
        db,
        source,
        crawled,
        indexer=indexer,
    )


def _index_crawled_pages(
    db: Session,
    source: WebsiteSource,
    crawled,
    *,
    indexer: WebsiteIndexer,
) -> None:
    source.metadata_json = {
        **(source.metadata_json or {}),
        "visited_urls": crawled.visited_urls,
        "blocked_urls": crawled.blocked_urls,
    }
    indexer.index_pages(
        db,
        source,
        crawled.pages,
        synthetic_filename=synthetic_website_filename(source.url),
        checksum=combined_checksum([page.cleaned_text for page in crawled.pages]),
    )
    EventTracker().track_website_crawled(db, source=source)
    if source.document_id:
        FAQService().generate_faqs_for_workspace(
            db,
            workspace_id=source.workspace_id,
            document_ids=[source.document_id],
            website_source_ids=[source.id],
        )


def _remove_document_index(document: Document) -> None:
    QdrantVectorStore().delete_document_points(str(document.workspace_id), str(document.id))
