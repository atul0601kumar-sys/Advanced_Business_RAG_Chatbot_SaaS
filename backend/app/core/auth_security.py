from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.audit_logger import AuditAction, flag_suspicious_request
from app.core.config import get_settings
from app.core.input_validator import sanitize_text

settings = get_settings()

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerifyMismatchError
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    PasswordHasher = None
    InvalidHashError = VerifyMismatchError = Exception

_argon2_hasher = PasswordHasher() if PasswordHasher is not None else None


@dataclass(frozen=True)
class AuthTokenBundle:
    access_token: str
    refresh_token: str
    csrf_token: str
    expires_in: int


def hash_password(password: str) -> str:
    password_value = sanitize_text(password, max_length=256) or ""
    if _argon2_hasher is not None:
        return _argon2_hasher.hash(password_value)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password_value.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    password_value = sanitize_text(password, max_length=256) or ""
    if password_hash.startswith("$argon2") and _argon2_hasher is not None:
        try:
            return bool(_argon2_hasher.verify(password_hash, password_value))
        except (VerifyMismatchError, InvalidHashError):
            return False
    if password_hash.startswith("scrypt$"):
        try:
            _, salt_b64, digest_b64 = password_hash.split("$", 2)
        except ValueError:
            return False
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        expected = base64.b64decode(digest_b64.encode("utf-8"))
        actual = hashlib.scrypt(password_value.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(expected, actual)
    return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _client_fingerprint(request: Request) -> str:
    user_agent = request.headers.get("User-Agent", "").strip()
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()


def create_signed_token(payload: dict[str, Any], *, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    signed_payload = {
        **payload,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": secrets.token_hex(16),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(signed_payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(settings.jwt_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_segment}.{payload_segment}.{_b64url_encode(signature)}"


def decode_signed_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = hmac.new(settings.jwt_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_signature, _b64url_decode(signature_segment)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature.")
    payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    if payload.get("iss") != settings.jwt_issuer or payload.get("aud") != settings.jwt_audience:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience.")
    if expected_type and payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")
    if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    return payload


def create_access_token(subject: str, *, session_nonce: str, token_version: int, request: Request) -> tuple[str, str]:
    csrf_token = secrets.token_urlsafe(24)
    token = create_signed_token(
        {
            "sub": subject,
            "type": "access",
            "sid": session_nonce,
            "ver": token_version,
            "fp": _client_fingerprint(request),
            "csrf": csrf_token,
        },
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    return token, csrf_token


def create_refresh_token(subject: str, *, session_nonce: str, token_version: int, request: Request) -> str:
    return create_signed_token(
        {
            "sub": subject,
            "type": "refresh",
            "sid": session_nonce,
            "ver": token_version,
            "fp": _client_fingerprint(request),
        },
        expires_delta=timedelta(minutes=settings.jwt_refresh_token_expire_minutes),
    )


def decode_access_token(token: str) -> dict[str, Any]:
    return decode_signed_token(token, expected_type="access")


def issue_auth_tokens(user, request: Request) -> AuthTokenBundle:  # noqa: ANN001
    access_token, csrf_token = create_access_token(
        str(user.id),
        session_nonce=user.session_nonce,
        token_version=user.token_version,
        request=request,
    )
    refresh_token = create_refresh_token(
        str(user.id),
        session_nonce=user.session_nonce,
        token_version=user.token_version,
        request=request,
    )
    return AuthTokenBundle(
        access_token=access_token,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


def validate_token_binding(payload: dict[str, Any], user, request: Request) -> None:  # noqa: ANN001
    if payload.get("sid") != user.session_nonce or int(payload.get("ver", -1)) != int(user.token_version):
        flag_suspicious_request(request, action=AuditAction.SUSPICIOUS_REQUEST, metadata={"reason": "stale_session"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer valid.")
    if payload.get("fp") != _client_fingerprint(request):
        flag_suspicious_request(request, action=AuditAction.SUSPICIOUS_REQUEST, metadata={"reason": "fingerprint_mismatch"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session verification failed.")


def rotate_session_binding(user) -> None:  # noqa: ANN001
    user.session_nonce = secrets.token_hex(24)
    user.token_version = int(user.token_version or 0) + 1


def set_auth_cookies(response: Response, bundle: AuthTokenBundle) -> None:
    secure_cookie = settings.app_env != "development"
    cookie_kwargs = {
        "secure": secure_cookie,
        "samesite": settings.secure_cookie_samesite,
        "path": "/",
    }
    response.set_cookie(
        key="access_token",
        value=bundle.access_token,
        httponly=True,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        **cookie_kwargs,
    )
    response.set_cookie(
        key="refresh_token",
        value=bundle.refresh_token,
        httponly=True,
        max_age=settings.jwt_refresh_token_expire_minutes * 60,
        **cookie_kwargs,
    )
    response.set_cookie(
        key="csrf_token",
        value=bundle.csrf_token,
        httponly=False,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        **cookie_kwargs,
    )


def clear_auth_cookies(response: Response) -> None:
    for key in ("access_token", "refresh_token", "csrf_token"):
        response.delete_cookie(key=key, path="/")


class CSRFMiddleware(BaseHTTPMiddleware):
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/signup",
        "/api/v1/health",
    }

    async def dispatch(self, request: Request, call_next):
        if request.method not in self.SAFE_METHODS and request.url.path not in self.EXEMPT_PATHS:
            using_cookie_auth = "access_token" in request.cookies and not request.headers.get("Authorization")
            if using_cookie_auth:
                csrf_cookie = request.cookies.get("csrf_token")
                csrf_header = request.headers.get("X-CSRF-Token")
                if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
                    flag_suspicious_request(
                        request,
                        action=AuditAction.SUSPICIOUS_REQUEST,
                        metadata={"reason": "csrf_validation_failed"},
                    )
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "CSRF validation failed."},
                    )
        return await call_next(request)
