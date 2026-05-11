import unittest
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.models import IntegrationConnection, IntegrationDelivery, User, Workspace, WorkspaceMember
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


class IntegrationFrameworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
        self.settings = Settings(
            integration_queue_enabled=False,
            integration_queue_batch_size=20,
            integration_retry_backoff_seconds=0.0,
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def _seed_admin(self):
        with self.SessionLocal() as db:
            user = User(
                email="integrations@example.com",
                full_name="Integration Owner",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
                session_nonce=uuid.uuid4().hex,
            )
            db.add(user)
            db.flush()
            workspace = Workspace(
                name="Integration Workspace",
                slug=f"integration-{uuid.uuid4().hex[:8]}",
                description="Integration tests",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.commit()
            return user.id, workspace.id

    def _manager_with_provider(self, provider: FakeIntegrationProvider) -> IntegrationManager:
        registry = IntegrationRegistry()
        registry._providers["slack"] = provider  # type: ignore[attr-defined]
        return IntegrationManager(settings=self.settings, registry=registry)

    def test_manager_connects_lists_and_tests_integration(self) -> None:
        user_id, workspace_id = self._seed_admin()
        provider = FakeIntegrationProvider()
        manager = self._manager_with_provider(provider)

        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            response = manager.connect_integration(
                db,
                user,
                IntegrationConnectRequest(
                    workspace_id=workspace_id,
                    integration_type="slack",
                    display_name="Sales Alerts",
                    credentials={"bot_token": "xoxb-token"},
                    config={"channel_id": "C123", "event_types": ["lead_created", "message_sent"]},
                ),
            )
            self.assertEqual(response.connection.display_name, "Sales Alerts")
            stored = db.scalar(select(IntegrationConnection).where(IntegrationConnection.workspace_id == workspace_id))
            self.assertIsNotNone(stored)
            self.assertNotEqual(stored.encrypted_credentials, '{"bot_token":"xoxb-token"}')
            listing = manager.list_integrations(db, user, workspace_id)
            self.assertEqual(len(listing.connections), 1)
            self.assertEqual(provider.connected, ["Sales Alerts"])

            test_result = manager.test_integration(
                db,
                user,
                IntegrationTestRequest(
                    workspace_id=workspace_id,
                    integration_id=stored.id,
                    event_type="lead_created",
                ),
            )
            self.assertEqual(test_result.status, "success")
            self.assertEqual(provider.sent_events[-1][0], "lead_created")

    def test_dispatcher_and_queue_process_events_with_retry(self) -> None:
        user_id, workspace_id = self._seed_admin()
        provider = FakeIntegrationProvider(fail_first_send=True)
        manager = self._manager_with_provider(provider)
        queue = IntegrationQueue(settings=self.settings, manager=manager, session_factory=self.SessionLocal)

        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            manager.connect_integration(
                db,
                user,
                IntegrationConnectRequest(
                    workspace_id=workspace_id,
                    integration_type="slack",
                    display_name="Ops Alerts",
                    credentials={"bot_token": "xoxb-token"},
                    config={"channel_id": "C123", "event_types": ["lead_created"], "max_retries": 2},
                ),
            )
            dispatcher = EventDispatcher(settings=self.settings)
            queued = dispatcher.dispatch(
                db,
                workspace_id=workspace_id,
                event_type="lead_created",
                data={"lead_id": "lead-1", "message": "Need a demo"},
            )
            db.commit()
            self.assertEqual(queued, 1)

        first_processed = queue.process_pending_jobs(limit=10)
        self.assertEqual(first_processed, 1)
        with self.SessionLocal() as db:
            delivery = db.scalar(select(IntegrationDelivery).where(IntegrationDelivery.workspace_id == workspace_id))
            connection = db.scalar(select(IntegrationConnection).where(IntegrationConnection.workspace_id == workspace_id))
            self.assertEqual(delivery.status, "retrying")
            self.assertEqual(connection.status, "active")

        second_processed = queue.process_pending_jobs(limit=10)
        self.assertEqual(second_processed, 1)
        with self.SessionLocal() as db:
            delivery = db.scalar(select(IntegrationDelivery).where(IntegrationDelivery.workspace_id == workspace_id))
            connection = db.scalar(select(IntegrationConnection).where(IntegrationConnection.workspace_id == workspace_id))
            self.assertEqual(delivery.status, "success")
            self.assertEqual(connection.status, "active")
            self.assertEqual(provider.sent_events, [("lead_created", "Ops Alerts")])


if __name__ == "__main__":
    unittest.main()
