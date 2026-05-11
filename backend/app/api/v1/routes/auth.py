from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.audit_logger import AuditAction, shared_audit_logger
from app.core.rate_limiter import enforce_rate_limit
from app.core.config import get_settings
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_optional_current_user
from app.models import User
from app.schemas.auth import AuthResponse, AuthUserResponse, LoginRequest, MessageResponse, RefreshTokenRequest, SignupRequest
from app.services.auth import (
    authenticate_user,
    build_auth_response,
    clear_auth_cookie,
    load_user_with_memberships,
    refresh_user_session,
    serialize_user,
    set_auth_cookies,
    signup_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    user = signup_user(db, payload)
    auth_response, bundle = build_auth_response(user, request)
    set_auth_cookies(response, bundle)
    return auth_response


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    enforce_rate_limit(
        request,
        scope="login",
        limit=settings.login_rate_limit_count,
        window_seconds=settings.login_rate_limit_window_seconds,
    )
    user = authenticate_user(db, payload.email, payload.password, request)
    auth_response, bundle = build_auth_response(user, request)
    set_auth_cookies(response, bundle)
    return auth_response


@router.post("/refresh", response_model=AuthResponse)
def refresh_access_token(
    payload: RefreshTokenRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = refresh_user_session(db, request, payload)
    auth_response, bundle = build_auth_response(user, request)
    set_auth_cookies(response, bundle)
    shared_audit_logger.log(db, action=AuditAction.TOKEN_REFRESHED, request=request, user_id=user.id)
    db.commit()
    return auth_response


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if current_user is None:
        try:
            current_user = refresh_user_session(db, request, RefreshTokenRequest())
        except HTTPException:
            current_user = None
    if current_user is not None:
        from app.core.auth_security import rotate_session_binding

        rotate_session_binding(current_user)
        shared_audit_logger.log(db, action=AuditAction.LOGOUT, request=request, user_id=current_user.id)
        db.commit()
    clear_auth_cookie(response)
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=AuthUserResponse)
def current_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthUserResponse:
    hydrated_user = load_user_with_memberships(db, current_user.id)
    return serialize_user(hydrated_user)
