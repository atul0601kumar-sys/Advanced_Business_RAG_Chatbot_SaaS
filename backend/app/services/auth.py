import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import ROLE_ADMIN, ROLE_TEAM_MEMBER, ROLE_VIEWER, get_client_ip
from app.core.audit_logger import AuditAction, shared_audit_logger
from app.core.config import get_settings
from app.core.auth_security import (
    AuthTokenBundle,
    clear_auth_cookies,
    decode_signed_token,
    hash_password,
    issue_auth_tokens,
    rotate_session_binding,
    set_auth_cookies,
    validate_token_binding,
    verify_password,
)
from app.core.input_validator import sanitize_text
from app.models import User, Workspace, WorkspaceMember
from app.schemas.auth import AuthResponse, AuthUserResponse, RefreshTokenRequest, SignupRequest, WorkspaceMembershipSummary

settings = get_settings()

ALLOWED_ROLES = {ROLE_ADMIN, ROLE_TEAM_MEMBER, ROLE_VIEWER}


def slugify_workspace_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"workspace-{uuid.uuid4().hex[:8]}"


def serialize_user(user: User) -> AuthUserResponse:
    memberships = [
        WorkspaceMembershipSummary(
            workspace_id=membership.workspace.id,
            workspace_name=membership.workspace.name,
            workspace_slug=membership.workspace.slug,
            role=membership.role,
        )
        for membership in user.workspace_memberships
        if membership.workspace is not None
    ]
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        memberships=memberships,
    )


def load_user_with_memberships(db: Session, user_id: uuid.UUID) -> User | None:
    return db.scalar(
        select(User)
        .options(selectinload(User.workspace_memberships).selectinload(WorkspaceMember.workspace))
        .where(User.id == user_id)
    )


def set_auth_cookie(response: Response, token: str) -> None:
    raise NotImplementedError("Use set_auth_cookies with a full token bundle.")


def clear_auth_cookie(response: Response) -> None:
    clear_auth_cookies(response)


def _normalize_email(email: str) -> str:
    return (sanitize_text(email, max_length=255) or "").lower()


def _log_auth_event(
    db: Session,
    request: Request,
    *,
    action: str,
    user: User | None = None,
    metadata: dict | None = None,
) -> None:
    shared_audit_logger.log(
        db,
        action=action,
        request=request,
        user_id=user.id if user else None,
        metadata=metadata,
    )


def authenticate_user(db: Session, email: str, password: str, request: Request) -> User:
    user = db.scalar(
        select(User)
        .options(selectinload(User.workspace_memberships).selectinload(WorkspaceMember.workspace))
        .where(User.email == _normalize_email(email))
    )
    now = datetime.now(UTC)
    if user and user.account_locked_until and user.account_locked_until > now:
        _log_auth_event(db, request, action=AuditAction.ACCOUNT_LOCKED, user=user)
        db.commit()
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account is temporarily locked.")
    if not user or not verify_password(password, user.password_hash):
        if user is None:
            _log_auth_event(db, request, action=AuditAction.LOGIN_FAILURE, metadata={"email": _normalize_email(email)})
            db.commit()
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.max_login_failures:
                user.account_locked_until = now + timedelta(minutes=settings.account_lock_minutes)
                _log_auth_event(db, request, action=AuditAction.ACCOUNT_LOCKED, user=user)
            _log_auth_event(
                db,
                request,
                action=AuditAction.LOGIN_FAILURE,
                user=user,
                metadata={"attempts": user.failed_login_attempts},
            )
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")
    user.failed_login_attempts = 0
    user.account_locked_until = None
    user.last_login_at = now
    user.last_login_ip = get_client_ip(request)
    rotate_session_binding(user)
    _log_auth_event(db, request, action=AuditAction.LOGIN_SUCCESS, user=user)
    db.commit()
    db.refresh(user)
    return user


def signup_user(db: Session, payload: SignupRequest) -> User:
    existing_user = db.scalar(select(User).where(User.email == _normalize_email(payload.email)))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")

    base_slug = slugify_workspace_name(payload.workspace_name)
    candidate_slug = base_slug
    counter = 1
    while db.scalar(select(Workspace).where(Workspace.slug == candidate_slug)):
        counter += 1
        candidate_slug = f"{base_slug}-{counter}"

    user = User(
        email=_normalize_email(payload.email),
        full_name=sanitize_text(payload.full_name, max_length=255) or payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
        is_superuser=False,
        session_nonce=uuid.uuid4().hex,
    )
    db.add(user)
    db.flush()

    workspace = Workspace(
        name=sanitize_text(payload.workspace_name, max_length=255) or payload.workspace_name,
        slug=candidate_slug,
        description="Default workspace created during signup.",
        status="active",
        owner_user_id=user.id,
    )
    db.add(workspace)
    db.flush()

    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=ROLE_ADMIN,
    )
    db.add(membership)
    db.commit()

    created_user = load_user_with_memberships(db, user.id)
    if not created_user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user.")
    return created_user


def refresh_user_session(
    db: Session,
    request: Request,
    payload: RefreshTokenRequest,
) -> User:
    token = payload.refresh_token or request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is required.")
    claims = decode_signed_token(token, expected_type="refresh")
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token subject.")
    user = load_user_with_memberships(db, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not available.")
    if user.account_locked_until and user.account_locked_until > datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account is temporarily locked.")
    validate_token_binding(claims, user, request)
    return user


def build_auth_response(user: User, request: Request) -> tuple[AuthResponse, AuthTokenBundle]:
    tokens = issue_auth_tokens(user, request)
    return (
        AuthResponse(
            expires_in=tokens.expires_in,
            user=serialize_user(user),
        ),
        tokens,
    )
