from __future__ import annotations

from sqlalchemy import select

from app.core.config import Settings
from app.models import IntegrationConnection, IntegrationDelivery, User
from app.schemas.integration import IntegrationConnectRequest, IntegrationTestRequest
from app.services.base_integration import IntegrationContext, IntegrationResult, IntegrationService
from app.services.event_dispatcher import EventDispatcher
from app.services.integration_manager import IntegrationManager, IntegrationRegistry
from app.services.integration_queue import IntegrationQueue


class FakeIntegrationProvider(IntegrationService):
    integration_type = "slack"

    def __init__(self, *, fail_first_send: bool = False) -> None:
        self.connected: list[str] = []
        self.disconnected: list[str] = []
        self.sent_events: list[tuple[str, str]] = []
        self.fail_first_send = fail_first_send
        self._send_attempts = 0

    def connect(self, context: IntegrationContext) -> IntegrationResult:
        self.connected.append(context.display_name)
        return IntegrationResult(status_code=200, response_body="connected")

    def send_event(self, context: IntegrationContext, *, event_type: str, payload: dict) -> IntegrationResult:
        self._send_attempts += 1
        if self.fail_first_send and self._send_attempts == 1:
            raise RuntimeError("temporary failure")
        self.sent_events.append((event_type, context.display_name))
        return IntegrationResult(status_code=200, response_body="sent")

    def disconnect(self, context: IntegrationContext) -> IntegrationResult:
        self.disconnected.append(context.display_name)
        return IntegrationResult(status_code=200, response_body="disconnected")

    def validate_config(self, *, config: dict, credentials: dict) -> None:
        if not config.get("channel_id"):
            raise ValueError("channel_id required")
        if not credentials.get("bot_token"):
            raise ValueError("bot_token required")


def build_manager(provider: FakeIntegrationProvider) -> tuple[IntegrationManager, Settings]:
    settings = Settings(
        integration_queue_enabled=False,
        integration_queue_batch_size=20,
        integration_retry_backoff_seconds=0.0,
    )
    registry = IntegrationRegistry()
    registry._providers["slack"] = provider  # type: ignore[attr-defined]
    return IntegrationManager(settings=settings, registry=registry), settings


def test_manager_connects_lists_and_tests_integration(db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None
    provider = FakeIntegrationProvider()
    manager, _ = build_manager(provider)

    response = manager.connect_integration(
        db_session,
        user,
        IntegrationConnectRequest(
            workspace_id=seeded_workspace.workspace_id,
            integration_type="slack",
            display_name="Sales Alerts",
            credentials={"bot_token": "xoxb-token"},
            config={"channel_id": "C123", "event_types": ["lead_created", "message_sent"]},
        ),
    )
    assert response.connection.display_name == "Sales Alerts"

    stored = db_session.scalar(select(IntegrationConnection).where(IntegrationConnection.workspace_id == seeded_workspace.workspace_id))
    assert stored is not None
    assert stored.encrypted_credentials != '{"bot_token":"xoxb-token"}'
    listing = manager.list_integrations(db_session, user, seeded_workspace.workspace_id)
    assert len(listing.connections) == 1
    assert provider.connected == ["Sales Alerts"]

    test_result = manager.test_integration(
        db_session,
        user,
        IntegrationTestRequest(
            workspace_id=seeded_workspace.workspace_id,
            integration_id=stored.id,
            event_type="lead_created",
        ),
    )
    assert test_result.status == "success"
    assert provider.sent_events[-1][0] == "lead_created"


def test_dispatcher_and_queue_process_events_with_retry(session_factory, db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None
    provider = FakeIntegrationProvider(fail_first_send=True)
    manager, settings = build_manager(provider)
    queue = IntegrationQueue(settings=settings, manager=manager, session_factory=session_factory)

    manager.connect_integration(
        db_session,
        user,
        IntegrationConnectRequest(
            workspace_id=seeded_workspace.workspace_id,
            integration_type="slack",
            display_name="Ops Alerts",
            credentials={"bot_token": "xoxb-token"},
            config={"channel_id": "C123", "event_types": ["lead_created"], "max_retries": 2},
        ),
    )
    dispatcher = EventDispatcher(settings=settings)
    queued = dispatcher.dispatch(
        db_session,
        workspace_id=seeded_workspace.workspace_id,
        event_type="lead_created",
        data={"lead_id": "lead-1", "message": "Need a demo"},
    )
    db_session.commit()
    assert queued == 1

    first_processed = queue.process_pending_jobs(limit=10)
    assert first_processed == 1
    db_session.expire_all()
    delivery = db_session.scalar(select(IntegrationDelivery).where(IntegrationDelivery.workspace_id == seeded_workspace.workspace_id))
    connection = db_session.scalar(select(IntegrationConnection).where(IntegrationConnection.workspace_id == seeded_workspace.workspace_id))
    assert delivery is not None
    assert connection is not None
    assert delivery.status == "retrying"
    assert connection.status == "active"

    second_processed = queue.process_pending_jobs(limit=10)
    assert second_processed == 1
    db_session.expire_all()
    delivery = db_session.scalar(select(IntegrationDelivery).where(IntegrationDelivery.workspace_id == seeded_workspace.workspace_id))
    connection = db_session.scalar(select(IntegrationConnection).where(IntegrationConnection.workspace_id == seeded_workspace.workspace_id))
    assert delivery is not None
    assert connection is not None
    assert delivery.status == "success"
    assert connection.status == "active"
    assert provider.sent_events == [("lead_created", "Ops Alerts")]
