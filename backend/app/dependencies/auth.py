import uuid
from collections.abc import Iterable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.access_control import (
    ensure_workspace_exists,
    ensure_workspace_role,
    extract_bearer_token,
    get_workspace_member as load_workspace_member,
)
from app.core.auth_security import decode_access_token, validate_token_binding
from app.db.session import get_db
from app.models import User, WorkspaceMember


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")
    user = db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not available.")
    validate_token_binding(payload, user, request)
    request.state.auth_user_id = user.id
    return user


def get_optional_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = extract_bearer_token(request)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        return None
    try:
        validate_token_binding(payload, user, request)
    except HTTPException:
        return None
    request.state.auth_user_id = user.id
    return user


def get_workspace_member(
    workspace_id: uuid.UUID,
    current_user: User,
    db: Session,
) -> WorkspaceMember:
    return load_workspace_member(workspace_id, current_user, db)


def require_workspace_role(*allowed_roles: str):
    allowed: set[str] = set(allowed_roles)

    def dependency(
        workspace_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> WorkspaceMember:
        ensure_workspace_exists(db, workspace_id)
        return ensure_workspace_role(workspace_id, current_user, db, *allowed)

    return dependency


def has_any_role(role: str, accepted_roles: Iterable[str]) -> bool:
    return role in set(accepted_roles)
