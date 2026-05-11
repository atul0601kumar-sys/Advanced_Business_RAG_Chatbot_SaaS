from __future__ import annotations

import uuid

import pytest

from app.models import Lead
from tests.fixtures.sample_content import SAMPLE_LEAD


@pytest.mark.api
def test_leads_create_and_list(api_client, auth_headers, db_session, seeded_workspace):
    create_response = api_client.post(
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
    assert create_response.status_code == 200
    lead_id = create_response.json()["lead"]["id"]
    assert db_session.get(Lead, uuid.UUID(lead_id)) is not None

    list_response = api_client.get(
        f"/api/v1/leads?workspace_id={seeded_workspace.workspace_id}",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["email"] == SAMPLE_LEAD["email"]


@pytest.mark.api
def test_analytics_overview_returns_workspace_data(api_client, auth_headers, seeded_workspace):
    response = api_client.get(
        f"/api/v1/analytics/overview?workspace_id={seeded_workspace.workspace_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["total_chats"] >= 1
    assert payload["metrics"]["total_users"] >= 1
    assert "generated_at" in payload
