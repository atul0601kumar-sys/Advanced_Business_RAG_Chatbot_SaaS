import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_workspace_role
from app.models import User, WorkspaceMember
from app.schemas.auth import MessageResponse
from app.schemas.website_source import (
    WebsiteSourceActionResponse,
    WebsiteSourceCommandRequest,
    WebsiteSourceCreateRequest,
    WebsiteSourceQueueRequest,
    WebsiteSourceSummary,
)
from app.services.website_sources import (
    create_website_source,
    delete_website_source,
    get_website_source_or_404,
    list_website_sources,
    mark_website_source_for_reindex,
    queue_existing_website_source,
    queue_website_source_indexing,
    serialize_website_source,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/website-sources", tags=["website-sources"])
website_router = APIRouter(prefix="/website", tags=["website"])


@router.get("", response_model=list[WebsiteSourceSummary])
def get_website_sources(
    workspace_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member", "viewer")),
    db: Session = Depends(get_db),
) -> list[WebsiteSourceSummary]:
    return list_website_sources(db, workspace_id)


@router.post("", response_model=WebsiteSourceActionResponse, status_code=status.HTTP_201_CREATED)
def add_website_source(
    workspace_id: uuid.UUID,
    payload: WebsiteSourceCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> WebsiteSourceActionResponse:
    source = create_website_source(
        db,
        workspace_id,
        current_user,
        url=payload.url,
        domain_root=payload.domain_root,
        max_depth=payload.max_depth,
        max_pages=payload.max_pages,
    )
    queue_website_source_indexing(background_tasks, source.id)
    return WebsiteSourceActionResponse(message="Website source added and queued for crawling.", source=source)


@router.get("/{source_id}", response_model=WebsiteSourceSummary)
def get_website_source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member", "viewer")),
    db: Session = Depends(get_db),
) -> WebsiteSourceSummary:
    return serialize_website_source(get_website_source_or_404(db, workspace_id, source_id))


@router.post("/{source_id}/reindex", response_model=WebsiteSourceActionResponse)
def reindex_website_source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> WebsiteSourceActionResponse:
    source = mark_website_source_for_reindex(db, workspace_id, source_id)
    queue_website_source_indexing(background_tasks, source.id)
    return WebsiteSourceActionResponse(message="Website source reindex has been queued.", source=source)


@router.delete("/{source_id}", response_model=MessageResponse)
def remove_website_source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_website_source(db, workspace_id, source_id)
    return MessageResponse(message="Website source deleted successfully.")


@website_router.post("/add", response_model=WebsiteSourceActionResponse, status_code=status.HTTP_201_CREATED)
async def add_website_source_command(
    workspace_id: uuid.UUID,
    payload: WebsiteSourceCommandRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> WebsiteSourceActionResponse:
    if workspace_id != payload.workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace mismatch.")
    source = create_website_source(
        db,
        workspace_id,
        current_user,
        url=payload.url,
        domain_root=payload.domain_root,
        max_depth=payload.max_depth,
        max_pages=payload.max_pages,
    )
    queue_website_source_indexing(background_tasks, source.id)
    return WebsiteSourceActionResponse(message="Website source added and queued for crawling.", source=source)


@website_router.post("/crawl", response_model=WebsiteSourceActionResponse)
async def crawl_website_source_command(
    workspace_id: uuid.UUID,
    payload: WebsiteSourceQueueRequest,
    background_tasks: BackgroundTasks,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> WebsiteSourceActionResponse:
    if workspace_id != payload.workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace mismatch.")
    source = queue_existing_website_source(db, workspace_id, payload.source_id)
    queue_website_source_indexing(background_tasks, source.id)
    return WebsiteSourceActionResponse(message="Website source crawl has been queued.", source=source)


@website_router.get("/list", response_model=list[WebsiteSourceSummary])
async def list_website_sources_command(
    workspace_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member", "viewer")),
    db: Session = Depends(get_db),
) -> list[WebsiteSourceSummary]:
    return list_website_sources(db, workspace_id)


@website_router.delete("/{source_id}", response_model=MessageResponse)
async def delete_website_source_command(
    source_id: uuid.UUID,
    workspace_id: uuid.UUID,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_website_source(db, workspace_id, source_id)
    return MessageResponse(message="Website source deleted successfully.")


@website_router.post("/recrawl", response_model=WebsiteSourceActionResponse)
async def recrawl_website_source_command(
    workspace_id: uuid.UUID,
    payload: WebsiteSourceQueueRequest,
    background_tasks: BackgroundTasks,
    _: WorkspaceMember = Depends(require_workspace_role("admin", "team_member")),
    db: Session = Depends(get_db),
) -> WebsiteSourceActionResponse:
    if workspace_id != payload.workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace mismatch.")
    source = mark_website_source_for_reindex(db, workspace_id, payload.source_id)
    queue_website_source_indexing(background_tasks, source.id)
    return WebsiteSourceActionResponse(message="Website source re-crawl has been queued.", source=source)
