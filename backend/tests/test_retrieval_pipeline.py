import asyncio
import unittest
import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Document, DocumentChunk, User, Workspace, WorkspaceMember
from app.services.context_builder import ContextBuilder
from app.services.filter_engine import FilterEngine
from app.services.hybrid_search import HybridSearcher
from app.services.keyword_search import KeywordSearcher
from app.services.query_processor import ProcessedQuery
from app.services.retrieval_service import RetrievalService
from app.services.retrieval_types import RetrievalFilters, SearchHit
from app.services.vector_search import VectorSearcher


class FakeVectorStore:
    def __init__(self) -> None:
        self.last_filter = None

    def search_points(self, query_vector, qdrant_filter, limit):
        self.last_filter = qdrant_filter
        return [
            {"id": "point-1", "score": 0.92, "payload": {"workspace_id": "unused"}},
            {"id": "point-2", "score": 0.61, "payload": {"workspace_id": "unused"}},
        ][:limit]


class FakeQueryProcessor:
    def process(self, query: str) -> ProcessedQuery:
        return ProcessedQuery(
            original_query=query,
            normalized_query=query.lower(),
            keywords=query.lower().split(),
            embedding=[0.1, 0.2, 0.3],
        )


class FakeVectorSearcher:
    def search(self, db, query_embedding, filters, top_k):
        return type(
            "VectorResult",
            (),
            {
                "hits": [
                    SearchHit(
                        chunk_id="point-1",
                        text="Revenue rose sharply in Q1 and onboarding improved.",
                        vector_score=0.9,
                        metadata={
                            "document_id": "doc-1",
                            "file_name": "q1-report.pdf",
                            "page_number": 2,
                            "workspace_id": str(filters.workspace_id),
                            "chunk_index": 1,
                            "content_hash": "hash-1",
                        },
                    ),
                    SearchHit(
                        chunk_id="point-2",
                        text="Customer support deflection increased due to updated help flows.",
                        vector_score=0.4,
                        metadata={
                            "document_id": "doc-1",
                            "file_name": "q1-report.pdf",
                            "page_number": 3,
                            "workspace_id": str(filters.workspace_id),
                            "chunk_index": 2,
                            "content_hash": "hash-2",
                        },
                    ),
                ]
            },
        )()


class FakeKeywordSearcher:
    def search(self, db, normalized_query, filters, top_k):
        return type(
            "KeywordResult",
            (),
            {
                "hits": [
                    SearchHit(
                        chunk_id="point-1",
                        text="Revenue rose sharply in Q1 and onboarding improved.",
                        keyword_score=6.0,
                        metadata={
                            "document_id": "doc-1",
                            "file_name": "q1-report.pdf",
                            "page_number": 2,
                            "workspace_id": str(filters.workspace_id),
                            "chunk_index": 1,
                            "content_hash": "hash-1",
                        },
                    ),
                    SearchHit(
                        chunk_id="point-3",
                        text="Pipeline generation improved after new demo assets shipped.",
                        keyword_score=4.0,
                        metadata={
                            "document_id": "doc-2",
                            "file_name": "pipeline-notes.txt",
                            "page_number": None,
                            "workspace_id": str(filters.workspace_id),
                            "chunk_index": 0,
                            "content_hash": "hash-3",
                        },
                    ),
                ]
            },
        )()


class FakeReranker:
    def rerank(self, query: str, hits: list[SearchHit]) -> list[float]:
        score_map = {"point-3": 0.95, "point-1": 0.85, "point-2": 0.2}
        return [score_map.get(hit.chunk_id, 0.0) for hit in hits]


class FailingVectorSearcher:
    def search(self, db, query_embedding, filters, top_k):
        raise RuntimeError("vector search unavailable")


class RetrievalPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _seed_chunks(self):
        with self.SessionLocal() as db:
            user = User(
                email="retrieval@example.com",
                full_name="Retrieval User",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()

            workspace = Workspace(
                name="Retrieval Workspace",
                slug=f"retrieval-{uuid.uuid4().hex[:8]}",
                description="retrieval tests",
                status="active",
                owner_user_id=user.id,
            )
            other_workspace = Workspace(
                name="Other Workspace",
                slug=f"other-{uuid.uuid4().hex[:8]}",
                description="other tests",
                status="active",
                owner_user_id=user.id,
            )
            db.add_all([workspace, other_workspace])
            db.flush()
            db.add_all(
                [
                    WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"),
                    WorkspaceMember(workspace_id=other_workspace.id, user_id=user.id, role="admin"),
                ]
            )
            db.flush()

            document = Document(
                workspace_id=workspace.id,
                uploaded_by_user_id=user.id,
                title="q1-report.pdf",
                source_type="file",
                storage_path="storage/q1-report.pdf",
                mime_type="application/pdf",
                file_size=1000,
                checksum="checksum",
                ingestion_status="indexed",
                created_at=datetime.now(UTC),
                metadata_json={},
            )
            other_document = Document(
                workspace_id=other_workspace.id,
                uploaded_by_user_id=user.id,
                title="other-report.pdf",
                source_type="file",
                storage_path="storage/other-report.pdf",
                mime_type="application/pdf",
                file_size=1000,
                checksum="checksum-2",
                ingestion_status="indexed",
                created_at=datetime.now(UTC),
                metadata_json={},
            )
            db.add_all([document, other_document])
            db.flush()

            db.add_all(
                [
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=0,
                        content="Revenue rose sharply in Q1 and onboarding improved.",
                        token_count=10,
                        embedding_model="model",
                        qdrant_point_id="point-1",
                        metadata_json={
                            "document_id": str(document.id),
                            "file_name": "q1-report.pdf",
                            "page_number": 2,
                            "workspace_id": str(workspace.id),
                            "chunk_index": 0,
                            "content_hash": "hash-1",
                        },
                    ),
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=1,
                        content="Customer support deflection increased due to updated help flows.",
                        token_count=11,
                        embedding_model="model",
                        qdrant_point_id="point-2",
                        metadata_json={
                            "document_id": str(document.id),
                            "file_name": "q1-report.pdf",
                            "page_number": 3,
                            "workspace_id": str(workspace.id),
                            "chunk_index": 1,
                            "content_hash": "hash-2",
                        },
                    ),
                    DocumentChunk(
                        document_id=other_document.id,
                        chunk_index=0,
                        content="This chunk belongs to another workspace entirely.",
                        token_count=9,
                        embedding_model="model",
                        qdrant_point_id="point-x",
                        metadata_json={
                            "document_id": str(other_document.id),
                            "file_name": "other-report.pdf",
                            "page_number": 1,
                            "workspace_id": str(other_workspace.id),
                            "chunk_index": 0,
                            "content_hash": "hash-x",
                        },
                    ),
                ]
            )
            db.commit()
            return workspace, document

    def test_vector_search_enforces_workspace_filter_and_returns_scores(self) -> None:
        workspace, _ = self._seed_chunks()
        with self.SessionLocal() as db:
            store = FakeVectorStore()
            searcher = VectorSearcher(store)
            filters = RetrievalFilters(workspace_id=workspace.id)
            result = searcher.search(db, [0.1, 0.2], filters, top_k=20)

            self.assertEqual(len(result.hits), 2)
            self.assertEqual(result.hits[0].chunk_id, "point-1")
            self.assertAlmostEqual(result.hits[0].vector_score, 0.92)
            self.assertEqual(store.last_filter["must"][0]["match"]["value"], str(workspace.id))

    def test_vector_search_supports_multiple_document_filters(self) -> None:
        workspace, document = self._seed_chunks()
        other_document_id = uuid.uuid4()
        with self.SessionLocal() as db:
            store = FakeVectorStore()
            searcher = VectorSearcher(store)
            filters = RetrievalFilters(
                workspace_id=workspace.id,
                document_ids=[document.id, other_document_id],
            )
            searcher.search(db, [0.1, 0.2], filters, top_k=20)

            document_filter = store.last_filter["must"][1]
            self.assertEqual(document_filter["key"], "document_id")
            self.assertEqual(
                document_filter["match"]["any"],
                [str(document.id), str(other_document_id)],
            )

    def test_keyword_search_applies_workspace_and_file_filters(self) -> None:
        workspace, document = self._seed_chunks()
        with self.SessionLocal() as db:
            searcher = KeywordSearcher(FilterEngine())
            filters = RetrievalFilters(
                workspace_id=workspace.id,
                document_id=document.id,
                file_name="q1-report",
                file_type="pdf",
            )
            result = searcher.search(db, "revenue onboarding q1", filters, top_k=20)

            self.assertEqual(len(result.hits), 1)
            self.assertEqual(result.hits[0].chunk_id, "point-1")
            self.assertGreater(result.hits[0].keyword_score, 0)

    def test_keyword_search_supports_multiple_document_filters(self) -> None:
        workspace, document = self._seed_chunks()
        with self.SessionLocal() as db:
            searcher = KeywordSearcher(FilterEngine())
            filters = RetrievalFilters(
                workspace_id=workspace.id,
                document_ids=[document.id],
            )
            result = searcher.search(db, "revenue onboarding q1", filters, top_k=20)

            self.assertEqual(len(result.hits), 1)
            self.assertTrue(all(hit.metadata["document_id"] == str(document.id) for hit in result.hits))

    def test_hybrid_search_combines_and_deduplicates(self) -> None:
        hybrid = HybridSearcher()
        combined = hybrid.combine(
            [
                SearchHit(chunk_id="a", text="alpha", vector_score=0.9, metadata={}),
                SearchHit(chunk_id="b", text="beta", vector_score=0.4, metadata={}),
            ],
            [
                SearchHit(chunk_id="a", text="alpha", keyword_score=5.0, metadata={}),
                SearchHit(chunk_id="c", text="gamma", keyword_score=8.0, metadata={}),
            ],
            top_k=10,
        )

        self.assertEqual([hit.chunk_id for hit in combined], ["a", "c", "b"])
        self.assertTrue(all(0.0 <= hit.hybrid_score <= 1.0 for hit in combined))

    def test_retrieval_service_reranks_and_returns_top_chunks(self) -> None:
        workspace, _ = self._seed_chunks()
        with self.SessionLocal() as db:
            service = RetrievalService(
                query_processor=FakeQueryProcessor(),
                vector_searcher=FakeVectorSearcher(),
                keyword_searcher=FakeKeywordSearcher(),
                reranker=FakeReranker(),
                filter_engine=FilterEngine(),
                context_builder=ContextBuilder(token_limit=400),
            )
            response = asyncio.run(service.retrieve(db, workspace.id, "Revenue pipeline", None))

            self.assertEqual(response.final_chunks_count, 3)
            self.assertEqual(response.results[0].chunk_id, "point-3")
            self.assertEqual(response.results[1].chunk_id, "point-1")
            self.assertEqual(response.results[0].metadata.workspace_id, str(workspace.id))

    def test_retrieval_service_returns_safe_fallback_on_failure(self) -> None:
        workspace, _ = self._seed_chunks()
        with self.SessionLocal() as db:
            service = RetrievalService(
                query_processor=FakeQueryProcessor(),
                vector_searcher=FailingVectorSearcher(),
                keyword_searcher=FakeKeywordSearcher(),
                reranker=FakeReranker(),
                filter_engine=FilterEngine(),
                context_builder=ContextBuilder(token_limit=400),
            )
            response = asyncio.run(service.retrieve(db, workspace.id, "Revenue pipeline", None))

            self.assertEqual(response.results, [])
            self.assertEqual(response.final_chunks_count, 0)


if __name__ == "__main__":
    unittest.main()
