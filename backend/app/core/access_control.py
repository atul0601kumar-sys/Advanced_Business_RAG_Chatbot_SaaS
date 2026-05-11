from __future__ import annotations

import uuid
from collections.abc import Iterable

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember

ROLE_ADMIN = "admin"
ROLE_TEAM_MEMBER = "team_member"
ROLE_VIEWER = "viewer"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_TEAM_MEMBER, ROLE_VIEWER}
WORKSPACE_ROLE_PRIORITY = {
    ROLE_VIEWER: 1,
    ROLE_TEAM_MEMBER: 2,
    ROLE_ADMIN: 3,
}


def extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()
    return request.cookies.get("access_token")


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:64]
    if request.client is None:
        return None
    return (request.client.host or "")[:64] or None


def normalize_workspace_role(role: str | None) -> str:
    if role in ALLOWED_ROLES:
        return role
    return ROLE_VIEWER


def get_workspace_member(
    workspace_id: uuid.UUID,
    current_user: User,
    db: Session,
) -> WorkspaceMember:
    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access denied.")
    return membership


def ensure_workspace_exists(db: Session, workspace_id: uuid.UUID) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return workspace


def ensure_workspace_role(
    workspace_id: uuid.UUID,
    current_user: User,
    db: Session,
    *allowed_roles: str,
) -> WorkspaceMember:
    ensure_workspace_exists(db, workspace_id)
    membership = get_workspace_member(workspace_id, current_user, db)
    normalized_role = normalize_workspace_role(membership.role)
    if normalized_role not in set(allowed_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
    return membership


def has_any_role(role: str, accepted_roles: Iterable[str]) -> bool:
    return normalize_workspace_role(role) in {normalize_workspace_role(item) for item in accepted_roles}
