import json
from pathlib import Path
import unittest
import uuid
import shutil

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import ChatMessage, ChatSession, FAQ, User, Workspace, WorkspaceMember
from app.services.export_service import ExportService


class ExportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
        self.temp_dir = Path("tests") / f".tmp-export-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.settings = get_settings()
        self.original_export_storage_dir = self.settings.export_storage_dir
        self.settings.export_storage_dir = str(self.temp_dir)

    def tearDown(self) -> None:
        self.settings.export_storage_dir = self.original_export_storage_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.engine.dispose()

    def _seed(self):
        with self.SessionLocal() as db:
            user = User(
                email="exports@example.com",
                full_name="Exports User",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            outsider = User(
                email="outsider@example.com",
                full_name="Outsider",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add_all([user, outsider])
            db.flush()

            workspace = Workspace(
                name="Export Workspace",
                slug=f"export-workspace-{uuid.uuid4().hex[:8]}",
                description="Workspace used for export testing",
                status="active",
                owner_user_id=user.id,
            )
            other_workspace = Workspace(
                name="Other Workspace",
                slug=f"other-workspace-{uuid.uuid4().hex[:8]}",
                description="Other workspace",
                status="active",
                owner_user_id=outsider.id,
            )
            db.add_all([workspace, other_workspace])
            db.flush()
            db.add_all(
                [
                    WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"),
                    WorkspaceMember(workspace_id=other_workspace.id, user_id=outsider.id, role="admin"),
                ]
            )
            session = ChatSession(
                workspace_id=workspace.id,
                user_id=user.id,
                title="Export session",
                status="active",
                channel="web",
            )
            db.add(session)
            db.flush()
            db.add_all(
                [
                    ChatMessage(chat_session_id=session.id, role="user", content="How does export work?"),
                    ChatMessage(
                        chat_session_id=session.id,
                        role="assistant",
                        content="Export runs in the background.",
                        citations_json=[{"file_name": "guide.pdf", "page_number": 3, "chunk_preview": "Export runs in the background."}],
                        token_usage_json={"confidence": "High"},
                    ),
                ]
            )
            db.add(
                FAQ(
                    workspace_id=workspace.id,
                    question="How do exports work?",
                    answer="They are processed in the background and stored for secure download.",
                    category="Operations",
                    source="knowledge-base",
                    status="approved",
                    confidence_score=0.92,
                    normalized_question="how do exports work",
                )
            )
            db.commit()
            return {
                "user_id": user.id,
                "outsider_id": outsider.id,
                "workspace_id": workspace.id,
                "other_workspace_id": other_workspace.id,
                "session_id": session.id,
            }

    def test_chat_export_job_completes_and_writes_csv(self) -> None:
        seeded = self._seed()
        service = ExportService(session_factory=self.SessionLocal)
        with self.SessionLocal() as db:
            user = db.get(User, seeded["user_id"])
            response = service.create_job(
                db,
                user,
                job_type="chat",
                payload={
                    "workspace_id": str(seeded["workspace_id"]),
                    "format": "csv",
                    "session_ids": [str(seeded["session_id"])],
                },
            )

        should_retry = service.process_job(response.job_id)
        self.assertFalse(should_retry)

        with self.SessionLocal() as db:
            user = db.get(User, seeded["user_id"])
            status_payload = service.get_status(db, user, response.job_id)
            self.assertEqual(status_payload.status, "completed")
            self.assertEqual(status_payload.format, "csv")
            job, path = service.get_download_path(db, user, response.job_id)
            self.assertTrue(path.exists())
            csv_text = path.read_text(encoding="utf-8")
            self.assertIn("session_id", csv_text)
            self.assertIn("Export runs in the background.", csv_text)
            self.assertEqual(job.row_count, 2)

    def test_faq_export_job_completes_and_writes_json(self) -> None:
        seeded = self._seed()
        service = ExportService(session_factory=self.SessionLocal)
        with self.SessionLocal() as db:
            user = db.get(User, seeded["user_id"])
            response = service.create_job(
                db,
                user,
                job_type="faq",
                payload={
                    "workspace_id": str(seeded["workspace_id"]),
                    "format": "json",
                    "status": "approved",
                },
            )

        service.process_job(response.job_id)

        with self.SessionLocal() as db:
            user = db.get(User, seeded["user_id"])
            _, path = service.get_download_path(db, user, response.job_id)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["workspace"]["id"], str(seeded["workspace_id"]))
            self.assertEqual(payload["faqs"][0]["category"], "Operations")

    def test_analytics_export_job_completes_and_writes_pdf(self) -> None:
        seeded = self._seed()
        service = ExportService(session_factory=self.SessionLocal)
        with self.SessionLocal() as db:
            user = db.get(User, seeded["user_id"])
            response = service.create_job(
                db,
                user,
                job_type="analytics",
                payload={
                    "workspace_id": str(seeded["workspace_id"]),
                    "format": "pdf",
                },
            )

        service.process_job(response.job_id)

        with self.SessionLocal() as db:
            user = db.get(User, seeded["user_id"])
            job, path = service.get_download_path(db, user, response.job_id)
            self.assertEqual(job.content_type, "application/pdf")
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 1000)

    def test_workspace_scoping_blocks_other_users_from_status_access(self) -> None:
        seeded = self._seed()
        service = ExportService(session_factory=self.SessionLocal)
        with self.SessionLocal() as db:
            user = db.get(User, seeded["user_id"])
            response = service.create_job(
                db,
                user,
                job_type="chat",
                payload={"workspace_id": str(seeded["workspace_id"]), "format": "json"},
            )

        with self.SessionLocal() as db:
            outsider = db.get(User, seeded["outsider_id"])
            with self.assertRaises(HTTPException) as context:
                service.get_status(db, outsider, response.job_id)
            self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
