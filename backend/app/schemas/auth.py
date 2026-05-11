import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.input_validator import sanitize_text


class SignupRequest(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    workspace_name: str = Field(min_length=2, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_signup_email(cls, value: str) -> str:
        return (sanitize_text(value, max_length=255) or "").lower()

    @field_validator("full_name", "workspace_name", mode="before")
    @classmethod
    def sanitize_signup_fields(cls, value: str) -> str:
        return sanitize_text(value, max_length=255) or ""


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return (sanitize_text(value, max_length=255) or "").lower()


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = None


class WorkspaceMembershipSummary(BaseModel):
    workspace_id: uuid.UUID
    workspace_name: str
    workspace_slug: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class AuthUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    memberships: list[WorkspaceMembershipSummary]

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    expires_in: int
    user: AuthUserResponse


class MessageResponse(BaseModel):
    message: str
