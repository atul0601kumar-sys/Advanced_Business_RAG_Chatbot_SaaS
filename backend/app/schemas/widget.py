import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


WidgetEventName = Literal["widget_opened", "message_sent", "lead_submitted"]


class WidgetEmbedMetadata(BaseModel):
    auth_token: str
    auth_expires_at: datetime
    api_base_url: str
    script_url: str
    version: str
    allowed_origins: list[str] = Field(default_factory=list)


class WidgetEventRequest(BaseModel):
    workspace_id: uuid.UUID
    session_id: uuid.UUID | None = None
    event: WidgetEventName
    metadata: dict[str, Any] = Field(default_factory=dict)

