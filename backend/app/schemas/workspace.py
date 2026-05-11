import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    status: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberSummary(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberCreateRequest(BaseModel):
    email: str
    role: str = Field(min_length=3, max_length=50)


class WorkspaceMemberRoleUpdateRequest(BaseModel):
    role: str = Field(min_length=3, max_length=50)
