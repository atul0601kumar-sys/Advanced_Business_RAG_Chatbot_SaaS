import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ChatSession
from app.schemas.auth import MessageResponse
from app.schemas.chat import ChatFeedbackRequest, ChatFeedbackResponse
from app.schemas.widget import WidgetEventRequest
from app.services.chat_service import ChatService
from app.services.event_tracker import EventTracker
from app.services.widget_auth import WidgetAuthService

router = APIRouter(tags=["widget"])


def _require_widget_session(db: Session, workspace_id: uuid.UUID, session_id: uuid.UUID) -> None:
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id))
    if not session or session.workspace_id != workspace_id or session.channel != "widget":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")


@router.post("/feedback", response_model=ChatFeedbackResponse)
def submit_widget_feedback(
    payload: ChatFeedbackRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ChatFeedbackResponse:
    principal = WidgetAuthService().authenticate(request)
    _require_widget_session(db, principal.workspace_id, payload.session_id)
    return ChatService().submit_feedback(db, None, payload, background_tasks)


@router.post("/widget/event", response_model=MessageResponse)
def track_widget_event(
    payload: WidgetEventRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageResponse:
    principal = WidgetAuthService().authenticate(request)
    if principal.workspace_id != payload.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Widget workspace mismatch.")
    if payload.session_id is not None:
        _require_widget_session(db, payload.workspace_id, payload.session_id)
    EventTracker().track_event(
        db,
        workspace_id=payload.workspace_id,
        session_id=payload.session_id,
        event_type=payload.event,
        metadata={
            **payload.metadata,
            "source": "widget",
        },
    )
    db.commit()
    return MessageResponse(message="Widget event tracked.")
