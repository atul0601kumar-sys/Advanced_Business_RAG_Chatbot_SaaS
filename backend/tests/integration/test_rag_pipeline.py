from __future__ import annotations

import asyncio
import uuid

import pytest

from app.models import Document, DocumentChunk, User, Workspace, WorkspaceMember
from app.services.chunker import SmartChunker
from app.services.filter_engine import FilterEngine
from app.services.hybrid_search import HybridSearcher
from app.services.index_pipeline import IndexPipeline
from app.services.query_processor import ProcessedQuery
from app.services.retrieval_service import RetrievalService
from app.services.retrieval_types import SearchHit
from app.services.text_extractor import extract_text
from tests.fixtures.sample_content import SAMPLE_CHAT_QUERY, sample_pdf_bytes, sample_text_bytes


class StubEmbedder:
    model = "test-embedding-model"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1), float(len(text) % 7)] for index, text in enumerate(texts)]


class StubVectorStore:
    def __init__(self) -> None:
        self.points = []
        self.deleted_points = []
        self.deleted_document = None
        self.collection_sizes = []

    def ensure_collection(self, vector_size: int) -> None:
        self.collection_sizes.append(vector_size)

    def upsert_points(self, points) -> None:
        self.points.extend(points)

    def delete_points(self, point_ids) -> None:
        self.deleted_points.extend(point_ids)

    def delete_document_points(self, workspace_id: str, document_id: str) -> None:
        self.deleted_document = (workspace_id, document_id)


class FakeQueryProcessor:
    def process(self, query: str) -> ProcessedQuery:
        return ProcessedQuery(
            original_query=query,
            normalized_query=query.lower(),
            keywords=query.lower().split(),
            embedding=[0.8, 0.2],
        )


class FakeVectorSearcher:
    def search(self, db, query_embedding, filters, top_k):  # noqa: ARG002
        return type(
            "VectorResult",
            (),
            {
                "hits": [
                    SearchHit(
                        chunk_id="chunk-1",
                        text="Revenue grew 18 percent year over year and onboarding improved.",
                        vector_score=0.81,
                        metadata={"document_id": "doc-1", "workspace_id": str(filters.workspace_id), "file_name": "report.pdf"},
                    ),
                    SearchHit(
                        chunk_id="chunk-2",
                        text="Support deflection increased because help flows improved.",
                        vector_score=0.56,
                        metadata={"document_id": "doc-1", "workspace_id": str(filters.workspace_id), "file_name": "report.pdf"},
                    ),
                ][:top_k]
            },
        )()


class FakeKeywordSearcher:
    def search(self, db, normalized_query, filters, top_k):  # noqa: ARG002
        return type(
            "KeywordResult",
            (),
            {
                "hits": [
                    SearchHit(
                        chunk_id="chunk-2",
                        text="Support deflection increased because help flows improved.",
                        keyword_score=2.0,
                        metadata={"document_id": "doc-1", "workspace_id": str(filters.workspace_id), "file_name": "report.pdf"},
                    ),
                    SearchHit(
                        chunk_id="chunk-1",
                        text="Revenue grew 18 percent year over year and onboarding improved.",
                        keyword_score=5.0,
                        metadata={"document_id": "doc-1", "workspace_id": str(filters.workspace_id), "file_name": "report.pdf"},
                    ),
                ][:top_k]
            },
        )()


class FakeReranker:
    def rerank(self, query: str, hits: list[SearchHit]) -> list[float]:  # noqa: ARG002
        return [0.95 if hit.chunk_id == "chunk-1" else 0.15 for hit in hits]


@pytest.mark.integration
def test_chunking_and_sample_document_extraction_are_meaningful():
    extracted = extract_text("quarterly.txt", "text/plain", sample_text_bytes())
    chunks = SmartChunker(target_chunk_tokens=25, overlap_tokens=6, min_chunk_tokens=4).chunk_document(extracted)
    assert extracted.metadata["file_type"] == "txt"
    assert len(chunks) >= 2
    assert any("revenue" in chunk.text.lower() for chunk in chunks)
    assert all(chunk.token_count > 0 for chunk in chunks)


@pytest.mark.integration
def test_index_pipeline_builds_chunks_embeddings_and_vector_points(db_session):
    user = User(email="indexer@example.com", full_name="Indexer", password_hash="hashed", is_active=True, is_superuser=False)
    db_session.add(user)
    db_session.flush()
    workspace = Workspace(name="Indexing", slug=f"idx-{uuid.uuid4().hex[:6]}", description="idx", status="active", owner_user_id=user.id)
    db_session.add(workspace)
    db_session.flush()
    db_session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
    document = Document(
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        title="report.txt",
        source_type="file",
        mime_type="text/plain",
        file_size=len(sample_text_bytes()),
        ingestion_status="pending",
        metadata_json={},
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    vector_store = StubVectorStore()
    pipeline = IndexPipeline(embedder=StubEmbedder(), vector_store=vector_store)
    result = pipeline.index_document(db_session, document, sample_text_bytes())

    stored_document = db_session.get(Document, document.id)
    assert stored_document is not None
    assert stored_document.ingestion_status == "indexed"
    assert result.chunk_count == result.vector_count
    assert result.chunk_count >= 1
    assert vector_store.collection_sizes == [2]
    assert len(vector_store.points) == result.chunk_count
    assert db_session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).count() == result.chunk_count


@pytest.mark.integration
def test_hybrid_search_and_reranking_prioritize_relevant_chunk():
    hybrid = HybridSearcher()
    combined = hybrid.combine(
        [SearchHit(chunk_id="chunk-1", text="revenue details", vector_score=0.9, metadata={})],
        [SearchHit(chunk_id="chunk-2", text="generic note", keyword_score=1.0, metadata={}), SearchHit(chunk_id="chunk-1", text="revenue details", keyword_score=5.0, metadata={})],
        top_k=5,
    )
    assert combined[0].chunk_id == "chunk-1"


@pytest.mark.integration
def test_retrieval_service_returns_relevant_results_offline(db_session, seeded_workspace):
    service = RetrievalService(
        query_processor=FakeQueryProcessor(),
        vector_searcher=FakeVectorSearcher(),
        keyword_searcher=FakeKeywordSearcher(),
        reranker=FakeReranker(),
        filter_engine=FilterEngine(),
    )
    response = asyncio.run(service.retrieve(db_session, seeded_workspace.workspace_id, SAMPLE_CHAT_QUERY, None))
    assert response.final_chunks_count >= 1
    assert response.results[0].chunk_id == "chunk-1"
    assert "Revenue" in response.results[0].text
