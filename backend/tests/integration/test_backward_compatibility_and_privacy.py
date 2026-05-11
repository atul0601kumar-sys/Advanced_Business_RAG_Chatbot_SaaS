from __future__ import annotations

import base64
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import ChatMessage, ChatSession, Document, DocumentChunk, Lead, User
from app.schemas.lead import LeadExportRequest
from app.services.chat_service import ChatService
from app.services.documents import create_document_from_upload, delete_document, list_documents_for_workspace
from app.services.lead_service import LeadService
from tests.fixtures.sample_content import sample_text_bytes


@pytest.mark.integration
def test_legacy_chat_sessions_remain_readable(db_session, seeded_workspace):
    legacy_session = ChatSession(
        workspace_id=seeded_workspace.workspace_id,
        user_id=seeded_workspace.user_id,
        title=None,
        status="active",
        channel="web",
        session_summary=None,
    )
    db_session.add(legacy_session)
    db_session.flush()
    db_session.add(
        ChatMessage(
            chat_session_id=legacy_session.id,
            role="assistant",
            content="Legacy response with sparse metadata.",
            citations_json=None,
            token_usage_json=None,
            response_time_ms=None,
        )
    )
    db_session.commit()

    current_user = db_session.get(User, seeded_workspace.user_id)
    history = ChatService().get_history(db_session, current_user, legacy_session.id)

    assert history.session.id == legacy_session.id
    assert history.session.session_summary is None
    assert history.messages[0].citations == []
    assert history.messages[0].token_usage is None


@pytest.mark.integration
def test_legacy_documents_remain_listable_without_optional_fields(db_session, seeded_workspace):
    document = Document(
        workspace_id=seeded_workspace.workspace_id,
        uploaded_by_user_id=seeded_workspace.user_id,
        title="legacy.txt",
        source_type="file",
        mime_type="text/plain",
        file_size=0,
        checksum="legacy",
        ingestion_status="indexed",
        summary=None,
        metadata_json=None,
    )
    db_session.add(document)
    db_session.commit()

    listing = list_documents_for_workspace(db_session, seeded_workspace.workspace_id)
    legacy = next(item for item in listing if item.id == document.id)

    assert legacy.summary is None
    assert legacy.metadata_json is None
    assert legacy.chunk_count == 0


@pytest.mark.integration
def test_existing_leads_remain_readable_and_exports_stay_workspace_isolated(db_session, seeded_workspace):
    own_lead = Lead(
        workspace_id=seeded_workspace.workspace_id,
        chat_session_id=seeded_workspace.session_id,
        name="Legacy Lead",
        email="legacy@example.com",
        company=None,
        message=None,
        source="chatbot",
        status="new",
        priority="medium",
        tag="general",
        high_intent=False,
        metadata_json=None,
    )
    foreign_lead = Lead(
        workspace_id=seeded_workspace.other_workspace_id,
        chat_session_id=None,
        name="Other Workspace Lead",
        email="other@example.com",
        company=None,
        message=None,
        source="chatbot",
        status="new",
        priority="low",
        tag="general",
        high_intent=False,
        metadata_json=None,
    )
    db_session.add_all([own_lead, foreign_lead])
    db_session.commit()

    current_user = db_session.get(User, seeded_workspace.user_id)
    detail = LeadService().get_lead_detail(
        db_session,
        current_user,
        workspace_id=seeded_workspace.workspace_id,
        lead_id=own_lead.id,
    )
    csv_text = LeadService().export_leads_csv(
        db_session,
        current_user,
        LeadExportRequest(workspace_id=seeded_workspace.workspace_id),
    )

    assert detail.lead.id == own_lead.id
    assert "legacy@example.com" in csv_text
    assert "other@example.com" not in csv_text


@pytest.mark.integration
def test_deleted_documents_are_removed_from_storage_database_and_chunks(db_session, seeded_workspace, monkeypatch):
    current_user = db_session.get(User, seeded_workspace.user_id)
    assert current_user is not None

    from app.services import documents as document_service
    from app.services import text_extractor

    temp_dir = Path(tempfile.gettempdir()) / f"doc-delete-{uuid.uuid4().hex}"

    def store_file(workspace_id: str, document_id: str, filename: str, file_bytes: bytes) -> str:
        target_dir = temp_dir / workspace_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{document_id}_{filename}"
        target_path.write_bytes(file_bytes)
        return str(target_path)

    monkeypatch.setattr(document_service, "store_original_file", store_file)
    monkeypatch.setattr(document_service.EventTracker, "track_document_uploaded", lambda self, db, document, current_user: None)  # noqa: ARG005
    monkeypatch.setattr(text_extractor.settings, "storage_dir", str(temp_dir))
    file_bytes = sample_text_bytes()

    summary = create_document_from_upload(
        db_session,
        seeded_workspace.workspace_id,
        current_user,
        "privacy.txt",
        "text/plain",
        len(file_bytes),
        base64.b64encode(file_bytes).decode("utf-8"),
    )
    document = db_session.get(Document, summary.id)
    assert document is not None
    db_session.add(
        DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content="private facts",
            token_count=2,
            embedding_model="test",
        )
    )
    db_session.commit()

    class StubPipeline:
        def remove_document_index(self, document):  # noqa: ARG002
            return None

    delete_document(db_session, seeded_workspace.workspace_id, document.id, pipeline=StubPipeline())

    assert not (temp_dir / str(seeded_workspace.workspace_id) / f"{document.id}_privacy.txt").exists()
    assert db_session.get(Document, document.id) is None
    assert db_session.scalar(select(DocumentChunk).where(DocumentChunk.document_id == document.id)) is None
