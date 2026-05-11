from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.auth_security import hash_password
from app.models import User, WorkspaceMember


@pytest.mark.api
def test_workspace_member_management_flow(api_client, auth_headers, db_session, seeded_workspace):
    teammate = User(
        email="teammate@example.com",
        full_name="Teammate User",
        password_hash=hash_password("CorrectHorseBatteryStaple!"),
        is_active=True,
        is_superuser=False,
        session_nonce=uuid.uuid4().hex,
    )
    db_session.add(teammate)
    db_session.commit()

    create_response = api_client.post(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/members",
        headers=auth_headers,
        json={"email": teammate.email, "role": "viewer"},
    )
    assert create_response.status_code == 201
    created_member = create_response.json()
    assert created_member["email"] == teammate.email
    assert created_member["role"] == "viewer"

    list_response = api_client.get(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/members",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    assert any(member["email"] == teammate.email for member in list_response.json())

    update_response = api_client.patch(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/members/{created_member['id']}",
        headers=auth_headers,
        json={"role": "team_member"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["role"] == "team_member"

    delete_response = api_client.delete(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/members/{created_member['id']}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Workspace member removed successfully."


@pytest.mark.api
def test_workspace_member_management_requires_existing_user(api_client, auth_headers, seeded_workspace):
    response = api_client.post(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/members",
        headers=auth_headers,
        json={"email": "missing@example.com", "role": "viewer"},
    )
    assert response.status_code == 404
    assert "sign up" in response.json()["detail"].lower()


@pytest.mark.api
def test_last_admin_cannot_be_demoted_or_removed(api_client, auth_headers, db_session, seeded_workspace):
    owner_membership = db_session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == seeded_workspace.workspace_id,
            WorkspaceMember.user_id == seeded_workspace.user_id,
        )
    )
    assert owner_membership is not None

    demote_response = api_client.patch(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/members/{owner_membership.id}",
        headers=auth_headers,
        json={"role": "viewer"},
    )
    assert demote_response.status_code == 400

    delete_response = api_client.delete(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/members/{owner_membership.id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 400
