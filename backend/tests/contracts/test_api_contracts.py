from __future__ import annotations

from pydantic import TypeAdapter

import pytest

from app.schemas.analytics import AnalyticsOverviewResponse
from app.schemas.auth import AuthResponse
from app.schemas.chat import ChatAnswerResponse, ChatSessionSummary
from app.schemas.document import DocumentActionResponse, DocumentSummary
from app.schemas.lead import LeadCaptureResponse, LeadListResponse
from tests.fixtures.sample_content import SAMPLE_LEAD, sample_text_base64, sample_text_bytes


@pytest.mark.contract
def test_auth_response_contracts_are_stable(api_client):
    signup_response = api_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "contract@example.com",
            "full_name": "Contract User",
            "password": "CorrectHorseBatteryStaple!",
            "workspace_name": "Contract Workspace",
        },
    )
    assert signup_response.status_code == 201
    validated = AuthResponse.model_validate(signup_response.json())
    assert validated.user.email == "contract@example.com"


@pytest.mark.contract
def test_chat_response_contracts_are_stable(api_client, auth_headers, seeded_workspace, monkeypatch):
    class ContractChatService:
        def create_session(self, db, current_user, payload):  # noqa: ARG002
            return {
                "id": seeded_workspace.session_id,
                "workspace_id": payload.workspace_id,
                "user_id": current_user.id if current_user else None,
                "title": payload.title or "Contract chat",
                "status": "active",
                "channel": payload.channel,
                "started_at": "2026-01-01T00:00:00Z",
                "last_message_at": None,
                "session_summary": None,
                "needs_human_review": False,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "message_count": 0,
            }

        async def regenerate_last_response(self, db, current_user, payload):  # noqa: ARG002
            return {
                "answer": "Contract-safe answer",
                "citations": [
                    {
                        "file_name": "quarterly.txt",
                        "page_number": 1,
                        "url": None,
                        "chunk_preview": "Revenue grew 18 percent year over year.",
                    }
                ],
                "confidence": "High",
                "metadata": {
                    "retrieved_chunks": 1,
                    "processing_time": 10,
                    "stopped": False,
                },
            }

    monkeypatch.setattr("app.api.v1.routes.chat.ChatService", ContractChatService)

    create_response = api_client.post(
        "/api/v1/chat/session",
        headers=auth_headers,
        json={"workspace_id": str(seeded_workspace.workspace_id), "title": "Contract", "channel": "web"},
    )
    assert create_response.status_code == 201
    session = ChatSessionSummary.model_validate(create_response.json())
    assert session.workspace_id == seeded_workspace.workspace_id

    regenerate_response = api_client.post(
        "/api/v1/chat/regenerate",
        headers=auth_headers,
        json={"session_id": str(seeded_workspace.session_id), "mode": "detailed"},
    )
    assert regenerate_response.status_code == 200
    answer = ChatAnswerResponse.model_validate(regenerate_response.json())
    assert answer.metadata.retrieved_chunks == 1


@pytest.mark.contract
def test_document_and_lead_contracts_are_stable(api_client, auth_headers, seeded_workspace, monkeypatch):
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
    action = DocumentActionResponse.model_validate(upload_response.json())
    assert action.document is not None

    documents_response = api_client.get(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/documents",
        headers=auth_headers,
    )
    assert documents_response.status_code == 200
    documents = TypeAdapter(list[DocumentSummary]).validate_python(documents_response.json())
    assert documents

    lead_create = api_client.post(
        "/api/v1/leads/create",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "chat_session_id": str(seeded_workspace.session_id),
            "source": "chatbot",
            "schedule_call_requested": True,
            **SAMPLE_LEAD,
        },
    )
    assert lead_create.status_code == 200
    created_lead = LeadCaptureResponse.model_validate(lead_create.json())
    assert created_lead.lead.workspace_id == seeded_workspace.workspace_id

    lead_list = api_client.get(
        f"/api/v1/leads?workspace_id={seeded_workspace.workspace_id}",
        headers=auth_headers,
    )
    assert lead_list.status_code == 200
    listed = LeadListResponse.model_validate(lead_list.json())
    assert listed.total >= 1


@pytest.mark.contract
def test_analytics_contract_is_stable(api_client, auth_headers, seeded_workspace):
    response = api_client.get(
        f"/api/v1/analytics/overview?workspace_id={seeded_workspace.workspace_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = AnalyticsOverviewResponse.model_validate(response.json())
    assert payload.metrics.total_chats >= 1
