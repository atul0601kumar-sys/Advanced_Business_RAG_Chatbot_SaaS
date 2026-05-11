from __future__ import annotations

import csv
import hashlib
import io
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Document, DocumentChunk, FAQ, User, WebsiteSource
from app.schemas.chat import ChatAnswerResponse, ChatResponseMetadata, CitationItem
from app.schemas.faq import FAQGenerationRequest, FAQGenerationState
from app.services.faq_generator import FAQGenerator, GeneratedFAQCandidate, SourceExcerpt, SourceMaterial
from app.services.faq_validator import FAQValidator
from app.services.topic_extractor import TopicExtractor


@dataclass
class FAQGenerationStats:
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    rejected_count: int = 0
    message: str = "FAQ generation completed."


@dataclass
class FAQMatch:
    faq: FAQ
    score: float


class FAQGenerationCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, FAQGenerationState] = {}
        self._approved_cache: dict[str, tuple[datetime, list[FAQ]]] = {}
        self._ttl = timedelta(minutes=10)

    def set_state(self, workspace_id: uuid.UUID, state: FAQGenerationState) -> None:
        with self._lock:
            self._states[str(workspace_id)] = state

    def get_state(self, workspace_id: uuid.UUID) -> FAQGenerationState | None:
        with self._lock:
            return self._states.get(str(workspace_id))

    def get_approved(self, workspace_id: uuid.UUID) -> list[FAQ] | None:
        with self._lock:
            cached = self._approved_cache.get(str(workspace_id))
            if cached is None:
                return None
            cached_at, faqs = cached
            if datetime.now(UTC) - cached_at > self._ttl:
                self._approved_cache.pop(str(workspace_id), None)
                return None
            return list(faqs)

    def set_approved(self, workspace_id: uuid.UUID, faqs: list[FAQ]) -> None:
        with self._lock:
            self._approved_cache[str(workspace_id)] = (datetime.now(UTC), list(faqs))

    def invalidate_workspace(self, workspace_id: uuid.UUID) -> None:
        with self._lock:
            self._approved_cache.pop(str(workspace_id), None)


shared_faq_cache = FAQGenerationCache()


class FAQService:
    def __init__(
        self,
        topic_extractor: TopicExtractor | None = None,
        faq_generator: FAQGenerator | None = None,
        faq_validator: FAQValidator | None = None,
        cache: FAQGenerationCache | None = None,
    ) -> None:
        self.topic_extractor = topic_extractor or TopicExtractor()
        self.faq_generator = faq_generator or FAQGenerator()
        self.faq_validator = faq_validator or FAQValidator()
        self.cache = cache or shared_faq_cache

    def queue_generation(
        self,
        background_tasks: BackgroundTasks,
        db: Session,
        current_user: User,
        payload: FAQGenerationRequest,
    ) -> FAQGenerationState:
        from app.dependencies.auth import get_workspace_member

        membership = get_workspace_member(payload.workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role to generate FAQs.")
        state = FAQGenerationState(
            status="queued",
            message="FAQ generation has been queued.",
            started_at=datetime.now(UTC),
        )
        self.cache.set_state(payload.workspace_id, state)
        background_tasks.add_task(self.run_generation_job, payload.model_dump(mode="json"))
        return state

    def run_generation_job(self, payload: dict) -> None:
        from app.db.session import SessionLocal

        workspace_id = uuid.UUID(payload["workspace_id"])
        self.cache.set_state(
            workspace_id,
            FAQGenerationState(
                status="running",
                message="Generating FAQs from indexed knowledge sources.",
                started_at=datetime.now(UTC),
            ),
        )
        with SessionLocal() as db:
            try:
                stats = self.generate_faqs_for_workspace(
                    db,
                    workspace_id=workspace_id,
                    document_ids=[uuid.UUID(value) for value in payload.get("document_ids", [])],
                    website_source_ids=[uuid.UUID(value) for value in payload.get("website_source_ids", [])],
                    force=bool(payload.get("force", False)),
                    max_faqs_per_source=int(payload.get("max_faqs_per_source", 5)),
                )
                self.cache.set_state(
                    workspace_id,
                    FAQGenerationState(
                        status="completed",
                        message=stats.message,
                        started_at=self.cache.get_state(workspace_id).started_at if self.cache.get_state(workspace_id) else None,
                        completed_at=datetime.now(UTC),
                        created_count=stats.created_count,
                        updated_count=stats.updated_count,
                        skipped_count=stats.skipped_count,
                        rejected_count=stats.rejected_count,
                    ),
                )
            except Exception as exc:
                self.cache.set_state(
                    workspace_id,
                    FAQGenerationState(
                        status="failed",
                        message=f"FAQ generation failed: {exc}",
                        started_at=self.cache.get_state(workspace_id).started_at if self.cache.get_state(workspace_id) else None,
                        completed_at=datetime.now(UTC),
                    ),
                )

    def generate_faqs_for_workspace(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        document_ids: list[uuid.UUID] | None = None,
        website_source_ids: list[uuid.UUID] | None = None,
        force: bool = False,
        max_faqs_per_source: int = 5,
    ) -> FAQGenerationStats:
        materials = self._load_source_materials(
            db,
            workspace_id=workspace_id,
            document_ids=document_ids or [],
            website_source_ids=website_source_ids or [],
        )
        if not materials:
            return FAQGenerationStats(message="No indexed document or website content is available for FAQ generation.")

        stats = FAQGenerationStats()
        existing_faqs = db.scalars(select(FAQ).where(FAQ.workspace_id == workspace_id)).all()
        existing_by_question = {faq.normalized_question: faq for faq in existing_faqs}
        existing_fingerprints = {faq.generation_fingerprint for faq in existing_faqs if faq.generation_fingerprint}

        for source in materials:
            if not force and source.fingerprint in existing_fingerprints:
                stats.skipped_count += 1
                continue
            topics = self.topic_extractor.extract_topics(source)
            generated = self.faq_generator.generate(source, topics, max_faqs_per_source=max_faqs_per_source)
            validated: list[GeneratedFAQCandidate] = []
            for candidate in generated:
                clean = self.faq_validator.validate_candidate(candidate, source)
                if clean is None:
                    stats.rejected_count += 1
                    continue
                validated.append(clean)
            unique_candidates = self.faq_validator.deduplicate_candidates(
                validated,
                existing_normalized_questions=set(existing_by_question.keys()),
            )
            for candidate in unique_candidates:
                normalized = self.faq_validator.normalize_question(candidate.question)
                existing = existing_by_question.get(normalized)
                if existing and existing.status == "approved":
                    stats.skipped_count += 1
                    continue
                if existing:
                    existing.question = candidate.question
                    existing.answer = candidate.answer
                    existing.category = candidate.category
                    existing.source = candidate.source
                    existing.status = "draft"
                    existing.confidence_score = candidate.confidence_score
                    existing.source_type = candidate.source_type
                    existing.source_id = candidate.source_id
                    existing.generation_fingerprint = candidate.generation_fingerprint
                    existing.citations_json = [self._citation_to_dict(item) for item in candidate.citations]
                    stats.updated_count += 1
                    continue
                faq = FAQ(
                    workspace_id=workspace_id,
                    question=candidate.question,
                    answer=candidate.answer,
                    category=candidate.category,
                    source=candidate.source,
                    status="draft",
                    confidence_score=candidate.confidence_score,
                    normalized_question=normalized,
                    source_type=candidate.source_type,
                    source_id=candidate.source_id,
                    generation_fingerprint=candidate.generation_fingerprint,
                    citations_json=[self._citation_to_dict(item) for item in candidate.citations],
                )
                db.add(faq)
                db.flush()
                existing_by_question[normalized] = faq
                stats.created_count += 1

        db.commit()
        self.cache.invalidate_workspace(workspace_id)
        stats.message = (
            f"FAQ generation completed. Created {stats.created_count}, updated {stats.updated_count}, "
            f"skipped {stats.skipped_count}, rejected {stats.rejected_count}."
        )
        return stats

    def list_faqs(
        self,
        db: Session,
        current_user: User,
        *,
        workspace_id: uuid.UUID,
        category: str | None,
        status_filter: str | None,
        search: str | None,
        page: int,
        page_size: int,
    ):
        from app.dependencies.auth import get_workspace_member

        get_workspace_member(workspace_id, current_user, db)
        query = select(FAQ).where(FAQ.workspace_id == workspace_id)
        if category:
            query = query.where(FAQ.category == category)
        if status_filter:
            query = query.where(FAQ.status == status_filter)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(or_(FAQ.question.ilike(pattern), FAQ.answer.ilike(pattern), FAQ.source.ilike(pattern)))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = db.scalars(
            query.order_by(FAQ.updated_at.desc(), FAQ.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        categories = db.scalars(
            select(FAQ.category).where(FAQ.workspace_id == workspace_id).distinct().order_by(FAQ.category.asc())
        ).all()
        return items, int(total), list(categories), self.cache.get_state(workspace_id)

    def update_faq(self, db: Session, current_user: User, *, workspace_id: uuid.UUID, faq_id: uuid.UUID, question: str, answer: str, category: str, status_value: str | None):
        from app.dependencies.auth import get_workspace_member

        membership = get_workspace_member(workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role to edit FAQs.")
        faq = self._get_workspace_faq(db, workspace_id, faq_id)
        faq.question = " ".join(question.split())
        faq.answer = " ".join(answer.split())
        faq.category = " ".join(category.split())
        faq.normalized_question = self.faq_validator.normalize_question(faq.question)
        if status_value:
            faq.status = status_value
        db.commit()
        db.refresh(faq)
        self.cache.invalidate_workspace(workspace_id)
        return faq

    def bulk_update_status(self, db: Session, current_user: User, *, workspace_id: uuid.UUID, faq_ids: list[uuid.UUID], action: str) -> list[FAQ]:
        from app.dependencies.auth import get_workspace_member

        membership = get_workspace_member(workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role to review FAQs.")
        faqs = db.scalars(select(FAQ).where(FAQ.workspace_id == workspace_id, FAQ.id.in_(faq_ids))).all()
        next_status = "approved" if action == "approve" else "rejected"
        for faq in faqs:
            faq.status = next_status
        db.commit()
        self.cache.invalidate_workspace(workspace_id)
        return faqs

    def delete_faqs(self, db: Session, current_user: User, *, workspace_id: uuid.UUID, faq_ids: list[uuid.UUID]) -> int:
        from app.dependencies.auth import get_workspace_member

        membership = get_workspace_member(workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role to delete FAQs.")
        faqs = db.scalars(select(FAQ).where(FAQ.workspace_id == workspace_id, FAQ.id.in_(faq_ids))).all()
        deleted = len(faqs)
        for faq in faqs:
            db.delete(faq)
        db.commit()
        self.cache.invalidate_workspace(workspace_id)
        return deleted

    def export_faqs(self, db: Session, current_user: User, *, workspace_id: uuid.UUID, export_format: str, status_value: str) -> tuple[str, str]:
        from app.dependencies.auth import get_workspace_member

        get_workspace_member(workspace_id, current_user, db)
        faqs = db.scalars(
            select(FAQ).where(FAQ.workspace_id == workspace_id, FAQ.status == status_value).order_by(FAQ.category.asc(), FAQ.question.asc())
        ).all()
        if export_format == "json":
            payload = [
                {
                    "id": str(faq.id),
                    "question": faq.question,
                    "answer": faq.answer,
                    "category": faq.category,
                    "source": faq.source,
                    "workspace_id": str(faq.workspace_id),
                    "status": faq.status,
                    "confidence_score": faq.confidence_score,
                    "created_at": faq.created_at.isoformat(),
                    "updated_at": faq.updated_at.isoformat(),
                }
                for faq in faqs
            ]
            return json.dumps(payload, indent=2), "application/json"
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["question", "answer", "category", "source", "status", "confidence_score", "created_at", "updated_at"],
        )
        writer.writeheader()
        for faq in faqs:
            writer.writerow(
                {
                    "question": faq.question,
                    "answer": faq.answer,
                    "category": faq.category,
                    "source": faq.source,
                    "status": faq.status,
                    "confidence_score": faq.confidence_score,
                    "created_at": faq.created_at.isoformat(),
                    "updated_at": faq.updated_at.isoformat(),
                }
            )
        return output.getvalue(), "text/csv"

    def find_best_match(self, db: Session, workspace_id: uuid.UUID, query: str) -> FAQMatch | None:
        normalized_query = self.faq_validator.normalize_question(query)
        if not normalized_query:
            return None
        faqs = self.cache.get_approved(workspace_id)
        if faqs is None:
            faqs = db.scalars(select(FAQ).where(FAQ.workspace_id == workspace_id, FAQ.status == "approved")).all()
            self.cache.set_approved(workspace_id, faqs)
        best_match: FAQMatch | None = None
        query_tokens = set(normalized_query.split())
        for faq in faqs:
            faq_tokens = set((faq.normalized_question or "").split())
            jaccard = (len(query_tokens & faq_tokens) / len(query_tokens | faq_tokens)) if query_tokens and faq_tokens else 0.0
            similarity = SequenceMatcher(None, normalized_query, faq.normalized_question or "").ratio()
            score = max(jaccard, similarity)
            if normalized_query == faq.normalized_question:
                score = 1.0
            score = min(1.0, score + faq.confidence_score * 0.08)
            if best_match is None or score > best_match.score:
                best_match = FAQMatch(faq=faq, score=score)
        if best_match and best_match.score >= 0.82:
            return best_match
        return None

    def build_chat_response(self, match: FAQMatch, *, processing_time_ms: int) -> ChatAnswerResponse:
        citations = [
            CitationItem(
                document_id=item.get("document_id"),
                file_name=item.get("file_name"),
                page_number=item.get("page_number"),
                url=item.get("url"),
                chunk_preview=item.get("chunk_preview", ""),
            )
            for item in (match.faq.citations_json or [])
        ]
        if not citations:
            citations = [CitationItem(file_name=None, page_number=None, url=None, chunk_preview=match.faq.source)]
        confidence = "High" if match.score >= 0.92 or match.faq.confidence_score >= 0.85 else "Medium"
        return ChatAnswerResponse(
            answer=match.faq.answer,
            citations=citations,
            confidence=confidence,
            metadata=ChatResponseMetadata(
                retrieved_chunks=len(citations),
                processing_time=processing_time_ms,
                stopped=False,
                answer_strategy="faq",
                faq_id=match.faq.id,
            ),
        )

    def serialize_faq(self, faq: FAQ):
        return {
            "id": faq.id,
            "workspace_id": faq.workspace_id,
            "question": faq.question,
            "answer": faq.answer,
            "category": faq.category,
            "source": faq.source,
            "status": faq.status,
            "confidence_score": float(faq.confidence_score),
            "created_at": faq.created_at,
            "updated_at": faq.updated_at,
            "source_type": faq.source_type,
            "source_id": faq.source_id,
            "citations": [
                CitationItem(
                    document_id=item.get("document_id"),
                    file_name=item.get("file_name"),
                    page_number=item.get("page_number"),
                    url=item.get("url"),
                    chunk_preview=item.get("chunk_preview", ""),
                )
                for item in (faq.citations_json or [])
            ],
        }

    def _load_source_materials(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        document_ids: list[uuid.UUID],
        website_source_ids: list[uuid.UUID],
    ) -> list[SourceMaterial]:
        query = (
            select(Document)
            .options(selectinload(Document.chunks), selectinload(Document.website_sources))
            .where(Document.workspace_id == workspace_id, Document.ingestion_status == "indexed")
            .order_by(Document.created_at.desc())
        )
        if document_ids:
            query = query.where(Document.id.in_(document_ids))
        documents = db.scalars(query).all()
        materials: list[SourceMaterial] = []
        allowed_website_ids = {str(item) for item in website_source_ids}
        for document in documents:
            chunks = sorted(document.chunks, key=lambda item: item.chunk_index)
            if not chunks:
                continue
            if document.source_type == "url" and document.website_sources:
                for source in document.website_sources:
                    if allowed_website_ids and str(source.id) not in allowed_website_ids:
                        continue
                    materials.append(self._build_source_material(document, chunks, source))
                continue
            materials.append(self._build_source_material(document, chunks, None))
        return materials

    def _build_source_material(self, document: Document, chunks: list[DocumentChunk], source: WebsiteSource | None) -> SourceMaterial:
        source_label = source.url if source is not None else document.title
        combined = "\n\n".join(chunk.content for chunk in chunks[:18])
        fingerprint_seed = "|".join(
            [
                str(document.id),
                str(source.id) if source is not None else "",
                document.checksum or "",
                source.checksum if source is not None and source.checksum else "",
                str(len(chunks)),
            ]
        )
        excerpts = [
            SourceExcerpt(
                index=idx,
                chunk_id=str(chunk.id),
                text=chunk.content,
                file_name=document.title if source is None else document.title,
                page_number=(chunk.metadata_json or {}).get("page_number"),
                url=source.url if source is not None else None,
            )
            for idx, chunk in enumerate(chunks[:18], start=1)
        ]
        return SourceMaterial(
            workspace_id=str(document.workspace_id),
            source_type="website" if source is not None else "document",
            source_id=str(source.id if source is not None else document.id),
            source_label=source_label,
            fingerprint=hashlib.sha256(fingerprint_seed.encode("utf-8")).hexdigest(),
            content=combined,
            excerpts=excerpts,
        )

    def _get_workspace_faq(self, db: Session, workspace_id: uuid.UUID, faq_id: uuid.UUID) -> FAQ:
        faq = db.scalar(select(FAQ).where(FAQ.workspace_id == workspace_id, FAQ.id == faq_id))
        if faq is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found.")
        return faq

    def _citation_to_dict(self, citation) -> dict:
        return {
            "document_id": citation.document_id,
            "file_name": citation.file_name,
            "page_number": citation.page_number,
            "url": citation.url,
            "chunk_preview": citation.chunk_preview,
        }
