import asyncio
import json
import unittest
import uuid
from datetime import UTC, datetime

from fastapi import BackgroundTasks
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import ChatMessage, ChatSession, Feedback, User, Workspace, WorkspaceMember
from app.schemas.chat import (
    ChatAnswerResponse,
    ChatFeedbackRequest,
    ChatMessageRequest,
    ChatRegenerateRequest,
    ChatResponseMetadata,
    ChatSessionCreateRequest,
    CitationItem,
    StopGenerationRequest,
)
from app.services.chat_service import ChatService
from app.services.rag_service import RagStreamEvent


class FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


class FakeRagService:
    def __init__(self) -> None:
        self.generate_counter = 0

    def summarize_messages(self, existing_summary, messages):
        return "summary: " + " | ".join(message.role for message in messages[-4:])

    async def stream_answer(self, **kwargs):
        stop_event = kwargs["stop_event"]
        parts = ["Revenue ", "grew ", "18% year over year."]
        partial = ""
        for part in parts:
            if stop_event.is_set():
                break
            partial += part
            yield RagStreamEvent(event_type="token", token=part)
        yield RagStreamEvent(
            event_type="final",
            result=ChatAnswerResponse(
                answer=partial.strip() or "Stopped early.",
                citations=[
                    CitationItem(
                        file_name="q1-report.pdf",
                        page_number=2,
                        url=None,
                        chunk_preview="Revenue grew 18% year over year.",
                    )
                ],
                confidence="High",
                metadata=ChatResponseMetadata(
                    retrieved_chunks=3,
                    processing_time=18,
                    stopped=stop_event.is_set(),
                ),
            ),
        )

    async def generate_answer(self, **kwargs):
        self.generate_counter += 1
        return ChatAnswerResponse(
            answer=f"Regenerated answer {self.generate_counter}",
            citations=[
                CitationItem(
                    file_name="board-pack.pdf",
                    page_number=5,
                    url=None,
                    chunk_preview="Board pack cites 14% expansion in enterprise pipeline.",
                )
            ],
            confidence="Medium",
            metadata=ChatResponseMetadata(
                retrieved_chunks=2,
                processing_time=24,
                stopped=False,
            ),
        )


class FakeNotificationService:
    def __init__(self) -> None:
        self.negative_feedback_calls: list[dict] = []

    def queue_negative_feedback(self, background_tasks, *, feedback, workspace, chatbot_setting, message, current_user) -> None:
        self.negative_feedback_calls.append(
            {
                "feedback_id": str(feedback.id),
                "workspace_id": str(workspace.id),
                "message_id": str(message.id),
                "user_id": str(current_user.id),
            }
        )


class ChatServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _seed_workspace(self):
        with self.SessionLocal() as db:
            user = User(
                email="chat-user@example.com",
                full_name="Chat User",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()

            workspace = Workspace(
                name="Chat Workspace",
                slug=f"chat-workspace-{uuid.uuid4().hex[:8]}",
                description="workspace for chat tests",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.commit()
            return user.id, workspace.id

    def test_chat_session_stream_history_regenerate_and_feedback(self) -> None:
        user_id, workspace_id = self._seed_workspace()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            self.assertIsNotNone(user)
            notifications = FakeNotificationService()
            service = ChatService(rag_service=FakeRagService(), notification_service=notifications)

            session_summary = service.create_session(
                db,
                user,
                ChatSessionCreateRequest(workspace_id=workspace_id, title="Finance QA", channel="web"),
            )
            self.assertEqual(session_summary.workspace_id, workspace_id)

            sessions = service.list_sessions(db, user, workspace_id)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].title, "Finance QA")

            payload = ChatMessageRequest(
                session_id=session_summary.id,
                message="How much did revenue grow?",
                mode="detailed",
            )
            events = asyncio.run(self._collect_events(service.stream_message(db, user, payload, FakeRequest())))

            self.assertEqual(events[0]["event"], "start")
            self.assertEqual(events[1]["event"], "token")
            self.assertEqual(events[-1]["event"], "complete")
            self.assertEqual(events[-1]["data"]["confidence"], "High")
            self.assertEqual(events[-1]["data"]["citations"][0]["file_name"], "q1-report.pdf")

            history = service.get_history(db, user, session_summary.id)
            self.assertEqual([message.role for message in history.messages], ["user", "assistant"])
            self.assertEqual(history.messages[1].content, "Revenue grew 18% year over year.")
            self.assertEqual(history.session.message_count, 2)

            regenerated = asyncio.run(
                service.regenerate_last_response(
                    db,
                    user,
                    ChatRegenerateRequest(session_id=session_summary.id, mode="concise"),
                )
            )
            self.assertEqual(regenerated.answer, "Regenerated answer 1")

            refreshed_history = service.get_history(db, user, session_summary.id)
            self.assertEqual(len(refreshed_history.messages), 2)
            self.assertEqual(refreshed_history.messages[-1].content, "Regenerated answer 1")

            feedback = service.submit_feedback(
                db,
                user,
                ChatFeedbackRequest(
                    session_id=session_summary.id,
                    message_id=refreshed_history.messages[-1].id,
                    value="down",
                    category="accuracy",
                    comment="This answer missed the source context.",
                ),
                BackgroundTasks(),
            )
            self.assertEqual(feedback.message, "Feedback saved successfully.")
            feedback_row = db.scalar(select(Feedback).where(Feedback.id == feedback.feedback_id))
            self.assertIsNotNone(feedback_row)
            self.assertEqual(feedback_row.rating, -1)
            self.assertEqual(len(notifications.negative_feedback_calls), 1)

    def test_stop_generation_signal_is_shared_between_service_instances(self) -> None:
        user_id, workspace_id = self._seed_workspace()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            self.assertIsNotNone(user)
            creator_service = ChatService(rag_service=FakeRagService())
            session_summary = creator_service.create_session(
                db,
                user,
                ChatSessionCreateRequest(workspace_id=workspace_id, title="Ops Chat", channel="web"),
            )

            handle = creator_service.stop_registry.register(session_summary.id)
            stopper_service = ChatService(rag_service=FakeRagService())
            stopped = stopper_service.stop_generation(
                db,
                user,
                StopGenerationRequest(session_id=session_summary.id, generation_id=handle.generation_id),
            )

            self.assertTrue(stopped)
            self.assertTrue(handle.stop_event.is_set())
            creator_service.stop_registry.release(handle)

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
