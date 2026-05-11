import unittest
import uuid

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import ChatMessage, ChatSession, ChatbotSetting, User, Workspace, WorkspaceMember
from app.schemas.lead import LeadCreateRequest, LeadCaptureSettingsUpdateRequest, LeadExportRequest, LeadUpdateRequest
from app.services.lead_qualification import LeadQualificationService
from app.services.lead_service import LeadService


class FakeNotificationService:
    def __init__(self) -> None:
        self.lead_created_calls: list[dict] = []
        self.handoff_calls: list[dict] = []

    def queue_lead_created(self, background_tasks, *, lead, workspace, chatbot_setting) -> None:
        self.lead_created_calls.append(
            {
                "background_tasks": background_tasks,
                "lead_id": str(lead.id),
                "workspace_id": str(workspace.id),
                "setting_id": str(chatbot_setting.id) if chatbot_setting else None,
            }
        )

    def queue_handoff_requested(self, background_tasks, *, workspace, chatbot_setting, session_id, reason, user_question) -> None:
        self.handoff_calls.append(
            {
                "background_tasks": background_tasks,
                "workspace_id": str(workspace.id),
                "session_id": session_id,
                "reason": reason,
                "user_question": user_question,
            }
        )


class LeadServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _seed(self):
        with self.SessionLocal() as db:
            user = User(
                email="lead@example.com",
                full_name="Lead Owner",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()
            workspace = Workspace(
                name="Lead Workspace",
                slug=f"lead-{uuid.uuid4().hex[:8]}",
                description="Lead capture workspace",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            session = ChatSession(
                workspace_id=workspace.id,
                user_id=user.id,
                title="Lead session",
                status="active",
                channel="web",
            )
            db.add(session)
            db.flush()
            db.add(ChatMessage(chat_session_id=session.id, role="user", content="I need pricing and a demo urgently."))
            db.add(
                ChatbotSetting(
                    workspace_id=workspace.id,
                    display_name="Lead Bot",
                    lead_capture_enabled=True,
                    lead_capture_on_first_message=True,
                    lead_capture_after_message_count=3,
                    lead_capture_on_low_confidence=True,
                    schedule_call_enabled=True,
                )
            )
            db.commit()
            return user.id, workspace.id, session.id

    def test_qualification_marks_high_intent_sales_lead(self) -> None:
        result = LeadQualificationService().qualify(
            message="We want pricing, a demo, and need to buy this urgently.",
            use_case="sales",
            repeated_attempts=2,
        )
        self.assertEqual(result["priority"], "high")
        self.assertEqual(result["tag"], "sales")
        self.assertTrue(result["high_intent"])

    def test_capture_prompt_triggers_on_first_message(self) -> None:
        user_id, workspace_id, session_id = self._seed()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            session = db.get(ChatSession, session_id)
            prompt = LeadService().evaluate_capture_prompt(
                db,
                session,
                query="Can someone contact me about pricing?",
                confidence="High",
            )
            self.assertTrue(prompt.should_prompt)
            self.assertEqual(prompt.trigger, "human_request")

    def test_create_lead_persists_priority_and_tag(self) -> None:
        user_id, workspace_id, session_id = self._seed()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            notifications = FakeNotificationService()
            lead = LeadService(notification_service=notifications).create_lead(
                db,
                user,
                LeadCreateRequest(
                    workspace_id=workspace_id,
                    chat_session_id=session_id,
                    name="Priya",
                    email="priya@example.com",
                    company="Example Corp",
                    use_case="demo",
                    message="We need a pricing demo urgently for our team.",
                ),
                BackgroundTasks(),
            )
            self.assertEqual(lead.priority, "high")
            self.assertEqual(lead.tag, "sales")
            self.assertTrue(lead.high_intent)
            self.assertEqual(len(notifications.lead_created_calls), 1)

    def test_handoff_marks_session_for_human_review(self) -> None:
        user_id, workspace_id, session_id = self._seed()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            notifications = FakeNotificationService()
            response = LeadService(notification_service=notifications).register_handoff(
                db,
                user,
                workspace_id=workspace_id,
                session_id=session_id,
                reason="manual_handoff",
                message="Need a human follow-up",
                background_tasks=BackgroundTasks(),
            )
            session = db.get(ChatSession, session_id)
            self.assertTrue(session.needs_human_review)
            self.assertTrue(response.lead_prompt.should_prompt)
            self.assertEqual(len(notifications.handoff_calls), 1)

    def test_update_lead_notes_and_status(self) -> None:
        user_id, workspace_id, session_id = self._seed()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            lead = LeadService().create_lead(
                db,
                user,
                LeadCreateRequest(
                    workspace_id=workspace_id,
                    chat_session_id=session_id,
                    name="Priya",
                    email="priya@example.com",
                    message="Please contact me.",
                ),
            )
            updated = LeadService().update_lead(
                db,
                user,
                workspace_id=workspace_id,
                lead_id=lead.id,
                payload=LeadUpdateRequest(status="contacted", notes="Reached out by email."),
            )
            self.assertEqual(updated.status, "contacted")
            self.assertEqual(updated.notes, "Reached out by email.")

    def test_export_includes_all_lead_fields(self) -> None:
        user_id, workspace_id, session_id = self._seed()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            LeadService().create_lead(
                db,
                user,
                LeadCreateRequest(
                    workspace_id=workspace_id,
                    chat_session_id=session_id,
                    name="Priya",
                    email="priya@example.com",
                    company="Example Corp",
                    use_case="demo",
                    message="Please contact me about pricing.",
                ),
            )
            csv_text = LeadService().export_leads_csv(
                db,
                user,
                LeadExportRequest(workspace_id=workspace_id),
            )
            self.assertIn("workspace_id", csv_text)
            self.assertIn("chat_session_id", csv_text)
            self.assertIn("use_case", csv_text)
            self.assertIn("priority", csv_text)
            self.assertIn("Example Corp", csv_text)

    def test_settings_round_trip(self) -> None:
        user_id, workspace_id, _ = self._seed()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            updated = LeadService().update_settings(
                db,
                user,
                LeadCaptureSettingsUpdateRequest(
                    workspace_id=workspace_id,
                    lead_capture_enabled=True,
                    lead_capture_on_first_message=True,
                    lead_capture_after_message_count=5,
                    lead_capture_on_low_confidence=True,
                    force_lead_before_chat=True,
                    required_fields=["name", "email", "company"],
                    schedule_call_enabled=True,
                    lead_notifications_enabled=False,
                    admin_notification_email="owner@example.com",
                    notification_webhook_url="https://example.com/webhook",
                    auto_response_message="Thanks, our team will be in touch.",
                    notification_triggers={
                        "custom.account_owner": {
                            "enabled": True,
                            "channels": ["email"],
                            "email_recipients": ["ops@example.com"],
                            "webhook_urls": [],
                        }
                    },
                    notification_template_overrides={
                        "custom.event.admin": {
                            "subject": "Custom subject",
                            "text_body": "Custom text",
                            "html_body": "<p>Custom HTML</p>",
                        }
                    },
                ),
            )
            self.assertTrue(updated.force_lead_before_chat)
            self.assertEqual(updated.required_fields, ["name", "email", "company"])
            self.assertFalse(updated.lead_notifications_enabled)
            self.assertIn("custom.account_owner", updated.notification_triggers)
            self.assertEqual(updated.notification_template_overrides["custom.event.admin"].subject, "Custom subject")


if __name__ == "__main__":
    unittest.main()
