import base64
import shutil
import unittest
import uuid
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Document, User, Workspace, WorkspaceMember
from app.services.documents import (
    create_document_from_upload,
    delete_document,
    list_documents_for_workspace,
    mark_document_for_reindex,
)
from app.services.index_pipeline import IndexPipeline
from app.services.text_extractor import settings as extractor_settings


class FakeVectorStore:
    def __init__(self) -> None:
        self.deleted_documents: list[tuple[str, str]] = []

    def delete_document_points(self, workspace_id: str, document_id: str) -> None:
        self.deleted_documents.append((workspace_id, document_id))


class FakeDeletePipeline:
    def __init__(self) -> None:
        self.deleted_documents: list[tuple[str, str]] = []

    def remove_document_index(self, document: Document) -> None:
        self.deleted_documents.append((str(document.workspace_id), str(document.id)))


class FakeMissingQdrantDeletePipeline:
    def remove_document_index(self, document: Document) -> None:  # noqa: ARG002
        raise RuntimeError(
            "Qdrant request failed with HTTP 404: "
            '{"status":{"error":"Not found: Collection \\"document_chunks\\" doesn\'t exist!"}}'
        )


class DocumentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path.cwd() / ".tmp-test-storage"
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

    def test_upload_marks_pending_and_delete_removes_file(self) -> None:
        with self.SessionLocal() as db:
            user = User(
                email="doc.service@example.com",
                full_name="Document Service",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()

            workspace = Workspace(
                name="Document Ops",
                slug=f"document-ops-{uuid.uuid4().hex[:8]}",
                description="Temp workspace for document tests.",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.commit()

            upload = create_document_from_upload(
                db=db,
                workspace_id=workspace.id,
                current_user=user,
                filename="notes.txt",
                mime_type="text/plain",
                file_size=len(b"alpha\nbeta\ngamma"),
                content_base64=base64.b64encode(b"alpha\nbeta\ngamma").decode("utf-8"),
            )
            self.assertEqual(upload.ingestion_status, "pending")

            listed = list_documents_for_workspace(db, workspace.id)
            self.assertEqual(len(listed), 1)

            pending = mark_document_for_reindex(db, workspace.id, upload.id)
            self.assertEqual(pending.ingestion_status, "pending")

            stored_document = db.scalar(select(Document).where(Document.id == upload.id))
            self.assertIsNotNone(stored_document)
            self.assertTrue(Path(stored_document.storage_path).exists())

            fake_pipeline = FakeDeletePipeline()
            delete_document(db, workspace.id, upload.id, pipeline=fake_pipeline)  # type: ignore[arg-type]
            self.assertEqual(list_documents_for_workspace(db, workspace.id), [])
            self.assertFalse(Path(stored_document.storage_path).exists())
            self.assertEqual(fake_pipeline.deleted_documents, [(str(workspace.id), str(upload.id))])

    def test_delete_ignores_missing_qdrant_vectors_for_stale_document(self) -> None:
        with self.SessionLocal() as db:
            user = User(
                email="stale.delete@example.com",
                full_name="Stale Delete",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()

            workspace = Workspace(
                name="Stale Document Cleanup",
                slug=f"stale-docs-{uuid.uuid4().hex[:8]}",
                description="Temp workspace for stale cleanup tests.",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.commit()

            upload = create_document_from_upload(
                db=db,
                workspace_id=workspace.id,
                current_user=user,
                filename="legacy.txt",
                mime_type="text/plain",
                file_size=len(b"legacy content"),
                content_base64=base64.b64encode(b"legacy content").decode("utf-8"),
            )

            stored_document = db.scalar(select(Document).where(Document.id == upload.id))
            self.assertIsNotNone(stored_document)
            self.assertTrue(Path(stored_document.storage_path).exists())

            delete_document(
                db,
                workspace.id,
                upload.id,
                pipeline=FakeMissingQdrantDeletePipeline(),  # type: ignore[arg-type]
            )

            self.assertIsNone(db.scalar(select(Document).where(Document.id == upload.id)))
            self.assertFalse(Path(stored_document.storage_path).exists())


if __name__ == "__main__":
    unittest.main()
