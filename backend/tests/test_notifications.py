import unittest
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.models import NotificationJob, NotificationLog, User, Workspace, WorkspaceMember
from app.schemas.notification import NotificationSettingsUpdateRequest, NotificationTestEmailRequest, NotificationWebhookRequest
from app.services.notification_queue import NotificationQueue
from app.services.notification_service import NotificationService


class FakeEmailService:
    def __init__(self) -> None:
        self.requests = []

    def send(self, request) -> None:
        self.requests.append(request)


class FakeWebhookService:
    def __init__(self) -> None:
        self.calls = []

    def validate_url(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            raise ValueError("Webhook URLs must use http or https and include a host.")
        return url

    def send(self, webhook_url: str, payload: dict):
        self.calls.append({"url": webhook_url, "payload": payload})
        return type("WebhookResult", (), {"status_code": 200, "response_body": "ok"})()


class NotificationModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
        self.settings = Settings(
            frontend_url="http://localhost:3000",
            notification_email_max_retries=1,
            notification_webhook_max_retries=1,
            notification_queue_batch_size=20,
            notification_queue_enabled=False,
        )
        self.fake_email = FakeEmailService()
        self.fake_webhook = FakeWebhookService()
        self.queue = NotificationQueue(
            settings=self.settings,
            email_service=self.fake_email,
            webhook_service=self.fake_webhook,
            session_factory=self.SessionLocal,
            sleep_fn=lambda _: None,
        )
        self.service = NotificationService(
            settings=self.settings,
            queue=self.queue,
            webhook_service=self.fake_webhook,
            session_factory=self.SessionLocal,
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def _seed_admin(self):
        with self.SessionLocal() as db:
            user = User(
                email="owner@example.com",
                full_name="Owner",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()
            workspace = Workspace(
                name="Notify Workspace",
                slug=f"notify-{uuid.uuid4().hex[:8]}",
                description="Notification test workspace",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.commit()
            return user.id, workspace.id

    def test_update_settings_round_trip(self) -> None:
        user_id, workspace_id = self._seed_admin()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            updated = self.service.update_settings(
                db,
                user,
                NotificationSettingsUpdateRequest(
                    workspace_id=workspace_id,
                    notifications_enabled=True,
                    email_recipients=["ops@example.com", "sales@example.com"],
                    webhook_urls=["https://example.com/hooks/lead"],
                    retry_attempts=4,
                    rate_limit_count=15,
                    rate_limit_window_seconds=120,
                    event_rules={
                        "lead.created": {
                            "enabled": True,
                            "channels": ["email", "webhook"],
                            "email_recipients": ["custom@example.com"],
                            "webhook_urls": ["https://example.com/hooks/custom"],
                        }
                    },
                    template_overrides={
                        "lead.created.admin": {
                            "subject": "Custom lead subject",
                            "text_body": "Lead: ${lead_name}",
                            "html_body": "<p>${lead_name}</p>",
                        }
                    },
                ),
            )
            self.assertEqual(updated.email_recipients, ["ops@example.com", "sales@example.com"])
            self.assertEqual(updated.retry_attempts, 4)
            self.assertIn("lead.created", updated.event_rules)
            self.assertEqual(updated.template_overrides["lead.created.admin"].subject, "Custom lead subject")

    def test_lead_created_queues_jobs_and_worker_sends_them(self) -> None:
        user_id, workspace_id = self._seed_admin()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            self.service.update_settings(
                db,
                user,
                NotificationSettingsUpdateRequest(
                    workspace_id=workspace_id,
                    notifications_enabled=True,
                    email_recipients=["ops@example.com"],
                    webhook_urls=["https://example.com/hooks/lead"],
                    retry_attempts=2,
                    rate_limit_count=20,
                    rate_limit_window_seconds=60,
                    event_rules={},
                    template_overrides={},
                ),
            )

        queued = self.service.enqueue_lead_created(
            {
                "id": "lead-1",
                "workspace_id": str(workspace_id),
                "chat_session_id": "session-1",
                "name": "Priya",
                "email": "priya@example.com",
                "phone": "+1 555 0100",
                "company": "Example Corp",
                "message": "Please contact me urgently.",
                "priority": "high",
                "tag": "sales",
                "high_intent": True,
            },
            {"id": str(workspace_id), "name": "Notify Workspace", "slug": "notify"},
            {
                "notifications_enabled": True,
                "notification_email_recipients": ["ops@example.com"],
                "notification_webhook_urls": ["https://example.com/hooks/lead"],
                "notification_retry_attempts": 2,
                "notification_rate_limit_count": 20,
                "notification_rate_limit_window_seconds": 60,
                "notification_triggers": {},
                "notification_template_overrides": {},
            },
        )
        self.assertEqual(queued, 5)

        with self.SessionLocal() as db:
            jobs = db.scalars(select(NotificationJob)).all()
            self.assertEqual(len(jobs), 5)
            logs = db.scalars(select(NotificationLog)).all()
            self.assertEqual(len(logs), 5)
            self.assertTrue(all(log.status == "pending" for log in logs))

        processed = self.queue.process_pending_jobs(limit=10)
        self.assertEqual(processed, 5)
        self.assertEqual(len(self.fake_email.requests), 3)
        self.assertEqual(len(self.fake_webhook.calls), 2)

        with self.SessionLocal() as db:
            sent_logs = db.scalars(select(NotificationLog)).all()
            self.assertTrue(all(log.status == "sent" for log in sent_logs))

    def test_test_email_and_manual_webhook_queue_jobs(self) -> None:
        user_id, workspace_id = self._seed_admin()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            self.service.update_settings(
                db,
                user,
                NotificationSettingsUpdateRequest(
                    workspace_id=workspace_id,
                    notifications_enabled=True,
                    email_recipients=["ops@example.com"],
                    webhook_urls=["https://example.com/hooks/notify"],
                    retry_attempts=3,
                    rate_limit_count=20,
                    rate_limit_window_seconds=60,
                    event_rules={},
                    template_overrides={},
                ),
            )
            email_jobs = self.service.queue_test_email(
                db,
                user,
                NotificationTestEmailRequest(workspace_id=workspace_id, to_addresses=[]),
            )
            webhook_jobs = self.service.queue_manual_webhook(
                db,
                user,
                NotificationWebhookRequest(
                    workspace_id=workspace_id,
                    event_name="custom.account_owner",
                    payload={"account_id": "acct-1"},
                    webhook_urls=[],
                ),
            )
            self.assertEqual(email_jobs, 1)
            self.assertEqual(webhook_jobs, 1)

        processed = self.queue.process_pending_jobs(limit=10)
        self.assertEqual(processed, 2)
        self.assertEqual(len(self.fake_email.requests), 1)
        self.assertEqual(len(self.fake_webhook.calls), 1)

    def test_list_logs_returns_clear_status_rows(self) -> None:
        user_id, workspace_id = self._seed_admin()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            self.service.update_settings(
                db,
                user,
                NotificationSettingsUpdateRequest(
                    workspace_id=workspace_id,
                    notifications_enabled=True,
                    email_recipients=["ops@example.com"],
                    webhook_urls=[],
                    retry_attempts=2,
                    rate_limit_count=20,
                    rate_limit_window_seconds=60,
                    event_rules={},
                    template_overrides={},
                ),
            )
        self.service.enqueue_lead_created(
            {
                "id": "lead-2",
                "workspace_id": str(workspace_id),
                "chat_session_id": None,
                "name": "Asha",
                "email": "asha@example.com",
                "phone": None,
                "company": None,
                "message": "Need details.",
                "priority": "medium",
                "tag": "sales",
                "high_intent": False,
            },
            {"id": str(workspace_id), "name": "Notify Workspace", "slug": "notify"},
            {
                "notifications_enabled": True,
                "notification_email_recipients": ["ops@example.com"],
                "notification_webhook_urls": [],
                "notification_retry_attempts": 2,
                "notification_rate_limit_count": 20,
                "notification_rate_limit_window_seconds": 60,
                "notification_triggers": {},
                "notification_template_overrides": {},
            },
        )
        self.queue.process_pending_jobs(limit=10)
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            response = self.service.list_logs(db, user, workspace_id=workspace_id, limit=20)
            self.assertGreaterEqual(response.total, 2)
            self.assertTrue(all(item.status in {"pending", "sent", "failed"} for item in response.items))


if __name__ == "__main__":
    unittest.main()
