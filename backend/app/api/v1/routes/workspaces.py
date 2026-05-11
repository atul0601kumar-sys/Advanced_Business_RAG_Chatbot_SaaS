import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import ALLOWED_ROLES, ROLE_ADMIN
from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_workspace_role
from app.models import User, Workspace, WorkspaceMember
from app.schemas.auth import MessageResponse
from app.schemas.workspace import (
    WorkspaceMemberCreateRequest,
    WorkspaceMemberRoleUpdateRequest,
    WorkspaceMemberSummary,
    WorkspaceSummary,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _serialize_member(membership: WorkspaceMember) -> WorkspaceMemberSummary:
    return WorkspaceMemberSummary(
        id=membership.id,
        user_id=membership.user.id,
        full_name=membership.user.full_name,
        email=membership.user.email,
        role=membership.role,
    )


def _validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid workspace role.")
    return normalized


def _count_admins(db: Session, workspace_id: uuid.UUID) -> int:
    return len(
        db.scalars(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == ROLE_ADMIN,
            )
        ).all()
    )


@router.get("", response_model=list[WorkspaceSummary])
def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceSummary]:
    memberships = db.scalars(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.workspace))
        .where(WorkspaceMember.user_id == current_user.id)
        .order_by(WorkspaceMember.joined_at.asc())
    ).all()
    return [
        WorkspaceSummary(
            id=membership.workspace.id,
            name=membership.workspace.name,
            slug=membership.workspace.slug,
            description=membership.workspace.description,
            status=membership.workspace.status,
            role=membership.role,
            created_at=membership.workspace.created_at,
        )
        for membership in memberships
        if membership.workspace is not None
    ]


@router.get("/{workspace_id}", response_model=WorkspaceSummary)
def get_workspace(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(
        require_workspace_role("admin", "team_member", "viewer")
    ),
    db: Session = Depends(get_db),
) -> WorkspaceSummary:
    workspace = db.get(Workspace, workspace_id)
    return WorkspaceSummary(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        description=workspace.description,
        status=workspace.status,
        role=membership.role,
        created_at=workspace.created_at,
    )


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberSummary])
def get_workspace_members(
    workspace_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member", "viewer")),
    db: Session = Depends(get_db),
) -> list[WorkspaceMemberSummary]:
    memberships = db.scalars(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.joined_at.asc())
    ).all()
    return [
        _serialize_member(membership)
        for membership in memberships
        if membership.user is not None
    ]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberSummary,
    status_code=status.HTTP_201_CREATED,
)
def add_workspace_member(
    workspace_id: uuid.UUID,
    payload: WorkspaceMemberCreateRequest,
    _: WorkspaceMember = Depends(require_workspace_role("admin")),
    db: Session = Depends(get_db),
) -> WorkspaceMemberSummary:
    role = _validate_role(payload.role)
    normalized_email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Ask them to sign up before adding them to this workspace.",
        )

    existing_membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if existing_membership:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a workspace member.")

    membership = WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=role)
    db.add(membership)
    db.commit()
    membership = db.scalar(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(WorkspaceMember.id == membership.id)
    )
    if not membership or membership.user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add workspace member.")
    return _serialize_member(membership)


@router.patch("/{workspace_id}/members/{member_id}", response_model=WorkspaceMemberSummary)
def update_workspace_member_role(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: WorkspaceMemberRoleUpdateRequest,
    _: WorkspaceMember = Depends(require_workspace_role("admin")),
    db: Session = Depends(get_db),
) -> WorkspaceMemberSummary:
    membership = db.scalar(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(WorkspaceMember.id == member_id, WorkspaceMember.workspace_id == workspace_id)
    )
    if not membership or membership.user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace member not found.")

    role = _validate_role(payload.role)
    if membership.role == ROLE_ADMIN and role != ROLE_ADMIN and _count_admins(db, workspace_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one admin must remain in the workspace.",
        )

    membership.role = role
    db.commit()
    db.refresh(membership)
    return _serialize_member(membership)


@router.delete("/{workspace_id}/members/{member_id}", response_model=MessageResponse)
def remove_workspace_member(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace member not found.")
    if membership.role == ROLE_ADMIN and _count_admins(db, workspace_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one admin must remain in the workspace.",
        )

    db.delete(membership)
    db.commit()
    return MessageResponse(message="Workspace member removed successfully.")
