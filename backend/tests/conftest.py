from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.core.auth_security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import AnalyticsEvent, ChatMessage, ChatSession, ChatbotSetting, User, Workspace, WorkspaceMember
from app.services.auth import build_auth_response


@dataclass
class SeededWorkspace:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    other_workspace_id: uuid.UUID
    unaffiliated_workspace_id: uuid.UUID
    session_id: uuid.UUID


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def db_session(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api_client(session_factory, monkeypatch) -> Generator[TestClient, None, None]:
    storage_root = Path(tempfile.gettempdir()) / f"backend-test-storage-{uuid.uuid4().hex}"
    storage_root.mkdir(parents=True, exist_ok=True)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    from app.services import text_extractor
    from app.core import audit_logger
    from app.main import shared_export_queue, shared_integration_queue, shared_notification_queue

    monkeypatch.setattr(text_extractor.settings, "storage_dir", str(storage_root / "uploads"))
    monkeypatch.setattr(audit_logger, "SessionLocal", session_factory)
    monkeypatch.setattr(shared_notification_queue, "start", lambda: None)
    monkeypatch.setattr(shared_notification_queue, "stop", lambda: None)
    monkeypatch.setattr(shared_export_queue, "start", lambda: None)
    monkeypatch.setattr(shared_export_queue, "stop", lambda: None)
    monkeypatch.setattr(shared_integration_queue, "start", lambda: None)
    monkeypatch.setattr(shared_integration_queue, "stop", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        shutil.rmtree(storage_root, ignore_errors=True)


@pytest.fixture()
def request_factory():
    def _make_request(path: str = "/api/v1/auth/login", method: str = "POST", headers: dict[str, str] | None = None) -> Request:
        header_items = [(key.lower().encode("utf-8"), value.encode("utf-8")) for key, value in (headers or {}).items()]
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": path,
            "headers": header_items,
            "client": ("203.0.113.10", 443),
        }
        return Request(scope)

    return _make_request


@pytest.fixture()
def seeded_workspace(db_session: Session) -> SeededWorkspace:
    user = User(
        email="owner@example.com",
        full_name="Workspace Owner",
        password_hash=hash_password("CorrectHorseBatteryStaple!"),
        is_active=True,
        is_superuser=False,
        session_nonce=uuid.uuid4().hex,
    )
    db_session.add(user)
    db_session.flush()

    workspace = Workspace(
        name="Alpha Workspace",
        slug=f"alpha-{uuid.uuid4().hex[:8]}",
        description="Primary test workspace",
        status="active",
        owner_user_id=user.id,
    )
    other_workspace = Workspace(
        name="Beta Workspace",
        slug=f"beta-{uuid.uuid4().hex[:8]}",
        description="Secondary workspace",
        status="active",
        owner_user_id=user.id,
    )
    unaffiliated_workspace = Workspace(
        name="Gamma Workspace",
        slug=f"gamma-{uuid.uuid4().hex[:8]}",
        description="No membership workspace",
        status="active",
        owner_user_id=user.id,
    )
    db_session.add_all([workspace, other_workspace, unaffiliated_workspace])
    db_session.flush()
    db_session.add_all(
        [
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"),
            WorkspaceMember(workspace_id=other_workspace.id, user_id=user.id, role="viewer"),
        ]
    )

    session = ChatSession(
        workspace_id=workspace.id,
        user_id=user.id,
        title="Quarterly Review",
        channel="web",
        status="active",
    )
    db_session.add(session)
    db_session.flush()
    db_session.add_all(
        [
            ChatMessage(chat_session_id=session.id, role="user", content="How did revenue change?"),
            ChatMessage(chat_session_id=session.id, role="assistant", content="Revenue grew 18 percent year over year."),
        ]
    )
    db_session.add(
        ChatbotSetting(
            workspace_id=workspace.id,
            display_name="Finance Assistant",
            lead_capture_enabled=True,
            lead_capture_on_first_message=True,
            lead_capture_after_message_count=2,
            lead_capture_on_low_confidence=True,
            force_lead_before_chat=False,
            lead_required_fields_json=["name", "email"],
            schedule_call_enabled=True,
            lead_notifications_enabled=False,
            notifications_enabled=False,
            lead_auto_response_message="We will follow up shortly.",
        )
    )
    db_session.add(
        AnalyticsEvent(
            workspace_id=workspace.id,
            user_id=user.id,
            chat_session_id=session.id,
            event_type="message_sent",
            event_name="message_sent",
            properties_json={"query": "How did revenue change?"},
        )
    )
    db_session.commit()
    return SeededWorkspace(
        user_id=user.id,
        workspace_id=workspace.id,
        other_workspace_id=other_workspace.id,
        unaffiliated_workspace_id=unaffiliated_workspace.id,
        session_id=session.id,
    )


@pytest.fixture()
def auth_headers(
    api_client: TestClient,
    db_session: Session,
    seeded_workspace: SeededWorkspace,
    request_factory,
) -> dict[str, str]:
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None
    _, bundle = build_auth_response(
        user,
        request_factory(headers={"User-Agent": "pytest-client"}),
    )
    for cookie_name, cookie_value in {
        "access_token": bundle.access_token,
        "refresh_token": bundle.refresh_token,
        "csrf_token": bundle.csrf_token,
    }.items():
        api_client.cookies.set(cookie_name, cookie_value, path="/")
    return {
        "User-Agent": "pytest-client",
        "X-CSRF-Token": bundle.csrf_token,
    }
