import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_optional_current_user
from app.schemas.voice import (
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
    VoiceTranscriptionRequest,
    VoiceTranscriptionResponse,
)
from app.services.voice_service import VoiceService
from app.services.widget_auth import WidgetAuthService

router = APIRouter(prefix="/voice", tags=["voice"])


def _resolve_voice_actor(request: Request, db: Session, workspace_id: uuid.UUID):
    current_user = get_optional_current_user(request, db)
    if current_user is not None:
        return current_user
    principal = WidgetAuthService().authenticate(request)
    if principal.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Widget workspace mismatch.")
    return None


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
def transcribe_audio(
    payload: VoiceTranscriptionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> VoiceTranscriptionResponse:
    current_user = _resolve_voice_actor(request, db, payload.workspace_id)
    return VoiceService().transcribe(
        db,
        current_user=current_user,
        workspace_id=payload.workspace_id,
        payload=payload,
    )


@router.post("/synthesize", response_model=VoiceSynthesisResponse)
def synthesize_audio(
    payload: VoiceSynthesisRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> VoiceSynthesisResponse:
    current_user = _resolve_voice_actor(request, db, payload.workspace_id)
    return VoiceService().synthesize(
        db,
        current_user=current_user,
        workspace_id=payload.workspace_id,
        payload=payload,
    )
