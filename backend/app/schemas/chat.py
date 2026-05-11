import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.input_validator import sanitize_prompt_input, sanitize_text
from app.schemas.retrieval import RetrievalFiltersRequest
from app.schemas.lead import LeadCapturePrompt


ChatMode = Literal["concise", "detailed", "bullet"]
ConfidenceLevel = Literal["High", "Medium", "Low"]
FeedbackValue = Literal["up", "down"]


class ChatSessionCreateRequest(BaseModel):
    workspace_id: uuid.UUID
    title: str | None = Field(default=None, max_length=255)
    channel: str = Field(default="web", min_length=2, max_length=50)

    @field_validator("title", mode="before")
    @classmethod
    def sanitize_title(cls, value: str | None) -> str | None:
        return sanitize_text(value, max_length=255)


class ChatSessionSummary(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID | None
    title: str | None
    status: str
    channel: str
    started_at: datetime
    last_message_at: datetime | None
    session_summary: str | None
    needs_human_review: bool = False
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class CitationItem(BaseModel):
    document_id: str | None = None
    file_name: str | None = None
    page_number: int | None = None
    url: str | None = None
    chunk_preview: str


class ChatResponseMetadata(BaseModel):
    retrieved_chunks: int
    processing_time: int
    stopped: bool = False
    session_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    generation_id: str | None = None
    lead_capture: LeadCapturePrompt | None = None
    answer_strategy: str = "rag"
    faq_id: uuid.UUID | None = None


class ChatAnswerResponse(BaseModel):
    answer: str
    citations: list[CitationItem]
    confidence: ConfidenceLevel
    metadata: ChatResponseMetadata


class ChatHistoryMessage(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[CitationItem]
    token_usage: dict | None
    response_time_ms: int | None
    created_at: datetime
    updated_at: datetime


class ChatHistoryResponse(BaseModel):
    session: ChatSessionSummary
    messages: list[ChatHistoryMessage]


class ChatMessageRequest(BaseModel):
    session_id: uuid.UUID
    message: str = Field(min_length=1, max_length=8000)
    mode: ChatMode = "detailed"
    filters: RetrievalFiltersRequest | None = None

    @field_validator("message", mode="before")
    @classmethod
    def sanitize_message(cls, value: str) -> str:
        return sanitize_prompt_input(value).text


class ChatRegenerateRequest(BaseModel):
    session_id: uuid.UUID
    mode: ChatMode = "detailed"
    filters: RetrievalFiltersRequest | None = None


class ChatFeedbackRequest(BaseModel):
    session_id: uuid.UUID
    message_id: uuid.UUID
    value: FeedbackValue
    category: str | None = Field(default=None, max_length=100)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("category", "comment", mode="before")
    @classmethod
    def sanitize_feedback_fields(cls, value: str | None) -> str | None:
        return sanitize_text(value, max_length=1000)


class ChatFeedbackResponse(BaseModel):
    message: str
    feedback_id: uuid.UUID


class StopGenerationRequest(BaseModel):
    session_id: uuid.UUID
    generation_id: str | None = None
