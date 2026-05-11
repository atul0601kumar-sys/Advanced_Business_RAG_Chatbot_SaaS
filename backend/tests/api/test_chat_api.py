from __future__ import annotations

import json
import uuid

import pytest

from app.schemas.chat import ChatAnswerResponse, ChatResponseMetadata, CitationItem


class StubChatService:
    def __init__(self) -> None:
        self.created_session_id = uuid.uuid4()

    def create_session(self, db, current_user, payload):  # noqa: ARG002
        return {
            "id": self.created_session_id,
            "workspace_id": payload.workspace_id,
            "user_id": current_user.id if current_user else None,
            "title": payload.title or "New Chat",
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

    async def stream_message(self, db, current_user, payload, request):  # noqa: ARG002
        yield 'event: start\ndata: {"session_id":"%s","generation_id":"gen-1","message_id":"msg-1"}\n\n' % payload.session_id
        yield 'event: token\ndata: {"delta":"Revenue "}\n\n'
        yield 'event: token\ndata: {"delta":"grew"}\n\n'
        yield 'event: complete\ndata: {"answer":"Revenue grew","citations":[{"file_name":"report.pdf","page_number":2,"url":null,"chunk_preview":"Revenue grew 18 percent year over year."}],"confidence":"High","metadata":{"retrieved_chunks":2,"processing_time":15,"stopped":false,"message_id":"msg-1","generation_id":"gen-1"}}\n\n'

    async def regenerate_last_response(self, db, current_user, payload):  # noqa: ARG002
        return ChatAnswerResponse(
            answer="Regenerated answer",
            citations=[CitationItem(file_name="report.pdf", page_number=2, url=None, chunk_preview="Regenerated supporting evidence.")],
            confidence="Medium",
            metadata=ChatResponseMetadata(retrieved_chunks=1, processing_time=10, stopped=False),
        )


@pytest.mark.api
def test_chat_endpoints_cover_session_streaming_and_regeneration(api_client, auth_headers, seeded_workspace, monkeypatch):
    monkeypatch.setattr("app.api.v1.routes.chat.ChatService", StubChatService)

    create_response = api_client.post(
        "/api/v1/chat/session",
        headers=auth_headers,
        json={"workspace_id": str(seeded_workspace.workspace_id), "title": "API Test", "channel": "web"},
    )
    assert create_response.status_code == 201

    stream_response = api_client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"session_id": str(seeded_workspace.session_id), "message": "How did revenue change?", "mode": "detailed"},
    )
    assert stream_response.status_code == 200
    assert "event: complete" in stream_response.text
    assert "Revenue grew" in stream_response.text

    regenerate_response = api_client.post(
        "/api/v1/chat/regenerate",
        headers=auth_headers,
        json={"session_id": str(seeded_workspace.session_id), "mode": "concise"},
    )
    assert regenerate_response.status_code == 200
    assert regenerate_response.json()["answer"] == "Regenerated answer"


@pytest.mark.api
def test_chat_session_creation_blocks_cross_workspace_access(api_client, auth_headers, seeded_workspace):
    response = api_client.post(
        "/api/v1/chat/session",
        headers=auth_headers,
        json={"workspace_id": str(uuid.uuid4()), "title": "Forbidden", "channel": "web"},
    )
    assert response.status_code in {403, 404}
