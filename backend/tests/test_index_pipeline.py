import shutil
import unittest
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Document, DocumentChunk, User, Workspace, WorkspaceMember
from app.services.index_pipeline import IndexPipeline
from app.services.text_extractor import settings as extractor_settings


class FakeEmbedder:
    def __init__(self) -> None:
        self.model = "fake-embedding-model"
        self.requests: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.requests.append(texts)
        return [[float(len(text)), float(index), 1.0] for index, text in enumerate(texts)]


class FakeVectorStore:
    def __init__(self) -> None:
        self.collection_sizes: list[int] = []
        self.upserted = []
        self.deleted_points_calls: list[list[str]] = []
        self.deleted_documents: list[tuple[str, str]] = []

    def ensure_collection(self, vector_size: int) -> None:
        self.collection_sizes.append(vector_size)

    def upsert_points(self, points) -> None:
        self.upserted.append(points)

    def delete_points(self, point_ids: list[str]) -> None:
        self.deleted_points_calls.append(point_ids)

    def delete_document_points(self, workspace_id: str, document_id: str) -> None:
        self.deleted_documents.append((workspace_id, document_id))


class IndexPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path.cwd() / ".tmp-test-indexing"
        self.temp_root.mkdir(exist_ok=True)
        self.temp_dir = self.temp_root / f"case-{uuid.uuid4().hex[:8]}"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.previous_storage_dir = extractor_settings.storage_dir
        extractor_settings.storage_dir = str(self.temp_dir)
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        extractor_settings.storage_dir = self.previous_storage_dir
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.engine.dispose()

    def test_pipeline_syncs_chunks_metadata_and_safe_reindex(self) -> None:
        embedder = FakeEmbedder()
        vector_store = FakeVectorStore()
        pipeline = IndexPipeline(embedder=embedder, vector_store=vector_store)

        with self.SessionLocal() as db:
            user = User(
                email="index.pipeline@example.com",
                full_name="Index Pipeline",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()

            workspace = Workspace(
                name="Index Workspace",
                slug=f"index-workspace-{uuid.uuid4().hex[:8]}",
                description="Pipeline tests.",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.flush()

            document = Document(
                workspace_id=workspace.id,
                uploaded_by_user_id=user.id,
                title="report.txt",
                source_type="file",
                storage_path=str(self.temp_dir / "report.txt"),
                mime_type="text/plain",
                file_size=120,
                checksum="checksum",
                ingestion_status="pending",
                metadata_json={"original_filename": "report.txt"},
            )
            db.add(document)
            db.flush()
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=0,
                    content="Old chunk text.",
                    token_count=3,
                    embedding_model="old-model",
                    qdrant_point_id="old-point-id",
                    metadata_json={"document_id": str(document.id)},
                )
            )
            db.commit()
            db.refresh(document)

            file_bytes = (
                b"Revenue rose sharply in Q1. The customer support team improved deflection rates. "
                b"Revenue rose sharply in Q1. The customer support team improved deflection rates. "
                b"The launch readiness checklist is now complete."
            )
            result = pipeline.index_document(db, document, file_bytes)
            self.assertEqual(result.chunk_count, len(document.chunks))
            self.assertEqual(document.ingestion_status, "indexed")
            self.assertEqual(vector_store.collection_sizes, [3])
            self.assertEqual(vector_store.deleted_points_calls[0], ["old-point-id"])
            self.assertGreaterEqual(len(embedder.requests[0]), 1)

            for chunk in document.chunks:
                metadata = chunk.metadata_json or {}
                self.assertEqual(metadata["document_id"], str(document.id))
                self.assertEqual(metadata["workspace_id"], str(workspace.id))
                self.assertEqual(metadata["file_name"], "report.txt")
                self.assertEqual(metadata["source"], "file")
                self.assertEqual(metadata["content_type"], "txt")
                self.assertEqual(metadata["chunk_index"], chunk.chunk_index)
                self.assertEqual(metadata["chunk_id"], chunk.qdrant_point_id)

            previous_point_ids = [chunk.qdrant_point_id for chunk in document.chunks]
            second_result = pipeline.index_document(
                db,
                document,
                b"Fresh sentence one. Fresh sentence two. Fresh sentence three.",
            )
            self.assertEqual(document.ingestion_status, "indexed")
            self.assertEqual(second_result.vector_count, len(document.chunks))
            self.assertIn(previous_point_ids[0], vector_store.deleted_points_calls[-1])

            pipeline.remove_document_index(document)
            self.assertEqual(vector_store.deleted_documents[-1], (str(workspace.id), str(document.id)))


if __name__ == "__main__":
    unittest.main()
