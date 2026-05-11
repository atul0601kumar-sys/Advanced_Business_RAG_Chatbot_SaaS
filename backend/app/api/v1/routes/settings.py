import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import User
from app.schemas.auth import MessageResponse
from app.schemas.settings import ChatbotSettingsResponse, ChatbotSettingsUpdateRequest, PublicChatbotSettingsResponse
from app.services.settings_service import SettingsService
from app.services.widget_auth import WidgetAuthService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=ChatbotSettingsResponse)
def get_settings(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatbotSettingsResponse:
    return SettingsService().get_settings(db, current_user, workspace_id)


@router.put("/update", response_model=ChatbotSettingsResponse)
def update_settings(
    payload: ChatbotSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatbotSettingsResponse:
    return SettingsService().update_settings(db, current_user, payload)


@router.post("/reset-default", response_model=ChatbotSettingsResponse)
def reset_settings_to_default(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatbotSettingsResponse:
    return SettingsService().reset_defaults(db, current_user, workspace_id)


@router.get("/public", response_model=PublicChatbotSettingsResponse)
def get_public_settings(
    workspace_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> PublicChatbotSettingsResponse:
    origin = WidgetAuthService().extract_request_origin(request)
    return SettingsService().get_public_settings(db, workspace_id, origin=origin)
