from __future__ import annotations

import pytest


@pytest.mark.api
def test_signup_login_and_protected_route_flow(api_client):
    signup_response = api_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "signup@example.com",
            "full_name": "Signup User",
            "password": "CorrectHorseBatteryStaple!",
            "workspace_name": "Growth Workspace",
        },
    )
    assert signup_response.status_code == 201
    body = signup_response.json()
    assert body["user"]["email"] == "signup@example.com"
    assert body["user"]["memberships"][0]["role"] == "admin"
    assert "access_token" not in body
    assert "csrf_token" not in body
    assert signup_response.cookies.get("access_token")
    assert signup_response.cookies.get("refresh_token")
    assert signup_response.cookies.get("csrf_token")

    login_response = api_client.post(
        "/api/v1/auth/login",
        json={"email": "signup@example.com", "password": "CorrectHorseBatteryStaple!"},
        headers={"User-Agent": "pytest-client"},
    )
    assert login_response.status_code == 200
    assert "access_token" not in login_response.json()
    assert login_response.cookies.get("access_token")

    me_response = api_client.get(
        "/api/v1/auth/me",
        headers={"User-Agent": "pytest-client"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "signup@example.com"


@pytest.mark.api
def test_protected_route_blocks_unauthorized_requests(api_client):
    response = api_client.get("/api/v1/workspaces")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."
