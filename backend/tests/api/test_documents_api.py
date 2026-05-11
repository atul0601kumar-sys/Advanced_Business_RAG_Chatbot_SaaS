from __future__ import annotations

import uuid

import pytest

from app.models import Document
from tests.fixtures.sample_content import sample_text_base64, sample_text_bytes


@pytest.mark.api
def test_document_upload_reindex_and_delete_flow(api_client, auth_headers, db_session, seeded_workspace, monkeypatch):
    monkeypatch.setattr("app.api.v1.routes.documents.queue_document_indexing", lambda document_id: None)
    monkeypatch.setattr("app.services.documents.queue_document_indexing", lambda document_id: None)
    monkeypatch.setattr("app.services.documents.IndexPipeline.remove_document_index", lambda self, document: None)

    upload_response = api_client.post(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/documents",
        headers=auth_headers,
        json={
            "filename": "quarterly.txt",
            "mime_type": "text/plain",
            "content_base64": sample_text_base64(),
            "file_size": len(sample_text_bytes()),
        },
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["document"]["id"]

    reindex_response = api_client.post(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/documents/{document_id}/reindex",
        headers=auth_headers,
    )
    assert reindex_response.status_code == 200
    assert reindex_response.json()["document"]["ingestion_status"] == "pending"

    delete_response = api_client.delete(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/documents/{document_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 200
    assert db_session.get(Document, uuid.UUID(document_id)) is None
