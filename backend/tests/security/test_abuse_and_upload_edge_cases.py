from __future__ import annotations

import base64
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.rate_limiter import shared_rate_limiter
from app.models import User
from app.services.documents import create_document_from_upload
from app.services.text_extractor import extract_text


class StubChatService:
    async def stream_message(self, db, current_user, payload, request):  # noqa: ARG002
        yield 'event: complete\ndata: {"answer":"ok","citations":[],"confidence":"Low","metadata":{"retrieved_chunks":0,"processing_time":1,"stopped":false}}\n\n'

    def stop_generation(self, db, current_user, payload):  # noqa: ARG002
        return False


@pytest.mark.security
def test_api_rate_limiting_blocks_rapid_requests(api_client, auth_headers, seeded_workspace, monkeypatch):
    from app.core import rate_limiter

    original_limit = rate_limiter.settings.api_rate_limit_count
    original_window = rate_limiter.settings.api_rate_limit_window_seconds
    shared_rate_limiter._buckets.clear()
    monkeypatch.setattr(rate_limiter.settings, "api_rate_limit_count", 2)
    monkeypatch.setattr(rate_limiter.settings, "api_rate_limit_window_seconds", 60)

    try:
        for _ in range(2):
            response = api_client.get(
                f"/api/v1/workspaces/{seeded_workspace.workspace_id}/documents",
                headers=auth_headers,
            )
            assert response.status_code == 200

        blocked = api_client.get(
            f"/api/v1/workspaces/{seeded_workspace.workspace_id}/documents",
            headers=auth_headers,
        )
        assert blocked.status_code == 429
    finally:
        monkeypatch.setattr(rate_limiter.settings, "api_rate_limit_count", original_limit)
        monkeypatch.setattr(rate_limiter.settings, "api_rate_limit_window_seconds", original_window)
        shared_rate_limiter._buckets.clear()


@pytest.mark.security
def test_chat_rate_limiting_blocks_spam_messages(api_client, auth_headers, seeded_workspace, monkeypatch):
    from app.api.v1.routes import chat as chat_routes
    from app.core import rate_limiter

    shared_rate_limiter._buckets.clear()
    monkeypatch.setattr(rate_limiter.settings, "chat_rate_limit_count", 2)
    monkeypatch.setattr(rate_limiter.settings, "chat_rate_limit_window_seconds", 60)
    monkeypatch.setattr(chat_routes, "ChatService", StubChatService)

    try:
        for _ in range(2):
            response = api_client.post(
                "/api/v1/chat/message",
                headers=auth_headers,
                json={"session_id": str(seeded_workspace.session_id), "message": "spam", "mode": "concise"},
            )
            assert response.status_code == 200

        blocked = api_client.post(
            "/api/v1/chat/message",
            headers=auth_headers,
            json={"session_id": str(seeded_workspace.session_id), "message": "spam", "mode": "concise"},
        )
        assert blocked.status_code == 429
    finally:
        shared_rate_limiter._buckets.clear()


@pytest.mark.security
def test_very_large_upload_is_rejected(db_session, seeded_workspace, monkeypatch):
    from app.services import text_extractor

    current_user = db_session.get(User, seeded_workspace.user_id)
    assert current_user is not None
    monkeypatch.setattr(text_extractor.settings, "max_upload_size_mb", 1)

    with pytest.raises(HTTPException, match="File is too large"):
        create_document_from_upload(
            db_session,
            seeded_workspace.workspace_id,
            current_user,
            "too-large.txt",
            "text/plain",
            2 * 1024 * 1024,
            base64.b64encode(b"tiny").decode("utf-8"),
        )


@pytest.mark.security
def test_corrupted_pdf_upload_fails_gracefully():
    with pytest.raises(HTTPException, match="Uploaded PDF content is invalid"):
        extract_text("broken.pdf", "application/pdf", b"this-is-not-a-pdf")


@pytest.mark.security
def test_empty_text_upload_is_handled_without_crashing(db_session, seeded_workspace, monkeypatch):
    from app.services import documents as document_service

    current_user = db_session.get(User, seeded_workspace.user_id)
    assert current_user is not None
    temp_dir = Path(tempfile.gettempdir()) / f"empty-upload-{uuid.uuid4().hex}"
    monkeypatch.setattr(document_service, "store_original_file", lambda workspace_id, document_id, filename, file_bytes: str(temp_dir / f"{document_id}_{filename}"))  # noqa: ARG005
    monkeypatch.setattr(document_service.EventTracker, "track_document_uploaded", lambda self, db, document, current_user: None)  # noqa: ARG005

    summary = create_document_from_upload(
        db_session,
        seeded_workspace.workspace_id,
        current_user,
        "empty.txt",
        "text/plain",
        0,
        "",
    )

    assert summary.title == "empty.txt"
    assert summary.file_size == 0
    assert summary.ingestion_status == "pending"
