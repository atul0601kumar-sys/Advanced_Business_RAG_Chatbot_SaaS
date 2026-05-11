from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import AsyncIterator

from fastapi import BackgroundTasks
from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit_logger import AuditAction, flag_suspicious_request
from app.dependencies.auth import get_workspace_member
from app.core.input_validator import sanitize_prompt_input
from app.models import ChatMessage, ChatSession, ChatbotSetting, Feedback, UnresolvedQuestion, User, Workspace
from app.schemas.chat import (
    ChatAnswerResponse,
    ChatFeedbackRequest,
    ChatFeedbackResponse,
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatRegenerateRequest,
    ChatSessionCreateRequest,
    ChatSessionSummary,
)
from app.schemas.chat import StopGenerationRequest
from app.core.config import get_settings
from app.services.memory_manager import MemoryManager
from app.services.lead_service import LeadService
from app.services.event_tracker import EventTracker
from app.services.notification_service import NotificationService
from app.services.rag_service import RagService
from app.services.settings_service import SettingsService
from app.services.streaming_handler import StopGenerationRegistry, StreamingHandler

logger = logging.getLogger(__name__)
settings = get_settings()
shared_stop_registry = StopGenerationRegistry()


class ChatService:
    def __init__(
        self,
        rag_service: RagService | None = None,
        memory_manager: MemoryManager | None = None,
        streaming_handler: StreamingHandler | None = None,
        stop_registry: StopGenerationRegistry | None = None,
        lead_service: LeadService | None = None,
        notification_service: NotificationService | None = None,
        event_tracker: EventTracker | None = None,
        settings_service: SettingsService | None = None,
    ) -> None:
        self.rag_service = rag_service or RagService()
        self.memory_manager = memory_manager or MemoryManager(
            recent_message_limit=settings.chat_recent_message_limit,
            token_limit=settings.chat_memory_token_limit,
            summary_trigger_message_count=settings.chat_summary_trigger_message_count,
        )
        self.streaming_handler = streaming_handler or StreamingHandler()
        self.stop_registry = stop_registry or shared_stop_registry
        self.lead_service = lead_service or LeadService()
        self.notification_service = notification_service or NotificationService()
        self.event_tracker = event_tracker or EventTracker()
        self.settings_service = settings_service or SettingsService()

    def create_session(self, db: Session, current_user: User | None, payload: ChatSessionCreateRequest) -> ChatSessionSummary:
        if current_user is not None:
            get_workspace_member(payload.workspace_id, current_user, db)
        session = ChatSession(
            workspace_id=payload.workspace_id,
            user_id=current_user.id if current_user else None,
            title=payload.title,
            status="active",
            channel=payload.channel,
            started_at=datetime.now(UTC),
            last_message_at=None,
        )
        db.add(session)
        self.event_tracker.track_chat_started(db, session=session, current_user=current_user)
        db.commit()
        db.refresh(session)
        return self._serialize_session(db, session)

    def list_sessions(self, db: Session, current_user: User, workspace_id: uuid.UUID) -> list[ChatSessionSummary]:
        get_workspace_member(workspace_id, current_user, db)
        sessions = db.scalars(
            select(ChatSession)
            .where(
                ChatSession.workspace_id == workspace_id,
                ChatSession.user_id == current_user.id,
            )
            .order_by(ChatSession.last_message_at.desc().nullslast(), ChatSession.created_at.desc())
        ).all()
        return [self._serialize_session(db, session) for session in sessions]

    def get_history(self, db: Session, current_user: User | None, session_id: uuid.UUID) -> ChatHistoryResponse:
        session = self._get_session_for_actor(db, current_user, session_id)
        messages = self._load_session_messages(db, session.id)
        return ChatHistoryResponse(
            session=self._serialize_session(db, session),
            messages=[
                ChatHistoryMessage(
                    id=message.id,
                    role=message.role,
                    content=message.content,
                    citations=message.citations_json or [],
                    token_usage=message.token_usage_json,
                    response_time_ms=message.response_time_ms,
                    created_at=message.created_at,
                    updated_at=message.updated_at,
                )
                for message in messages
            ],
        )

    async def stream_message(
        self,
        db: Session,
        current_user: User | None,
        payload: ChatMessageRequest,
        request: Request,
    ) -> AsyncIterator[str]:
        session = self._get_session_for_actor(db, current_user, payload.session_id)
        sanitized_prompt = sanitize_prompt_input(payload.message)
        if sanitized_prompt.was_modified:
            flag_suspicious_request(
                request,
                action=AuditAction.PROMPT_INJECTION,
                metadata={"session_id": str(session.id)},
            )
        user_message = self._store_message(
            db,
            session,
            role="user",
            content=sanitized_prompt.text,
        )
        self.event_tracker.track_message_sent(
            db,
            session=session,
            current_user=current_user,
            message=user_message,
            payload=payload.model_copy(update={"message": sanitized_prompt.text}),
        )
        all_messages = self._load_session_messages(db, session.id)
        memory = self.memory_manager.build_memory(
            all_messages,
            session.session_summary,
            summarizer=self.rag_service.summarize_messages,
        )
        session.session_summary = memory.updated_summary
        self._ensure_session_title(session, sanitized_prompt.text)
        db.commit()

        handle = self.stop_registry.register(session.id)
        yield self.streaming_handler.encode(
            "start",
            {
                "session_id": str(session.id),
                "generation_id": handle.generation_id,
                "message_id": str(user_message.id),
            },
        )

        assistant_result: ChatAnswerResponse | None = None
        try:
            prior_messages = [message for message in memory.recent_messages if message.id != user_message.id]
            async for event in self.rag_service.stream_answer(
                db=db,
                workspace_id=session.workspace_id,
                query=sanitized_prompt.text,
                mode=payload.mode,
                filters=payload.filters,
                memory=memory,
                prior_messages=prior_messages,
                stop_event=handle.stop_event,
            ):
                if await request.is_disconnected():
                    handle.stop_event.set()
                if event.event_type == "token":
                    yield self.streaming_handler.encode("token", {"delta": event.token})
                    continue
                if event.result is not None:
                    assistant_result = event.result
        finally:
            self.stop_registry.release(handle)

        if assistant_result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Streaming response did not complete.",
            )

        lead_capture = self.lead_service.evaluate_capture_prompt(
            db,
            session,
            query=sanitized_prompt.text,
            confidence=assistant_result.confidence,
        )
        if lead_capture.should_prompt and lead_capture.trigger in {"low_confidence", "human_request"}:
            self._mark_needs_human_review(db, session, user_message, sanitized_prompt.text, lead_capture.trigger)
        saved_assistant = self._store_assistant_result(
            db,
            session=session,
            result=assistant_result,
            generation_id=handle.generation_id,
            current_user=current_user,
        )
        yield self.streaming_handler.encode(
            "complete",
            assistant_result.model_copy(
                update={
                    "metadata": assistant_result.metadata.model_copy(
                        update={
                            "session_id": session.id,
                            "message_id": saved_assistant.id,
                            "generation_id": handle.generation_id,
                            "lead_capture": lead_capture,
                        }
                    )
                }
            ).model_dump(mode="json"),
        )

    async def regenerate_last_response(
        self,
        db: Session,
        current_user: User | None,
        payload: ChatRegenerateRequest,
    ) -> ChatAnswerResponse:
        session = self._get_session_for_actor(db, current_user, payload.session_id)
        messages = self._load_session_messages(db, session.id)
        last_user = next((message for message in reversed(messages) if message.role == "user"), None)
        if last_user is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user message available to regenerate.")
        last_assistant = self._find_last_assistant_after_user(messages, last_user.id)
        last_user_index = next(index for index, message in enumerate(messages) if message.id == last_user.id)
        history_before_user = messages[:last_user_index]
        memory = self.memory_manager.build_memory(
            history_before_user + [last_user],
            session.session_summary,
            summarizer=self.rag_service.summarize_messages,
        )
        prior_messages = [message for message in memory.recent_messages if message.id != last_user.id]
        result = await self.rag_service.generate_answer(
            db=db,
            workspace_id=session.workspace_id,
            query=sanitize_prompt_input(last_user.content).text,
            mode=payload.mode,
            filters=payload.filters,
            memory=memory,
            prior_messages=prior_messages,
        )
        if last_assistant is None:
            saved = self._store_assistant_result(db, session, result, current_user=current_user)
        else:
            saved = self._update_assistant_result(db, session, last_assistant, result, current_user=current_user)
        lead_capture = self.lead_service.evaluate_capture_prompt(
            db,
            session,
            query=sanitize_prompt_input(last_user.content).text,
            confidence=result.confidence,
        )
        if lead_capture.should_prompt and lead_capture.trigger in {"low_confidence", "human_request"}:
            self._mark_needs_human_review(
                db,
                session,
                last_user,
                sanitize_prompt_input(last_user.content).text,
                lead_capture.trigger,
            )
        return result.model_copy(
            update={
                "metadata": result.metadata.model_copy(
                    update={"session_id": session.id, "message_id": saved.id, "lead_capture": lead_capture}
                )
            }
        )

    def submit_feedback(
        self,
        db: Session,
        current_user: User | None,
        payload: ChatFeedbackRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> ChatFeedbackResponse:
        session = self._get_session_for_actor(db, current_user, payload.session_id)
        message = db.scalar(
            select(ChatMessage).where(
                ChatMessage.id == payload.message_id,
                ChatMessage.chat_session_id == session.id,
            )
        )
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat message not found.")
        runtime_setting = self.settings_service.get_setting_for_runtime(db, session.workspace_id)
        analytics_config = runtime_setting.analytics_config_json or {}
        if not analytics_config.get("feedback_collection_enabled", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Feedback collection is disabled for this chatbot.",
            )

        feedback = Feedback(
            workspace_id=session.workspace_id,
            chat_session_id=session.id,
            chat_message_id=message.id,
            user_id=current_user.id if current_user else None,
            rating=1 if payload.value == "up" else -1,
            category=payload.category,
            comment=payload.comment,
        )
        db.add(feedback)
        confidence = message.token_usage_json.get("confidence") if message.token_usage_json else None
        self.event_tracker.track_feedback_submitted(
            db,
            feedback=feedback,
            confidence=confidence,
            response_excerpt=message.content[:500],
        )
        db.commit()
        db.refresh(feedback)
        if feedback.rating < 0 and background_tasks is not None and current_user is not None:
            workspace = db.get(Workspace, session.workspace_id)
            chatbot_setting = db.scalar(select(ChatbotSetting).where(ChatbotSetting.workspace_id == session.workspace_id))
            if workspace is not None:
                self.notification_service.queue_negative_feedback(
                    background_tasks,
                    feedback=feedback,
                    workspace=workspace,
                    chatbot_setting=chatbot_setting,
                    message=message,
                    current_user=current_user,
                )
        return ChatFeedbackResponse(message="Feedback saved successfully.", feedback_id=feedback.id)

    def stop_generation(
        self,
        db: Session,
        current_user: User | None,
        payload: StopGenerationRequest,
    ) -> bool:
        session = self._get_session_for_actor(db, current_user, payload.session_id)
        return self.stop_registry.stop(session.id, payload.generation_id)

    def _serialize_session(self, db: Session, session: ChatSession) -> ChatSessionSummary:
        message_count = db.scalar(
            select(func.count(ChatMessage.id)).where(ChatMessage.chat_session_id == session.id)
        ) or 0
        return ChatSessionSummary(
            id=session.id,
            workspace_id=session.workspace_id,
            user_id=session.user_id,
            title=session.title,
            status=session.status,
            channel=session.channel,
            started_at=session.started_at,
            last_message_at=session.last_message_at,
            session_summary=session.session_summary,
            needs_human_review=session.needs_human_review,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=int(message_count),
        )

    def _get_owned_session(self, db: Session, current_user: User, session_id: uuid.UUID) -> ChatSession:
        session = db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
        get_workspace_member(session.workspace_id, current_user, db)
        return session

    def _get_widget_session(self, db: Session, session_id: uuid.UUID) -> ChatSession:
        session = db.scalar(select(ChatSession).where(ChatSession.id == session_id))
        if not session or session.channel != "widget":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
        return session

    def _get_session_for_actor(self, db: Session, current_user: User | None, session_id: uuid.UUID) -> ChatSession:
        if current_user is not None:
            return self._get_owned_session(db, current_user, session_id)
        return self._get_widget_session(db, session_id)

    def _load_session_messages(self, db: Session, session_id: uuid.UUID) -> list[ChatMessage]:
        return db.scalars(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        ).all()

    def _store_message(
        self,
        db: Session,
        session: ChatSession,
        *,
        role: str,
        content: str,
        citations_json: list | None = None,
        token_usage_json: dict | None = None,
        response_time_ms: int | None = None,
    ) -> ChatMessage:
        timestamp = datetime.now(UTC)
        message = ChatMessage(
            chat_session_id=session.id,
            role=role,
            content=content,
            citations_json=citations_json,
            token_usage_json=token_usage_json,
            response_time_ms=response_time_ms,
            created_at=timestamp,
            updated_at=timestamp,
        )
        session.last_message_at = timestamp
        db.add(message)
        db.flush()
        return message

    def _store_assistant_result(
        self,
        db: Session,
        session: ChatSession,
        result: ChatAnswerResponse,
        generation_id: str | None = None,
        current_user: User | None = None,
    ) -> ChatMessage:
        message = self._store_message(
            db,
            session,
            role="assistant",
            content=result.answer,
            citations_json=[citation.model_dump() for citation in result.citations],
            token_usage_json={
                "confidence": result.confidence,
                "retrieved_chunks": result.metadata.retrieved_chunks,
                "processing_time": result.metadata.processing_time,
                "stopped": result.metadata.stopped,
                "generation_id": generation_id,
                "answer_strategy": result.metadata.answer_strategy,
                "faq_id": str(result.metadata.faq_id) if result.metadata.faq_id else None,
            },
            response_time_ms=result.metadata.processing_time,
        )
        self.event_tracker.track_message_received(
            db,
            session=session,
            current_user=current_user,
            message=message,
            result=result,
            regenerated=False,
        )
        db.commit()
        db.refresh(message)
        db.refresh(session)
        return message

    def _update_assistant_result(
        self,
        db: Session,
        session: ChatSession,
        message: ChatMessage,
        result: ChatAnswerResponse,
        current_user: User | None = None,
    ) -> ChatMessage:
        message.content = result.answer
        message.citations_json = [citation.model_dump() for citation in result.citations]
        message.token_usage_json = {
            "confidence": result.confidence,
            "retrieved_chunks": result.metadata.retrieved_chunks,
            "processing_time": result.metadata.processing_time,
            "stopped": result.metadata.stopped,
            "answer_strategy": result.metadata.answer_strategy,
            "faq_id": str(result.metadata.faq_id) if result.metadata.faq_id else None,
        }
        message.response_time_ms = result.metadata.processing_time
        session.last_message_at = datetime.now(UTC)
        self.event_tracker.track_message_received(
            db,
            session=session,
            current_user=current_user,
            message=message,
            result=result,
            regenerated=True,
        )
        db.commit()
        db.refresh(message)
        return message

    def _ensure_session_title(self, session: ChatSession, message_text: str) -> None:
        if session.title:
            return
        normalized = " ".join(message_text.strip().split())
        session.title = normalized[:80] if normalized else "Untitled chat"

    def _find_last_assistant_after_user(self, messages: list[ChatMessage], user_message_id: uuid.UUID) -> ChatMessage | None:
        for index, message in enumerate(messages):
            if message.id != user_message_id:
                continue
            for follower in messages[index + 1 :]:
                if follower.role == "assistant":
                    return follower
                if follower.role == "user":
                    return None
            return None
        return None

    def _mark_needs_human_review(
        self,
        db: Session,
        session: ChatSession,
        user_message: ChatMessage,
        question: str,
        reason: str,
    ) -> None:
        session.needs_human_review = True
        already_open = db.scalar(
            select(UnresolvedQuestion).where(
                UnresolvedQuestion.chat_session_id == session.id,
                UnresolvedQuestion.chat_message_id == user_message.id,
                UnresolvedQuestion.status == "open",
            )
        )
        if not already_open:
            db.add(
                UnresolvedQuestion(
                    workspace_id=session.workspace_id,
                    chat_session_id=session.id,
                    chat_message_id=user_message.id,
                    question=question,
                    normalized_question=" ".join(question.lower().split())[:500],
                    reason=reason,
                    status="open",
                )
            )
        self.event_tracker.track_unanswered_question(
            db,
            session=session,
            user_message=user_message,
            question=question,
            reason=reason,
        )
        db.commit()
