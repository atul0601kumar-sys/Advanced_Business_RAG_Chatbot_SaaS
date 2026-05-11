from __future__ import annotations

from sqlalchemy import select

from app.core.config import Settings
from app.models import NotificationJob, NotificationLog, User
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


def build_service(session_factory):
    settings = Settings(
        frontend_url="http://localhost:3000",
        notification_email_max_retries=1,
        notification_webhook_max_retries=1,
        notification_queue_batch_size=20,
        notification_queue_enabled=False,
    )
    fake_email = FakeEmailService()
    fake_webhook = FakeWebhookService()
    queue = NotificationQueue(
        settings=settings,
        email_service=fake_email,
        webhook_service=fake_webhook,
        session_factory=session_factory,
        sleep_fn=lambda _: None,
    )
    service = NotificationService(
        settings=settings,
        queue=queue,
        webhook_service=fake_webhook,
        session_factory=session_factory,
    )
    return service, queue, fake_email, fake_webhook


def test_update_settings_round_trip(session_factory, db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None
    service, _, _, _ = build_service(session_factory)

    updated = service.update_settings(
        db_session,
        user,
        NotificationSettingsUpdateRequest(
            workspace_id=seeded_workspace.workspace_id,
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

    assert updated.email_recipients == ["ops@example.com", "sales@example.com"]
    assert updated.retry_attempts == 4
    assert "lead.created" in updated.event_rules
    assert updated.template_overrides["lead.created.admin"].subject == "Custom lead subject"


def test_lead_created_queues_jobs_and_worker_sends_them(session_factory, db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None
    service, queue, fake_email, fake_webhook = build_service(session_factory)

    service.update_settings(
        db_session,
        user,
        NotificationSettingsUpdateRequest(
            workspace_id=seeded_workspace.workspace_id,
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

    queued = service.enqueue_lead_created(
        {
            "id": "lead-1",
            "workspace_id": str(seeded_workspace.workspace_id),
            "chat_session_id": str(seeded_workspace.session_id),
            "name": "Priya",
            "email": "priya@example.com",
            "phone": "+1 555 0100",
            "company": "Example Corp",
            "message": "Please contact me urgently.",
            "priority": "high",
            "tag": "sales",
            "high_intent": True,
        },
        {"id": str(seeded_workspace.workspace_id), "name": "Notify Workspace", "slug": "notify"},
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
    assert queued == 5

    jobs = db_session.scalars(select(NotificationJob)).all()
    logs = db_session.scalars(select(NotificationLog)).all()
    assert len(jobs) == 5
    assert len(logs) == 5
    assert all(log.status == "pending" for log in logs)

    processed = queue.process_pending_jobs(limit=10)
    assert processed == 5
    assert len(fake_email.requests) == 3
    assert len(fake_webhook.calls) == 2

    db_session.expire_all()
    sent_logs = db_session.scalars(select(NotificationLog)).all()
    assert all(log.status == "sent" for log in sent_logs)


def test_test_email_and_manual_webhook_queue_jobs(session_factory, db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None
    service, queue, fake_email, fake_webhook = build_service(session_factory)

    service.update_settings(
        db_session,
        user,
        NotificationSettingsUpdateRequest(
            workspace_id=seeded_workspace.workspace_id,
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
    email_jobs = service.queue_test_email(
        db_session,
        user,
        NotificationTestEmailRequest(workspace_id=seeded_workspace.workspace_id, to_addresses=[]),
    )
    webhook_jobs = service.queue_manual_webhook(
        db_session,
        user,
        NotificationWebhookRequest(
            workspace_id=seeded_workspace.workspace_id,
            event_name="custom.account_owner",
            payload={"account_id": "acct-1"},
            webhook_urls=[],
        ),
    )
    assert email_jobs == 1
    assert webhook_jobs == 1

    processed = queue.process_pending_jobs(limit=10)
    assert processed == 2
    assert len(fake_email.requests) == 1
    assert len(fake_webhook.calls) == 1
