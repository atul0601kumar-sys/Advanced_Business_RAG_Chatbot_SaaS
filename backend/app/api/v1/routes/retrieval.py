import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import require_workspace_role
from app.models import WorkspaceMember
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/workspaces/{workspace_id}/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
async def search_retrieval(
    workspace_id: uuid.UUID,
    payload: RetrievalRequest,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member", "viewer")),
    db: Session = Depends(get_db),
) -> RetrievalResponse:
    service = RetrievalService()
    return await service.retrieve(db, workspace_id, payload.query, payload.filters)
