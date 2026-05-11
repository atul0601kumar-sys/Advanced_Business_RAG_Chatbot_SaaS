import unittest
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Document, DocumentChunk, FAQ, User, WebsiteSource, Workspace, WorkspaceMember
from app.services.faq_generator import CitationDraft, GeneratedFAQCandidate
from app.services.faq_service import FAQService
from app.services.topic_extractor import ExtractedTopic


class FakeTopicExtractor:
    def extract_topics(self, source):
        return [ExtractedTopic(name="Pricing Policy", summary="Pricing and billing rules.", keywords=["pricing", "billing"])]


class FakeFAQGenerator:
    def generate(self, source, topics, *, max_faqs_per_source=5):
        primary_question = (
            "What pricing policy applies to enterprise customers?"
            if source.source_type == "document"
            else "What support response time is available on the standard plan?"
        )
        primary_answer = (
            "Enterprise customers are billed monthly based on active seats and usage commitments."
            if source.source_type == "document"
            else "Standard plan support requests receive a first response within one business day."
        )
        return [
            GeneratedFAQCandidate(
                question=primary_question,
                answer=primary_answer,
                category="Pricing Policy",
                source=source.source_label,
                confidence_score=0.91,
                citations=[CitationDraft(file_name="pricing.pdf", page_number=2, chunk_preview="Billed monthly based on active seats.")],
                source_type=source.source_type,
                source_id=source.source_id,
                generation_fingerprint=source.fingerprint,
            ),
            GeneratedFAQCandidate(
                question=primary_question,
                answer="Duplicate variant that should be removed.",
                category="Pricing Policy",
                source=source.source_label,
                confidence_score=0.55,
                citations=[],
                source_type=source.source_type,
                source_id=source.source_id,
                generation_fingerprint=source.fingerprint,
            ),
        ]


class FAQServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_generation_dedup_and_match(self) -> None:
        with self.SessionLocal() as db:
            user = User(
                email="faq-user@example.com",
                full_name="FAQ User",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()
            workspace = Workspace(
                name="FAQ Workspace",
                slug=f"faq-workspace-{uuid.uuid4().hex[:8]}",
                description="workspace for faq tests",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            document = Document(
                workspace_id=workspace.id,
                uploaded_by_user_id=user.id,
                title="pricing.pdf",
                source_type="file",
                mime_type="application/pdf",
                file_size=100,
                checksum="doc-checksum",
                ingestion_status="indexed",
                summary="Pricing reference",
            )
            db.add(document)
            db.flush()
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    website_source_id=None,
                    chunk_index=0,
                    content="Enterprise customers are billed monthly based on active seats and annual commitments.",
                    token_count=20,
                    embedding_model="fake",
                    qdrant_point_id=f"point-{uuid.uuid4()}",
                    metadata_json={"page_number": 2},
                )
            )
            website_doc = Document(
                workspace_id=workspace.id,
                uploaded_by_user_id=user.id,
                title="support-page.txt",
                source_type="url",
                mime_type="text/plain",
                file_size=100,
                checksum="web-checksum",
                ingestion_status="indexed",
                summary="Support page",
            )
            db.add(website_doc)
            db.flush()
            source = WebsiteSource(
                workspace_id=workspace.id,
                document_id=website_doc.id,
                url="https://example.com/support",
                domain="example.com",
                title="Support",
                crawl_status="indexed",
                checksum="web-checksum",
                content_snapshot="Support hours and SLA",
            )
            db.add(source)
            db.flush()
            db.add(
                DocumentChunk(
                    document_id=website_doc.id,
                    website_source_id=source.id,
                    chunk_index=0,
                    content="Support requests receive a first response within one business day for standard plans.",
                    token_count=18,
                    embedding_model="fake",
                    qdrant_point_id=f"point-{uuid.uuid4()}",
                    metadata_json={"page_number": 1},
                )
            )
            db.commit()

            service = FAQService(topic_extractor=FakeTopicExtractor(), faq_generator=FakeFAQGenerator())
            stats = service.generate_faqs_for_workspace(db, workspace_id=workspace.id)
            self.assertEqual(stats.created_count, 2)
            faqs = db.scalars(select(FAQ).where(FAQ.workspace_id == workspace.id)).all()
            self.assertEqual(len(faqs), 2)
            self.assertTrue(all(faq.status == "draft" for faq in faqs))

            faqs[0].status = "approved"
            db.commit()

            match = service.find_best_match(db, workspace.id, "What pricing policy applies to enterprise customers?")
            self.assertIsNotNone(match)
            self.assertEqual(match.faq.question, "What pricing policy applies to enterprise customers?")


if __name__ == "__main__":
    unittest.main()
