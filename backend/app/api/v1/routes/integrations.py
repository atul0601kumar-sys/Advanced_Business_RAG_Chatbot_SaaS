import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import User
from app.schemas.integration import (
    IntegrationActionResponse,
    IntegrationConnectRequest,
    IntegrationDisconnectRequest,
    IntegrationListResponse,
    IntegrationTestRequest,
    IntegrationTestResponse,
    IntegrationUpdateRequest,
)
from app.services.integration_manager import IntegrationManager

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/connect", response_model=IntegrationActionResponse)
def connect_integration(
    payload: IntegrationConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntegrationActionResponse:
    return IntegrationManager().connect_integration(db, current_user, payload)


@router.get("/list", response_model=IntegrationListResponse)
def list_integrations(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntegrationListResponse:
    return IntegrationManager().list_integrations(db, current_user, workspace_id)


@router.put("/update", response_model=IntegrationActionResponse)
def update_integration(
    payload: IntegrationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntegrationActionResponse:
    return IntegrationManager().update_integration(db, current_user, payload)


@router.delete("/disconnect", response_model=IntegrationActionResponse)
def disconnect_integration(
    payload: IntegrationDisconnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntegrationActionResponse:
    return IntegrationManager().disconnect_integration(db, current_user, payload)


@router.post("/test", response_model=IntegrationTestResponse)
def test_integration(
    payload: IntegrationTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntegrationTestResponse:
    return IntegrationManager().test_integration(db, current_user, payload)
