import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limiter import enforce_rate_limit
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_optional_current_user
from app.models import ChatSession, User
from app.schemas.auth import MessageResponse
from app.schemas.chat import (
    ChatAnswerResponse,
    ChatFeedbackRequest,
    ChatFeedbackResponse,
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatRegenerateRequest,
    ChatSessionCreateRequest,
    ChatSessionSummary,
    StopGenerationRequest,
)
from app.services.chat_service import ChatService
from app.services.widget_auth import WidgetAuthService

router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()


def _resolve_chat_actor(
    request: Request,
    db: Session,
    *,
    workspace_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
) -> User | None:
    current_user = get_optional_current_user(request, db)
    if current_user is not None:
        return current_user

    principal = WidgetAuthService().authenticate(request)
    if workspace_id is not None and principal.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Widget workspace mismatch.")
    if session_id is not None:
        session = db.scalar(select(ChatSession).where(ChatSession.id == session_id))
        if not session or session.workspace_id != principal.workspace_id or session.channel != "widget":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    return None


@router.post("/session", response_model=ChatSessionSummary, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    payload: ChatSessionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ChatSessionSummary:
    service = ChatService()
    current_user = _resolve_chat_actor(request, db, workspace_id=payload.workspace_id)
    if current_user is None:
        payload = payload.model_copy(update={"channel": "widget"})
    return service.create_session(db, current_user, payload)


@router.get("/sessions", response_model=list[ChatSessionSummary])
def list_chat_sessions(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSessionSummary]:
    service = ChatService()
    return service.list_sessions(db, current_user, workspace_id)


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
def get_chat_history(
    session_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> ChatHistoryResponse:
    service = ChatService()
    current_user = _resolve_chat_actor(request, db, session_id=session_id)
    return service.get_history(db, current_user, session_id)


@router.post("/message")
async def send_chat_message(
    payload: ChatMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    enforce_rate_limit(
        request,
        scope="chat",
        limit=settings.chat_rate_limit_count,
        window_seconds=settings.chat_rate_limit_window_seconds,
    )
    service = ChatService()
    current_user = _resolve_chat_actor(request, db, session_id=payload.session_id)
    return StreamingResponse(
        service.stream_message(db, current_user, payload, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/regenerate", response_model=ChatAnswerResponse)
async def regenerate_chat_response(
    payload: ChatRegenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ChatAnswerResponse:
    service = ChatService()
    current_user = _resolve_chat_actor(request, db, session_id=payload.session_id)
    return await service.regenerate_last_response(db, current_user, payload)


@router.post("/feedback", response_model=ChatFeedbackResponse)
def submit_chat_feedback(
    payload: ChatFeedbackRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> ChatFeedbackResponse:
    service = ChatService()
    current_user = _resolve_chat_actor(request, db, session_id=payload.session_id)
    return service.submit_feedback(db, current_user, payload, background_tasks)


@router.post("/stop", response_model=MessageResponse)
def stop_chat_generation(
    payload: StopGenerationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageResponse:
    service = ChatService()
    current_user = _resolve_chat_actor(request, db, session_id=payload.session_id)
    stopped = service.stop_generation(db, current_user, payload)
    if stopped:
        return MessageResponse(message="Generation stop signal sent.")
    return MessageResponse(message="No active generation was found for that session.")
