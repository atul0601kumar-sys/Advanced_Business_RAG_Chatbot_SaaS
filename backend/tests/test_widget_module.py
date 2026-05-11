import asyncio
import json
import unittest
import uuid

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import User, Workspace, WorkspaceMember
from app.schemas.chat import (
    ChatAnswerResponse,
    ChatFeedbackRequest,
    ChatMessageRequest,
    ChatResponseMetadata,
    ChatSessionCreateRequest,
)
from app.schemas.lead import LeadCreateRequest
from app.schemas.chat import CitationItem
from app.services.chat_service import ChatService
from app.services.lead_service import LeadService
from app.services.rag_service import RagStreamEvent
from app.services.settings_service import SettingsService


class FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


class FakeRagService:
    def summarize_messages(self, existing_summary, messages):
        return "summary"

    async def stream_answer(self, **kwargs):
        yield RagStreamEvent(event_type="token", token="Hello ")
        yield RagStreamEvent(
            event_type="final",
            result=ChatAnswerResponse(
                answer="Hello from the widget.",
                citations=[
                    CitationItem(
                        file_name="widget.pdf",
                        page_number=1,
                        url=None,
                        chunk_preview="Hello from the widget.",
                    )
                ],
                confidence="High",
                metadata=ChatResponseMetadata(
                    retrieved_chunks=1,
                    processing_time=5,
                    stopped=False,
                ),
            ),
        )


class WidgetModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _seed_workspace(self):
        with self.SessionLocal() as db:
            user = User(
                email="widget-owner@example.com",
                full_name="Widget Owner",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()
            workspace = Workspace(
                name="Widget Workspace",
                slug=f"widget-{uuid.uuid4().hex[:8]}",
                description="Widget tests",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.commit()
            return user.id, workspace.id

    def test_public_widget_session_message_feedback_and_lead_flow(self) -> None:
        owner_id, workspace_id = self._seed_workspace()
        with self.SessionLocal() as db:
            owner = db.get(User, owner_id)
            self.assertIsNotNone(owner)

            public_settings = SettingsService().get_public_settings(
                db,
                workspace_id,
                origin="http://example.com",
            )
            self.assertEqual(public_settings.workspace_id, workspace_id)
            self.assertTrue(public_settings.embed.auth_token)

            chat_service = ChatService(rag_service=FakeRagService())
            session = chat_service.create_session(
                db,
                None,
                ChatSessionCreateRequest(workspace_id=workspace_id, title="Widget session", channel="widget"),
            )
            self.assertIsNone(session.user_id)
            self.assertEqual(session.channel, "widget")

            events = asyncio.run(
                self._collect_events(
                    chat_service.stream_message(
                        db,
                        None,
                        ChatMessageRequest(session_id=session.id, message="Hello", mode="detailed"),
                        FakeRequest(),
                    ),
                )
            )
            self.assertEqual(events[0]["event"], "start")
            self.assertEqual(events[-1]["event"], "complete")

            history = chat_service.get_history(db, None, session.id)
            self.assertEqual(len(history.messages), 2)

            assistant_message = history.messages[-1]
            feedback = chat_service.submit_feedback(
                db,
                None,
                ChatFeedbackRequest(session_id=session.id, message_id=assistant_message.id, value="up"),
                BackgroundTasks(),
            )
            self.assertEqual(feedback.message, "Feedback saved successfully.")

            lead = LeadService().create_lead(
                db,
                None,
                LeadCreateRequest(
                    workspace_id=workspace_id,
                    chat_session_id=session.id,
                    name="Widget Visitor",
                    email="visitor@example.com",
                    company="Acme",
                    use_case="Support",
                    message="Please contact me.",
                    source="widget",
                ),
                BackgroundTasks(),
            )
            self.assertEqual(lead.source, "widget")

    async def _collect_events(self, stream):
        parsed = []
        async for raw_event in stream:
            stripped = raw_event.strip()
            lines = stripped.splitlines()
            event_name = lines[0].removeprefix("event: ").strip()
            data = json.loads(lines[1].removeprefix("data: ").strip())
            parsed.append({"event": event_name, "data": data})
        return parsed


if __name__ == "__main__":
    unittest.main()
