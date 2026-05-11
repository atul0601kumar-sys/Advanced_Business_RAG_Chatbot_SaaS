from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.dependencies.auth import get_workspace_member
from app.models import ChatSession, ExportJob, FAQ, Lead, User, Workspace
from app.schemas.export import ExportJobResponse
from app.services.analytics_service import AnalyticsService
from app.services.event_tracker import EventTracker
from app.services.file_storage import get_storage_service
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)
settings = get_settings()


class ExportService:
    def __init__(
        self,
        analytics_service: AnalyticsService | None = None,
        report_generator: ReportGenerator | None = None,
        event_tracker: EventTracker | None = None,
        session_factory=None,
    ) -> None:
        self.analytics_service = analytics_service or AnalyticsService()
        self.report_generator = report_generator or ReportGenerator()
        self.event_tracker = event_tracker or EventTracker()
        self.session_factory = session_factory

    def create_job(self, db: Session, current_user: User, *, job_type: str, payload: dict[str, Any]) -> ExportJobResponse:
        workspace_id = uuid.UUID(str(payload["workspace_id"]))
        get_workspace_member(workspace_id, current_user, db)
        self._enforce_rate_limits(db, current_user.id, workspace_id)
        export_format = str(payload.get("format", "csv"))
        job = ExportJob(
            workspace_id=workspace_id,
            requested_by_user_id=current_user.id,
            job_type=job_type,
            export_format=export_format,
            status="pending",
            filters_json=payload,
        )
        db.add(job)
        db.flush()
        self.event_tracker.track_event(
            db,
            workspace_id=workspace_id,
            user_id=current_user.id,
            event_type="export_requested",
            metadata={
                "job_id": job.id,
                "job_type": job_type,
                "format": export_format,
            },
        )
        db.commit()
        db.refresh(job)
        logger.info("Export job queued", extra={"job_id": str(job.id), "job_type": job.job_type})
        return self.serialize_job(job)

    def get_job(self, db: Session, current_user: User, job_id: uuid.UUID) -> ExportJob:
        job = db.get(ExportJob, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found.")
        get_workspace_member(job.workspace_id, current_user, db)
        return job

    def get_status(self, db: Session, current_user: User, job_id: uuid.UUID) -> ExportJobResponse:
        job = self.get_job(db, current_user, job_id)
        return self.serialize_job(job)

    def get_download_payload(self, db: Session, current_user: User, job_id: uuid.UUID) -> tuple[ExportJob, bytes]:
        job = self.get_job(db, current_user, job_id)
        if job.status != "completed" or not job.storage_path:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export file is not ready for download.")
        expires_at = self._ensure_aware(job.expires_at) if job.expires_at else None
        if expires_at and expires_at < datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="This download link has expired.")
        storage = get_storage_service(settings)
        if not storage.exists(job.storage_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file is no longer available.")
        self.event_tracker.track_event(
            db,
            workspace_id=job.workspace_id,
            user_id=current_user.id,
            event_type="export_downloaded",
            metadata={"job_id": job.id, "job_type": job.job_type, "format": job.export_format},
        )
        db.commit()
        return job, storage.load_bytes(job.storage_path)

    def get_download_path(self, db: Session, current_user: User, job_id: uuid.UUID) -> tuple[ExportJob, Path]:
        job = self.get_job(db, current_user, job_id)
        if job.status != "completed" or not job.storage_path:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export file is not ready for download.")
        expires_at = self._ensure_aware(job.expires_at) if job.expires_at else None
        if expires_at and expires_at < datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="This download link has expired.")
        storage = get_storage_service(settings)
        if not storage.exists(job.storage_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file is no longer available.")
        self.event_tracker.track_event(
            db,
            workspace_id=job.workspace_id,
            user_id=current_user.id,
            event_type="export_downloaded",
            metadata={"job_id": job.id, "job_type": job.job_type, "format": job.export_format},
        )
        db.commit()
        local_path = Path(job.storage_path)
        if local_path.exists():
            return job, local_path
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Export is stored remotely; use the signed download URL instead.",
        )

    def process_job(self, job_id: uuid.UUID) -> bool:
        session_factory = self.session_factory
        if session_factory is None:
            from app.db.session import SessionLocal

            session_factory = SessionLocal

        with session_factory() as db:
            job = db.get(ExportJob, job_id)
            if job is None:
                return False
            if job.status == "completed":
                return False
            job.status = "processing"
            job.started_at = datetime.now(UTC)
            job.error_message = None
            job.attempts += 1
            db.commit()
            db.refresh(job)
            try:
                content, content_type, file_name, row_count = self._build_export_content(db, job)
                storage_path = self._store_file(job, content, file_name)
                job.status = "completed"
                job.storage_path = str(storage_path)
                job.file_name = file_name
                job.file_url = get_storage_service(settings).generate_signed_url(storage_path, download_name=file_name) or (
                    f"/api/v1/export/download/{job.id}"
                )
                job.content_type = content_type
                job.row_count = row_count
                job.completed_at = datetime.now(UTC)
                job.expires_at = datetime.now(UTC) + timedelta(minutes=settings.export_download_ttl_minutes)
                self.event_tracker.track_event(
                    db,
                    workspace_id=job.workspace_id,
                    user_id=job.requested_by_user_id,
                    event_type="export_completed",
                    metadata={
                        "job_id": job.id,
                        "job_type": job.job_type,
                        "format": job.export_format,
                        "row_count": row_count,
                    },
                )
                db.commit()
                logger.info("Export job completed", extra={"job_id": str(job.id), "row_count": row_count})
                return False
            except Exception as exc:
                retry = job.attempts < settings.export_job_max_retries
                job.status = "pending" if retry else "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.now(UTC) if not retry else None
                self.event_tracker.track_event(
                    db,
                    workspace_id=job.workspace_id,
                    user_id=job.requested_by_user_id,
                    event_type="export_failed",
                    metadata={
                        "job_id": job.id,
                        "job_type": job.job_type,
                        "format": job.export_format,
                        "attempts": job.attempts,
                        "error": str(exc),
                        "retrying": retry,
                    },
                )
                db.commit()
                logger.exception("Export job failed", extra={"job_id": str(job.id), "retry": retry})
                return retry

    def serialize_job(self, job: ExportJob) -> ExportJobResponse:
        return ExportJobResponse(
            job_id=job.id,
            workspace_id=job.workspace_id,
            type=job.job_type,  # type: ignore[arg-type]
            format=job.export_format,  # type: ignore[arg-type]
            status=job.status,  # type: ignore[arg-type]
            file_url=job.file_url,
            file_name=job.file_name,
            content_type=job.content_type,
            row_count=job.row_count,
            created_at=job.created_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
        )

    def _build_export_content(self, db: Session, job: ExportJob) -> tuple[bytes, str, str, int]:
        if job.job_type == "chat":
            payload = self._build_chat_export_payload(db, job)
            return self._render_dataset(job, payload, title="Chat History Export", base_filename="chat-history")
        if job.job_type == "lead":
            payload = self._build_lead_export_payload(db, job)
            return self._render_dataset(job, payload, title="Lead Export", base_filename="leads")
        if job.job_type == "faq":
            payload = self._build_faq_export_payload(db, job)
            return self._render_dataset(job, payload, title="FAQ Export", base_filename="faqs")
        if job.job_type == "analytics":
            report = self._build_analytics_export_payload(db, job)
            return self._render_analytics(job, report)
        raise RuntimeError(f"Unsupported export job type: {job.job_type}")

    def _render_dataset(
        self,
        job: ExportJob,
        payload: dict[str, Any],
        *,
        title: str,
        base_filename: str,
    ) -> tuple[bytes, str, str, int]:
        export_format = job.export_format
        generated_at = datetime.now(UTC)
        summary_items = payload["summary_items"]
        filter_items = payload["filter_items"]
        rows = payload["rows"]
        row_count = len(rows)
        if export_format == "json":
            content = json.dumps(payload["json"], ensure_ascii=False, indent=2, default=str).encode("utf-8")
            return content, "application/json", f"{base_filename}-{job.id}.json", row_count
        if export_format == "csv":
            content = self.report_generator.build_table_csv(rows, payload["fieldnames"])
            return content, "text/csv", f"{base_filename}-{job.id}.csv", row_count
        pdf_rows = [[str(row.get(field, "")) for field in payload["fieldnames"]] for row in rows]
        content = self.report_generator.build_table_pdf(
            title=title,
            subtitle=payload["subtitle"],
            generated_at=generated_at,
            summary_items=summary_items,
            filter_items=filter_items,
            column_titles=payload["fieldnames"],
            rows=pdf_rows,
        )
        return content, "application/pdf", f"{base_filename}-{job.id}.pdf", row_count

    def _render_analytics(self, job: ExportJob, report: dict[str, Any]) -> tuple[bytes, str, str, int]:
        if job.export_format == "json":
            content = json.dumps(report, ensure_ascii=False, indent=2, default=str).encode("utf-8")
            return content, "application/json", f"analytics-report-{job.id}.json", 1
        if job.export_format == "csv":
            rows = self.report_generator.build_analytics_csv_rows(report)
            content = self.report_generator.build_table_csv(
                rows,
                ["section", "label", "value", "description", "bucket", "secondary_value", "meta"],
            )
            return content, "text/csv", f"analytics-report-{job.id}.csv", len(rows)
        content = self.report_generator.build_analytics_pdf(report)
        return content, "application/pdf", f"analytics-report-{job.id}.pdf", 1

    def _build_chat_export_payload(self, db: Session, job: ExportJob) -> dict[str, Any]:
        filters = job.filters_json or {}
        workspace = self._get_workspace(db, job.workspace_id)
        query = (
            select(ChatSession)
            .options(selectinload(ChatSession.messages), selectinload(ChatSession.user))
            .where(ChatSession.workspace_id == job.workspace_id)
        )
        session_ids = [uuid.UUID(item) for item in filters.get("session_ids", [])]
        if session_ids:
            query = query.where(ChatSession.id.in_(session_ids))
        if filters.get("user_id"):
            query = query.where(ChatSession.user_id == uuid.UUID(filters["user_id"]))
        if filters.get("source"):
            query = query.where(ChatSession.channel == filters["source"])
        if filters.get("date_from"):
            query = query.where(ChatSession.started_at >= self._parse_datetime(filters["date_from"]))
        if filters.get("date_to"):
            query = query.where(ChatSession.started_at <= self._parse_datetime(filters["date_to"]))
        sessions = db.scalars(query.order_by(ChatSession.started_at.desc())).all()

        rows: list[dict[str, Any]] = []
        json_sessions: list[dict[str, Any]] = []
        for session in sessions:
            ordered_messages = sorted(session.messages, key=lambda item: (item.created_at, item.id))
            json_sessions.append(
                {
                    "session_id": str(session.id),
                    "title": session.title,
                    "channel": session.channel,
                    "user_id": str(session.user_id) if session.user_id else None,
                    "started_at": session.started_at.isoformat(),
                    "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
                    "messages": [
                        {
                            "message_id": str(message.id),
                            "role": message.role,
                            "content": message.content,
                            "citations": message.citations_json or [],
                            "confidence_score": (message.token_usage_json or {}).get("confidence"),
                            "created_at": message.created_at.isoformat(),
                        }
                        for message in ordered_messages
                    ],
                }
            )
            for message in ordered_messages:
                rows.append(
                    {
                        "session_id": str(session.id),
                        "session_title": session.title or "",
                        "channel": session.channel,
                        "user_id": str(session.user_id) if session.user_id else "",
                        "role": message.role,
                        "message": message.content,
                        "citations": json.dumps(message.citations_json or [], ensure_ascii=False),
                        "confidence_score": (message.token_usage_json or {}).get("confidence") or "",
                        "timestamp": message.created_at.isoformat(),
                    }
                )

        return {
            "fieldnames": [
                "session_id",
                "session_title",
                "channel",
                "user_id",
                "role",
                "message",
                "citations",
                "confidence_score",
                "timestamp",
            ],
            "rows": rows,
            "json": {
                "workspace": {"id": str(workspace.id), "name": workspace.name, "slug": workspace.slug},
                "filters": filters,
                "sessions": json_sessions,
            },
            "summary_items": [
                ("Workspace", workspace.name),
                ("Sessions exported", str(len(json_sessions))),
                ("Messages exported", str(len(rows))),
            ],
            "filter_items": self._filters_to_pairs(filters),
            "subtitle": "Workspace-isolated export of chat sessions, messages, citations, and confidence scores.",
        }

    def _build_lead_export_payload(self, db: Session, job: ExportJob) -> dict[str, Any]:
        filters = job.filters_json or {}
        workspace = self._get_workspace(db, job.workspace_id)
        query = select(Lead).where(Lead.workspace_id == job.workspace_id)
        if filters.get("status"):
            query = query.where(Lead.status == filters["status"])
        if filters.get("priority"):
            query = query.where(Lead.priority == filters["priority"])
        if filters.get("source"):
            query = query.where(Lead.source == filters["source"])
        if filters.get("date_from"):
            query = query.where(Lead.created_at >= self._parse_datetime(filters["date_from"]))
        if filters.get("date_to"):
            query = query.where(Lead.created_at <= self._parse_datetime(filters["date_to"]))
        leads = db.scalars(query.order_by(Lead.created_at.desc())).all()

        rows = [
            {
                "name": lead.name or "",
                "email": lead.email or "",
                "phone": lead.phone or "",
                "company": lead.company or "",
                "message": lead.message or "",
                "status": lead.status,
                "priority": lead.priority,
                "source": lead.source,
                "created_at": lead.created_at.isoformat(),
            }
            for lead in leads
        ]
        return {
            "fieldnames": ["name", "email", "phone", "company", "message", "status", "priority", "source", "created_at"],
            "rows": rows,
            "json": {
                "workspace": {"id": str(workspace.id), "name": workspace.name, "slug": workspace.slug},
                "filters": filters,
                "leads": rows,
            },
            "summary_items": [("Workspace", workspace.name), ("Leads exported", str(len(rows)))],
            "filter_items": self._filters_to_pairs(filters),
            "subtitle": "Filtered lead export including contact details, lifecycle status, and capture timestamps.",
        }

    def _build_faq_export_payload(self, db: Session, job: ExportJob) -> dict[str, Any]:
        filters = job.filters_json or {}
        workspace = self._get_workspace(db, job.workspace_id)
        query = select(FAQ).where(FAQ.workspace_id == job.workspace_id)
        if filters.get("status"):
            query = query.where(FAQ.status == filters["status"])
        if filters.get("category"):
            query = query.where(FAQ.category == filters["category"])
        if filters.get("source"):
            pattern = f'%{filters["source"]}%'
            query = query.where(FAQ.source.ilike(pattern))
        if filters.get("date_from"):
            query = query.where(FAQ.created_at >= self._parse_datetime(filters["date_from"]))
        if filters.get("date_to"):
            query = query.where(FAQ.created_at <= self._parse_datetime(filters["date_to"]))
        faqs = db.scalars(query.order_by(FAQ.category.asc(), FAQ.question.asc())).all()

        rows = [
            {
                "question": faq.question,
                "answer": faq.answer,
                "category": faq.category,
                "source": faq.source,
                "status": faq.status,
                "confidence_score": f"{faq.confidence_score:.2f}",
                "created_at": faq.created_at.isoformat(),
            }
            for faq in faqs
        ]
        return {
            "fieldnames": ["question", "answer", "category", "source", "status", "confidence_score", "created_at"],
            "rows": rows,
            "json": {
                "workspace": {"id": str(workspace.id), "name": workspace.name, "slug": workspace.slug},
                "filters": filters,
                "faqs": rows,
            },
            "summary_items": [("Workspace", workspace.name), ("FAQs exported", str(len(rows)))],
            "filter_items": self._filters_to_pairs(filters),
            "subtitle": "Approved and reviewable FAQ export for client-facing knowledge operations.",
        }

    def _build_analytics_export_payload(self, db: Session, job: ExportJob) -> dict[str, Any]:
        filters = job.filters_json or {}
        workspace = self._get_workspace(db, job.workspace_id)
        date_from = self._parse_datetime(filters.get("date_from")) if filters.get("date_from") else None
        date_to = self._parse_datetime(filters.get("date_to")) if filters.get("date_to") else None
        user_id = uuid.UUID(filters["user_id"]) if filters.get("user_id") else None
        document_id = uuid.UUID(filters["document_id"]) if filters.get("document_id") else None
        source = filters.get("source")

        overview = self.analytics_service.get_overview(
            db,
            workspace_id=job.workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        ).model_dump(mode="json")
        chats = self.analytics_service.get_chat_analytics(
            db,
            workspace_id=job.workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        ).model_dump(mode="json")
        leads = self.analytics_service.get_lead_analytics(
            db,
            workspace_id=job.workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        ).model_dump(mode="json")
        performance = self.analytics_service.get_performance_analytics(
            db,
            workspace_id=job.workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        ).model_dump(mode="json")
        queries = self.analytics_service.get_query_analytics(
            db,
            workspace_id=job.workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        ).model_dump(mode="json")
        feedback = self.analytics_service.get_feedback_analytics(
            db,
            workspace_id=job.workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        ).model_dump(mode="json")

        return {
            "workspace": {"id": str(workspace.id), "name": workspace.name, "slug": workspace.slug},
            "generated_at": datetime.now(UTC).isoformat(),
            "date_range": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            },
            "filters": filters,
            "overview": overview,
            "chats": chats,
            "leads": leads,
            "performance": performance,
            "queries": queries,
            "feedback": feedback,
        }

    def _store_file(self, job: ExportJob, content: bytes, file_name: str) -> str:
        return get_storage_service(settings).store_bytes(
            object_group="exports",
            workspace_id=str(job.workspace_id),
            object_id=str(job.id),
            filename=file_name,
            content=content,
        )

    def _get_workspace(self, db: Session, workspace_id: uuid.UUID) -> Workspace:
        workspace = db.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        return workspace

    def _enforce_rate_limits(self, db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        active_jobs = db.scalar(
            select(func.count(ExportJob.id)).where(
                ExportJob.requested_by_user_id == user_id,
                ExportJob.workspace_id == workspace_id,
                ExportJob.status.in_(["pending", "processing"]),
            )
        ) or 0
        if active_jobs >= settings.export_active_job_limit_per_user:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many export jobs are already running. Please wait for one to finish.",
            )

        since = datetime.now(UTC) - timedelta(hours=1)
        recent_jobs = db.scalar(
            select(func.count(ExportJob.id)).where(
                ExportJob.requested_by_user_id == user_id,
                ExportJob.workspace_id == workspace_id,
                ExportJob.created_at >= since,
            )
        ) or 0
        if recent_jobs >= settings.export_rate_limit_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Export rate limit reached for this workspace. Please try again later.",
            )

    def _filters_to_pairs(self, filters: dict[str, Any]) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for key in ["date_from", "date_to", "source", "status", "priority", "category", "user_id", "document_id"]:
            value = filters.get(key)
            if value:
                pairs.append((key.replace("_", " ").title(), str(value)))
        session_ids = filters.get("session_ids") or []
        if session_ids:
            pairs.append(("Selected sessions", ", ".join(session_ids)))
        return pairs

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return self._ensure_aware(value)
        return self._ensure_aware(datetime.fromisoformat(str(value).replace("Z", "+00:00")))

    def _ensure_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
