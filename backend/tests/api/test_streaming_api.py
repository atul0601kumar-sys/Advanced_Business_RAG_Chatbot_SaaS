from __future__ import annotations

import json

import pytest


class OrderedStreamingService:
    async def stream_message(self, db, current_user, payload, request):  # noqa: ARG002
        yield 'event: start\ndata: {"session_id":"%s","generation_id":"gen-ordered","message_id":"msg-ordered"}\n\n' % payload.session_id
        yield 'event: token\ndata: {"delta":"Revenue "}\n\n'
        yield 'event: token\ndata: {"delta":"grew "}\n\n'
        yield 'event: token\ndata: {"delta":"18 percent."}\n\n'
        yield 'event: complete\ndata: {"answer":"Revenue grew 18 percent.","citations":[],"confidence":"High","metadata":{"retrieved_chunks":1,"processing_time":3,"stopped":false,"generation_id":"gen-ordered"}}\n\n'

    def stop_generation(self, db, current_user, payload):  # noqa: ARG002
        return bool(payload.generation_id)


@pytest.mark.api
def test_streaming_response_preserves_chunk_order_and_termination(api_client, auth_headers, seeded_workspace, monkeypatch):
    monkeypatch.setattr("app.api.v1.routes.chat.ChatService", OrderedStreamingService)

    response = api_client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"session_id": str(seeded_workspace.session_id), "message": "Revenue?", "mode": "concise"},
    )
    assert response.status_code == 200

    frames = [frame for frame in response.text.split("\n\n") if frame.strip()]
    token_deltas = []
    for frame in frames:
        event_line, data_line = frame.split("\n")
        event_name = event_line.replace("event: ", "")
        payload = json.loads(data_line.replace("data: ", ""))
        if event_name == "token":
            token_deltas.append(payload["delta"])
    assert token_deltas == ["Revenue ", "grew ", "18 percent."]
    assert frames[-1].startswith("event: complete")


@pytest.mark.api
def test_stop_generation_endpoint_reports_success(api_client, auth_headers, seeded_workspace, monkeypatch):
    monkeypatch.setattr("app.api.v1.routes.chat.ChatService", OrderedStreamingService)
    response = api_client.post(
        "/api/v1/chat/stop",
        headers=auth_headers,
        json={"session_id": str(seeded_workspace.session_id), "generation_id": "gen-ordered"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Generation stop signal sent."
