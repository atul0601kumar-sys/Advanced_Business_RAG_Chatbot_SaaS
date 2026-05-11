import uuid
from typing import Literal

from pydantic import BaseModel, Field


VoiceInputProviderOption = Literal["browser", "backend"]
VoiceOutputProviderOption = Literal["browser", "backend"]


class VoiceTranscriptionRequest(BaseModel):
    workspace_id: uuid.UUID
    audio_base64: str = Field(min_length=1)
    mime_type: str = Field(min_length=3, max_length=100)
    language: str | None = Field(default=None, max_length=20)


class VoiceTranscriptionResponse(BaseModel):
    transcript: str
    provider: str


class VoiceSynthesisRequest(BaseModel):
    workspace_id: uuid.UUID
    text: str = Field(min_length=1, max_length=12000)
    voice_style: str | None = Field(default=None, max_length=100)
    format: str = Field(default="mp3", max_length=20)


class VoiceSynthesisResponse(BaseModel):
    audio_base64: str
    mime_type: str
    provider: str
