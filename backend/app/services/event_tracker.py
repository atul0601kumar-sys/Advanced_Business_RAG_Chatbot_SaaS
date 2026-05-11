from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import AnalyticsEvent, ChatMessage, ChatSession, Document, Feedback, Lead, User, WebsiteSource
from app.schemas.chat import ChatAnswerResponse, ChatMessageRequest
from app.services.event_dispatcher import EventDispatcher
from app.services.query_analyzer import QueryAnalyzer
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class EventTracker:
    def __init__(
        self,
        query_analyzer: QueryAnalyzer | None = None,
        settings_service: SettingsService | None = None,
        event_dispatcher: EventDispatcher | None = None,
    ) -> None:
        self.query_analyzer = query_analyzer or QueryAnalyzer()
        self.settings_service = settings_service or SettingsService()
        self.event_dispatcher = event_dispatcher or EventDispatcher()

    def track_event(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        event_type: str,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        metadata: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> AnalyticsEvent:
        runtime_setting = self.settings_service.get_setting_for_runtime(db, workspace_id)
        analytics_config = runtime_setting.analytics_config_json or {}
        if not analytics_config.get("tracking_enabled", True):
            return AnalyticsEvent(
                workspace_id=workspace_id,
                user_id=None,
                chat_session_id=session_id,
                event_type=event_type,
                event_name=event_type.replace("_", " ").title(),
                properties_json={},
                occurred_at=occurred_at or datetime.now(UTC),
            )
        event = AnalyticsEvent(
            workspace_id=workspace_id,
            user_id=None if analytics_config.get("anonymize_user_data") else user_id,
            chat_session_id=session_id,
            event_type=event_type,
            event_name=event_type.replace("_", " ").title(),
            properties_json=self._normalize_value(metadata or {}),
            occurred_at=occurred_at or datetime.now(UTC),
        )
        db.add(event)
        db.flush()
        self.event_dispatcher.dispatch(
            db,
            workspace_id=workspace_id,
            event_type=event_type,
            data=self._normalize_value(metadata or {}),
        )
        logger.info(
            "Tracked analytics event",
            extra={
                "event_id": str(event.id),
                "event_type": event.event_type,
                "workspace_id": str(workspace_id),
                "session_id": str(session_id) if session_id else None,
            },
        )
        return event

    def track_chat_started(self, db: Session, *, session: ChatSession, current_user: User | None) -> AnalyticsEvent:
        db.flush()
        return self.track_event(
            db,
            workspace_id=session.workspace_id,
            user_id=current_user.id if current_user else session.user_id,
            session_id=session.id,
            event_type="chat_started",
            metadata={
                "source": session.channel,
                "title": session.title,
                "started_at": session.started_at,
            },
        )

    def track_message_sent(
        self,
        db: Session,
        *,
        session: ChatSession,
        current_user: User | None,
        message: ChatMessage,
        payload: ChatMessageRequest,
    ) -> AnalyticsEvent:
        return self.track_event(
            db,
            workspace_id=session.workspace_id,
            user_id=current_user.id if current_user else session.user_id,
            session_id=session.id,
            event_type="message_sent",
            metadata={
                "message_id": message.id,
                "query": message.content,
                "normalized_query": self.query_analyzer.normalize_query(message.content),
                "mode": payload.mode,
                "source": session.channel,
                "filters": payload.filters.model_dump(mode="json") if payload.filters else None,
            },
            occurred_at=message.created_at,
        )

    def track_message_received(
        self,
        db: Session,
        *,
        session: ChatSession,
        current_user: User | None,
        message: ChatMessage,
        result: ChatAnswerResponse,
        regenerated: bool = False,
    ) -> AnalyticsEvent:
        return self.track_event(
            db,
            workspace_id=session.workspace_id,
            user_id=current_user.id if current_user else session.user_id,
            session_id=session.id,
            event_type="message_received",
            metadata={
                "message_id": message.id,
                "answer_excerpt": result.answer[:500],
                "confidence": result.confidence,
                "confidence_score": self._confidence_score(result.confidence),
                "response_time_ms": result.metadata.processing_time,
                "retrieved_chunks": result.metadata.retrieved_chunks,
                "retrieval_success": result.metadata.retrieved_chunks > 0,
                "source": session.channel,
                "regenerated": regenerated,
                "citations": [citation.model_dump(mode="json") for citation in result.citations],
                "document_ids": [citation.document_id for citation in result.citations if citation.document_id],
                "urls": [citation.url for citation in result.citations if citation.url],
            },
            occurred_at=message.created_at,
        )

    def track_lead_created(self, db: Session, *, lead: Lead, current_user: User | None) -> AnalyticsEvent:
        db.flush()
        event = self.track_event(
            db,
            workspace_id=lead.workspace_id,
            user_id=current_user.id if current_user else None,
            session_id=lead.chat_session_id,
            event_type="lead_created",
            metadata={
                "lead_id": lead.id,
                "source": lead.source,
                "priority": lead.priority,
                "status": lead.status,
                "high_intent": lead.high_intent,
                "tag": lead.tag,
                "company": lead.company,
                "use_case": lead.use_case,
            },
            occurred_at=lead.created_at,
        )
        if (lead.priority or "").lower() == "high":
            self.track_event(
                db,
                workspace_id=lead.workspace_id,
                user_id=current_user.id if current_user else None,
                session_id=lead.chat_session_id,
                event_type="high_priority_lead",
                metadata={
                    "lead_id": lead.id,
                    "priority": lead.priority,
                    "source": lead.source,
                    "company": lead.company,
                },
                occurred_at=lead.created_at,
            )
        return event

    def track_lead_converted(
        self,
        db: Session,
        *,
        lead: Lead,
        current_user: User,
        previous_status: str | None,
    ) -> AnalyticsEvent:
        return self.track_event(
            db,
            workspace_id=lead.workspace_id,
            user_id=current_user.id,
            session_id=lead.chat_session_id,
            event_type="lead_converted",
            metadata={
                "lead_id": lead.id,
                "source": lead.source,
                "priority": lead.priority,
                "status": lead.status,
                "previous_status": previous_status,
                "high_intent": lead.high_intent,
                "tag": lead.tag,
            },
            occurred_at=lead.updated_at,
        )

    def track_feedback_submitted(
        self,
        db: Session,
        *,
        feedback: Feedback,
        confidence: str | None,
        response_excerpt: str | None,
    ) -> AnalyticsEvent:
        db.flush()
        return self.track_event(
            db,
            workspace_id=feedback.workspace_id,
            user_id=feedback.user_id,
            session_id=feedback.chat_session_id,
            event_type="feedback_submitted",
            metadata={
                "feedback_id": feedback.id,
                "rating": feedback.rating,
                "category": feedback.category,
                "comment": feedback.comment,
                "confidence": confidence,
                "confidence_score": self._confidence_score(confidence),
                "response_excerpt": response_excerpt,
            },
            occurred_at=feedback.created_at,
        )

    def track_unanswered_question(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_message: ChatMessage,
        question: str,
        reason: str,
    ) -> AnalyticsEvent:
        return self.track_event(
            db,
            workspace_id=session.workspace_id,
            user_id=session.user_id,
            session_id=session.id,
            event_type="unanswered_question",
            metadata={
                "message_id": user_message.id,
                "question": question,
                "normalized_query": self.query_analyzer.normalize_query(question),
                "reason": reason,
                "source": session.channel,
            },
            occurred_at=user_message.created_at,
        )

    def track_document_uploaded(self, db: Session, *, document: Document, current_user: User) -> AnalyticsEvent:
        db.flush()
        return self.track_event(
            db,
            workspace_id=document.workspace_id,
            user_id=current_user.id,
            event_type="document_uploaded",
            metadata={
                "document_id": document.id,
                "title": document.title,
                "source_type": document.source_type,
                "mime_type": document.mime_type,
                "file_size": document.file_size,
            },
            occurred_at=document.created_at,
        )

    def track_website_crawled(self, db: Session, *, source: WebsiteSource) -> AnalyticsEvent:
        db.flush()
        metadata = source.metadata_json or {}
        return self.track_event(
            db,
            workspace_id=source.workspace_id,
            user_id=None,
            session_id=None,
            event_type="website_crawled",
            metadata={
                "source_id": source.id,
                "document_id": source.document_id,
                "url": source.url,
                "domain": source.domain,
                "page_count": metadata.get("page_count"),
                "visited_urls": metadata.get("visited_urls", []),
                "blocked_urls": metadata.get("blocked_urls", []),
            },
            occurred_at=source.last_crawled_at or datetime.now(UTC),
        )

    def _normalize_value(self, value):
        if isinstance(value, dict):
            return {key: self._normalize_value(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self._normalize_value(child) for child in value]
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _confidence_score(self, confidence: str | None) -> float | None:
        if confidence == "High":
            return 0.9
        if confidence == "Medium":
            return 0.6
        if confidence == "Low":
            return 0.3
        return None
