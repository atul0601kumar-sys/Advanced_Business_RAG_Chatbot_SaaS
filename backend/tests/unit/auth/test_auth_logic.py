from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.access_control import ensure_workspace_role, normalize_workspace_role
from app.core.auth_security import decode_access_token, validate_token_binding
from app.dependencies.auth import has_any_role
from app.models import User, WorkspaceMember
from app.services.auth import authenticate_user, build_auth_response, signup_user, slugify_workspace_name
from app.schemas.auth import SignupRequest


def test_signup_creates_workspace_and_membership(db_session, request_factory):
    created = signup_user(
        db_session,
        SignupRequest(
            email="new.user@example.com",
            full_name="New User",
            password="CorrectHorseBatteryStaple!",
            workspace_name="Revenue Ops HQ",
        ),
    )
    assert created.email == "new.user@example.com"
    assert created.workspace_memberships[0].role == "admin"
    assert created.workspace_memberships[0].workspace.slug.startswith("revenue-ops-hq")


def test_authenticate_user_resets_lockout_and_issues_bound_token(db_session, seeded_workspace, request_factory):
    request = request_factory(headers={"User-Agent": "pytest-client"})
    user = authenticate_user(db_session, "owner@example.com", "CorrectHorseBatteryStaple!", request)
    _, token_bundle = build_auth_response(user, request)
    payload = decode_access_token(token_bundle.access_token)
    validate_token_binding(payload, user, request)
    assert payload["sub"] == str(user.id)


def test_workspace_role_checks_enforce_rbac(db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None
    membership = ensure_workspace_role(seeded_workspace.workspace_id, user, db_session, "admin")
    assert isinstance(membership, WorkspaceMember)
    with pytest.raises(HTTPException):
        ensure_workspace_role(seeded_workspace.other_workspace_id, user, db_session, "admin")


def test_role_helpers_normalize_and_match():
    assert normalize_workspace_role("admin") == "admin"
    assert normalize_workspace_role("unknown") == "viewer"
    assert has_any_role("team_member", {"viewer", "team_member"}) is True


def test_slugify_workspace_name_generates_safe_slug():
    assert slugify_workspace_name("Revenue Ops / North America") == "revenue-ops-north-america"
