import unittest
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import (
    ChatMessage,
    ChatSession,
    Document,
    Feedback,
    Lead,
    UnresolvedQuestion,
    User,
    WebsiteSource,
    Workspace,
    WorkspaceMember,
)
from app.services.analytics_service import AnalyticsService
from app.services.event_tracker import EventTracker


class AnalyticsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_overview_and_query_analytics_are_workspace_scoped(self) -> None:
        workspace_one, workspace_two = self._seed()
        with self.SessionLocal() as db:
            service = AnalyticsService()

            overview = service.get_overview(
                db,
                workspace_id=workspace_one["workspace_id"],
                date_from=None,
                date_to=None,
                user_id=None,
                document_id=None,
                source=None,
            )
            self.assertEqual(overview.metrics.total_chats, 1)
            self.assertEqual(overview.metrics.total_leads, 2)
            self.assertEqual(overview.metrics.total_documents, 1)
            self.assertEqual(overview.metrics.total_website_sources, 1)
            self.assertEqual(overview.metrics.total_users, 2)
            self.assertEqual(overview.metrics.total_messages, 2)
            self.assertGreater(overview.metrics.average_response_time_ms, 0)

            queries = service.get_query_analytics(
                db,
                workspace_id=workspace_one["workspace_id"],
                date_from=None,
                date_to=None,
                user_id=None,
                document_id=None,
                source=None,
            )
            self.assertTrue(any(item.query == "How does pricing work?" for item in queries.most_asked_questions))
            self.assertTrue(any(item.keyword == "pricing" for item in queries.keywords))
            self.assertTrue(any(item.label == "pricing.pdf" for item in queries.most_used_documents))

            performance = service.get_performance_analytics(
                db,
                workspace_id=workspace_one["workspace_id"],
                date_from=None,
                date_to=None,
                user_id=None,
                document_id=None,
                source=None,
            )
            self.assertEqual(performance.unanswered_queries, 1)
            self.assertGreaterEqual(performance.retrieval_success_rate, 100.0)

            other_overview = service.get_overview(
                db,
                workspace_id=workspace_two["workspace_id"],
                date_from=None,
                date_to=None,
                user_id=None,
                document_id=None,
                source=None,
            )
            self.assertEqual(other_overview.metrics.total_chats, 1)
            self.assertEqual(other_overview.metrics.total_messages, 1)
            self.assertEqual(other_overview.metrics.total_leads, 1)
            self.assertEqual(other_overview.metrics.total_documents, 0)

    def _seed(self):
        tracker = EventTracker()
        now = datetime.now(UTC)
        with self.SessionLocal() as db:
            owner = User(
                email="owner@example.com",
                full_name="Owner",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            analyst = User(
                email="analyst@example.com",
                full_name="Analyst",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            outsider = User(
                email="other@example.com",
                full_name="Other",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add_all([owner, analyst, outsider])
            db.flush()

            workspace_one = Workspace(
                name="Workspace One",
                slug=f"workspace-one-{uuid.uuid4().hex[:8]}",
                description="Primary analytics workspace",
                status="active",
                owner_user_id=owner.id,
            )
            workspace_two = Workspace(
                name="Workspace Two",
                slug=f"workspace-two-{uuid.uuid4().hex[:8]}",
                description="Secondary analytics workspace",
                status="active",
                owner_user_id=outsider.id,
            )
            db.add_all([workspace_one, workspace_two])
            db.flush()
            db.add_all(
                [
                    WorkspaceMember(workspace_id=workspace_one.id, user_id=owner.id, role="admin"),
                    WorkspaceMember(workspace_id=workspace_one.id, user_id=analyst.id, role="team_member"),
                    WorkspaceMember(workspace_id=workspace_two.id, user_id=outsider.id, role="admin"),
                ]
            )
            db.flush()

            document = Document(
                workspace_id=workspace_one.id,
                uploaded_by_user_id=owner.id,
                title="pricing.pdf",
                source_type="file",
                storage_path="storage/pricing.pdf",
                mime_type="application/pdf",
                file_size=1200,
                ingestion_status="indexed",
            )
            db.add(document)
            db.flush()
            tracker.track_document_uploaded(db, document=document, current_user=owner)

            website_source = WebsiteSource(
                workspace_id=workspace_one.id,
                document_id=document.id,
                url="https://example.com/pricing",
                domain="example.com",
                crawl_status="indexed",
                last_crawled_at=now,
                metadata_json={"page_count": 2, "visited_urls": ["https://example.com/pricing"]},
            )
            db.add(website_source)
            db.flush()
            tracker.track_website_crawled(db, source=website_source)

            chat_session = ChatSession(
                workspace_id=workspace_one.id,
                user_id=analyst.id,
                title="Pricing thread",
                status="active",
                channel="web",
                started_at=now - timedelta(minutes=9),
                last_message_at=now - timedelta(minutes=6),
            )
            db.add(chat_session)
            db.flush()
            tracker.track_chat_started(db, session=chat_session, current_user=analyst)

            user_message = ChatMessage(
                chat_session_id=chat_session.id,
                role="user",
                content="How does pricing work?",
                created_at=now - timedelta(minutes=8),
                updated_at=now - timedelta(minutes=8),
            )
            assistant_message = ChatMessage(
                chat_session_id=chat_session.id,
                role="assistant",
                content="Pricing starts with a base subscription plus analytics usage.",
                citations_json=[
                    {
                        "document_id": str(document.id),
                        "file_name": "pricing.pdf",
                        "page_number": 2,
                        "url": "https://example.com/pricing",
                        "chunk_preview": "Pricing starts with a base subscription.",
                    }
                ],
                token_usage_json={"confidence": "High", "retrieved_chunks": 2},
                response_time_ms=820,
                created_at=now - timedelta(minutes=7),
                updated_at=now - timedelta(minutes=7),
            )
            db.add_all([user_message, assistant_message])
            db.flush()
            tracker.track_event(
                db,
                workspace_id=workspace_one.id,
                user_id=analyst.id,
                session_id=chat_session.id,
                event_type="message_sent",
                metadata={
                    "query": user_message.content,
                    "normalized_query": "how does pricing work",
                    "source": "web",
                },
                occurred_at=user_message.created_at,
            )
            tracker.track_event(
                db,
                workspace_id=workspace_one.id,
                user_id=analyst.id,
                session_id=chat_session.id,
                event_type="message_received",
                metadata={
                    "confidence": "High",
                    "confidence_score": 0.9,
                    "response_time_ms": 820,
                    "retrieved_chunks": 2,
                    "retrieval_success": True,
                    "source": "web",
                    "document_ids": [str(document.id)],
                    "citations": assistant_message.citations_json,
                },
                occurred_at=assistant_message.created_at,
            )

            feedback = Feedback(
                workspace_id=workspace_one.id,
                chat_session_id=chat_session.id,
                chat_message_id=assistant_message.id,
                user_id=analyst.id,
                rating=-1,
                category="accuracy",
                comment="Need more discount detail.",
                created_at=now - timedelta(minutes=5),
                updated_at=now - timedelta(minutes=5),
            )
            db.add(feedback)
            db.flush()
            tracker.track_feedback_submitted(
                db,
                feedback=feedback,
                confidence="High",
                response_excerpt=assistant_message.content[:120],
            )

            unanswered = UnresolvedQuestion(
                workspace_id=workspace_one.id,
                chat_session_id=chat_session.id,
                chat_message_id=user_message.id,
                question="Do you offer annual discounts?",
                normalized_question="annual discounts",
                reason="not_found_in_knowledge_base",
                status="open",
                created_at=now - timedelta(minutes=4),
                updated_at=now - timedelta(minutes=4),
            )
            db.add(unanswered)
            db.flush()
            tracker.track_unanswered_question(
                db,
                session=chat_session,
                user_message=user_message,
                question=unanswered.question,
                reason=unanswered.reason,
            )

            converted_lead = Lead(
                workspace_id=workspace_one.id,
                chat_session_id=chat_session.id,
                name="Priya",
                email="priya@example.com",
                source="chatbot",
                status="converted",
                priority="high",
                tag="sales",
                high_intent=True,
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(hours=1),
            )
            open_lead = Lead(
                workspace_id=workspace_one.id,
                chat_session_id=chat_session.id,
                name="Sam",
                email="sam@example.com",
                source="widget",
                status="new",
                priority="medium",
                tag="support",
                high_intent=False,
                created_at=now - timedelta(hours=5),
                updated_at=now - timedelta(hours=5),
            )
            other_lead = Lead(
                workspace_id=workspace_two.id,
                name="Other Lead",
                email="otherlead@example.com",
                source="chatbot",
                status="new",
                priority="low",
                tag="general",
                high_intent=False,
            )
            db.add_all([converted_lead, open_lead, other_lead])
            db.flush()
            tracker.track_lead_created(db, lead=converted_lead, current_user=owner)
            tracker.track_lead_converted(db, lead=converted_lead, current_user=owner, previous_status="qualified")
            tracker.track_lead_created(db, lead=open_lead, current_user=owner)

            other_session = ChatSession(
                workspace_id=workspace_two.id,
                user_id=outsider.id,
                title="Other chat",
                status="active",
                channel="widget",
                started_at=now - timedelta(hours=2),
                last_message_at=now - timedelta(hours=2),
            )
            db.add(other_session)
            db.flush()
            tracker.track_chat_started(db, session=other_session, current_user=outsider)
            db.add(
                ChatMessage(
                    chat_session_id=other_session.id,
                    role="user",
                    content="Other workspace message",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                )
            )
            db.commit()

            return (
                {"workspace_id": workspace_one.id},
                {"workspace_id": workspace_two.id},
            )


if __name__ == "__main__":
    unittest.main()
