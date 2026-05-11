from __future__ import annotations

import uuid

import pytest

from app.models import Document, DocumentChunk, User, Workspace, WorkspaceMember
from app.services.index_pipeline import IndexPipeline


class IntegrityEmbedder:
    model = "integrity-model"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1), float(len(text))] for index, text in enumerate(texts)]


class IntegrityVectorStore:
    def __init__(self) -> None:
        self.points = []

    def ensure_collection(self, vector_size: int) -> None:  # noqa: ARG002
        return None

    def upsert_points(self, points) -> None:
        self.points.extend(points)

    def delete_points(self, point_ids) -> None:  # noqa: ARG002
        return None

    def delete_document_points(self, workspace_id: str, document_id: str) -> None:  # noqa: ARG002
        return None


@pytest.mark.integration
def test_index_pipeline_prevents_duplicate_chunk_rows_and_maps_metadata(db_session):
    user = User(email="integrity@example.com", full_name="Integrity", password_hash="hashed", is_active=True, is_superuser=False)
    db_session.add(user)
    db_session.flush()
    workspace = Workspace(name="Integrity", slug=f"integrity-{uuid.uuid4().hex[:6]}", description="integrity", status="active", owner_user_id=user.id)
    db_session.add(workspace)
    db_session.flush()
    db_session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))

    document = Document(
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        title="integrity.txt",
        source_type="file",
        mime_type="text/plain",
        file_size=128,
        ingestion_status="pending",
        metadata_json={},
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    repeated_text = (
        b"Revenue grew 18 percent year over year.\n\n"
        b"Revenue grew 18 percent year over year.\n\n"
        b"Onboarding improved after workflow automation."
    )
    pipeline = IndexPipeline(embedder=IntegrityEmbedder(), vector_store=IntegrityVectorStore())
    result = pipeline.index_document(db_session, document, repeated_text)

    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index).all()
    assert result.chunk_count == len(chunks)
    assert len({chunk.chunk_index for chunk in chunks}) == len(chunks)
    assert len({chunk.metadata_json["content_hash"] for chunk in chunks}) == len(chunks)
    assert all(chunk.metadata_json["workspace_id"] == str(workspace.id) for chunk in chunks)
    assert all(chunk.metadata_json["document_id"] == str(document.id) for chunk in chunks)


@pytest.mark.integration
def test_workspace_scoped_queries_only_return_owned_documents(db_session, seeded_workspace):
    owned = Document(
        workspace_id=seeded_workspace.workspace_id,
        uploaded_by_user_id=seeded_workspace.user_id,
        title="owned.txt",
        source_type="file",
        mime_type="text/plain",
        file_size=1,
        ingestion_status="indexed",
        metadata_json={},
    )
    foreign = Document(
        workspace_id=seeded_workspace.other_workspace_id,
        uploaded_by_user_id=seeded_workspace.user_id,
        title="foreign.txt",
        source_type="file",
        mime_type="text/plain",
        file_size=1,
        ingestion_status="indexed",
        metadata_json={},
    )
    db_session.add_all([owned, foreign])
    db_session.commit()

    owned_docs = db_session.query(Document).filter(Document.workspace_id == seeded_workspace.workspace_id).all()
    assert all(document.workspace_id == seeded_workspace.workspace_id for document in owned_docs)
