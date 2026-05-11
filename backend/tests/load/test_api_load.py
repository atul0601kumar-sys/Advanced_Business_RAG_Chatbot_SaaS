from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import tempfile
from pathlib import Path

import pytest

from app.core.auth_security import hash_password
from app.db.base import Base
from app.models import User, Workspace, WorkspaceMember
from app.schemas.chat import ChatMessageRequest
from app.services.documents import create_document_from_upload
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tests.fixtures.sample_content import sample_text_base64, sample_text_bytes


class LoadChatService:
    async def stream_message(self, db, current_user, payload, request):  # noqa: ARG002
        yield 'event: start\ndata: {"session_id":"%s","generation_id":"gen-load","message_id":"msg-load"}\n\n' % payload.session_id
        yield 'event: token\ndata: {"delta":"Revenue "}\n\n'
        yield 'event: token\ndata: {"delta":"remained stable."}\n\n'
        yield 'event: complete\ndata: {"answer":"Revenue remained stable.","citations":[],"confidence":"High","metadata":{"retrieved_chunks":1,"processing_time":5,"stopped":false}}\n\n'


@pytest.mark.load
def test_concurrent_chat_requests_remain_stable(seeded_workspace):
    async def consume_stream(index: int) -> str:
        request = ChatMessageRequest(
            session_id=seeded_workspace.session_id,
            message=f"Give me the revenue update {index}",
            mode="concise",
        )
        payload = []
        async for chunk in LoadChatService().stream_message(None, None, request, None):
            payload.append(chunk)
        return "".join(payload)

    async def run_load() -> list[str]:
        return await asyncio.gather(*(consume_stream(index) for index in range(5)))

    responses = asyncio.run(run_load())
    assert all("event: complete" in response for response in responses)
    assert all('"delta":"Revenue "' in response for response in responses)


@pytest.mark.load
def test_multiple_document_uploads_remain_consistent(monkeypatch):
    monkeypatch.setattr("app.services.documents.store_original_file", lambda workspace_id, document_id, filename, file_bytes: str(Path(tempfile.gettempdir()) / f"{document_id}_{filename}"))  # noqa: ARG005
    monkeypatch.setattr("app.services.documents.EventTracker.track_document_uploaded", lambda self, db, document, current_user: None)  # noqa: ARG005

    def worker(index: int) -> str:
        database_path = Path(tempfile.gettempdir()) / f"load-upload-{index}.db"
        if database_path.exists():
            database_path.unlink()
        engine = create_engine(f"sqlite+pysqlite:///{database_path}", future=True)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        with SessionLocal() as db:
            user = User(
                email=f"load-{index}@example.com",
                full_name="Load User",
                password_hash=hash_password("CorrectHorseBatteryStaple!"),
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()
            workspace = Workspace(
                name=f"Load Workspace {index}",
                slug=f"load-workspace-{index}",
                description="load",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.commit()

            document = create_document_from_upload(
                db=db,
                workspace_id=workspace.id,
                current_user=user,
                filename=f"quarterly-{index}.txt",
                mime_type="text/plain",
                file_size=len(sample_text_bytes()),
                content_base64=sample_text_base64(),
            )
            return document.title

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(worker, range(4)))

    assert results == [f"quarterly-{index}.txt" for index in range(4)]
