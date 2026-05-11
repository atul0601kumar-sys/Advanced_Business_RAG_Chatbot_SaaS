from __future__ import annotations

import logging
import re
from io import StringIO
import uuid
from datetime import UTC, datetime, timedelta
import csv

from fastapi import BackgroundTasks
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.dependencies.auth import get_workspace_member
from app.models import Booking, ChatMessage, ChatSession, ChatbotSetting, Lead, MeetingType, UnresolvedQuestion, User, Workspace
from app.schemas.lead import (
    ConversationMessageSummary,
    HumanHandoffResponse,
    LeadCapturePrompt,
    LeadCaptureSettingsResponse,
    LeadCaptureSettingsUpdateRequest,
    LeadCreateRequest,
    LeadDetailResponse,
    LeadExportRequest,
    LeadNoteRequest,
    LeadListResponse,
    LeadSummary,
    LeadStatusUpdateRequest,
    LeadUpdateRequest,
)
from app.services.lead_classifier import LeadClassifier
from app.services.event_tracker import EventTracker
from app.services.notification_service import NotificationService
from app.services.scheduling_intent_detector import SchedulingIntentDetector
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)
settings = get_settings()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HUMAN_REQUEST_TERMS = {"contact", "demo", "support", "sales", "call", "human", "expert"}


class LeadService:
    def __init__(
        self,
        qualification_service: LeadClassifier | None = None,
        notification_service: NotificationService | None = None,
        event_tracker: EventTracker | None = None,
        settings_service: SettingsService | None = None,
        scheduling_intent_detector: SchedulingIntentDetector | None = None,
    ) -> None:
        self.qualification_service = qualification_service or LeadClassifier()
        self.notification_service = notification_service or NotificationService()
        self.event_tracker = event_tracker or EventTracker()
        self.settings_service = settings_service or SettingsService()
        self.scheduling_intent_detector = scheduling_intent_detector or SchedulingIntentDetector()

    def evaluate_capture_prompt(
        self,
        db: Session,
        session: ChatSession,
        *,
        query: str,
        confidence: str,
    ) -> LeadCapturePrompt:
        setting = db.scalar(select(ChatbotSetting).where(ChatbotSetting.workspace_id == session.workspace_id))
        lead_capture_config = (setting.lead_capture_config_json or {}) if setting else {}
        handoff_config = (setting.handoff_config_json or {}) if setting else {}
        custom_form_message = lead_capture_config.get("custom_form_message")
        user_message_count = db.scalar(
            select(func.count(ChatMessage.id)).where(
                ChatMessage.chat_session_id == session.id,
                ChatMessage.role == "user",
            )
        ) or 0
        normalized = " ".join(query.lower().split())
        wants_human = any(term in normalized for term in HUMAN_REQUEST_TERMS)
        scheduling_intent = self.scheduling_intent_detector.detect(query, wants_human_support=wants_human)

        if wants_human or scheduling_intent.detected:
            return LeadCapturePrompt(
                should_prompt=True,
                trigger="human_request" if wants_human else scheduling_intent.reason,
                message=(handoff_config.get("custom_message") or settings.lead_capture_manual_handoff_text),
                schedule_call_enabled=bool(setting and setting.schedule_call_enabled),
                high_intent=True,
                scheduling_intent_detected=scheduling_intent.detected,
            )

        if confidence == "Low" and (setting.lead_capture_on_low_confidence if setting else True):
            return LeadCapturePrompt(
                should_prompt=True,
                trigger="low_confidence",
                message=custom_form_message or "I may not have enough confidence here. Would you like a human expert to contact you?",
                schedule_call_enabled=bool(setting and setting.schedule_call_enabled),
                scheduling_intent_detected=False,
            )

        if setting and setting.force_lead_before_chat and user_message_count == 0:
            return LeadCapturePrompt(
                should_prompt=True,
                trigger="force_before_chat",
                message=setting.lead_auto_response_message or "Please share a couple of details so the right teammate can help from the start.",
                schedule_call_enabled=bool(setting.schedule_call_enabled),
                scheduling_intent_detected=False,
            )

        if setting and setting.lead_capture_enabled:
            if setting.lead_capture_on_first_message and user_message_count == 1:
                return LeadCapturePrompt(
                    should_prompt=True,
                    trigger="first_message",
                    message=custom_form_message or "If you'd like, you can share your contact details and a teammate can follow up.",
                    schedule_call_enabled=bool(setting.schedule_call_enabled),
                    scheduling_intent_detected=False,
                )
            threshold = max(1, setting.lead_capture_after_message_count or settings.lead_capture_default_after_messages)
            if user_message_count == threshold:
                return LeadCapturePrompt(
                    should_prompt=True,
                    trigger="after_n_messages",
                    message=custom_form_message or "It looks like this conversation may need follow-up. Would you like a human expert to contact you?",
                    schedule_call_enabled=bool(setting.schedule_call_enabled),
                    scheduling_intent_detected=False,
                )

        return LeadCapturePrompt(should_prompt=False, schedule_call_enabled=bool(setting and setting.schedule_call_enabled), scheduling_intent_detected=False)

    def register_handoff(
        self,
        db: Session,
        current_user: User,
        *,
        workspace_id: uuid.UUID,
        session_id: uuid.UUID,
        reason: str | None,
        message: str | None,
        background_tasks: BackgroundTasks | None = None,
    ) -> HumanHandoffResponse:
        get_workspace_member(workspace_id, current_user, db)
        session = self._get_session(db, workspace_id, session_id)
        session.needs_human_review = True
        setting = db.scalar(select(ChatbotSetting).where(ChatbotSetting.workspace_id == workspace_id))
        handoff_config = (setting.handoff_config_json or {}) if setting else {}
        workspace = db.get(Workspace, workspace_id)

        latest_user_message = db.scalar(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session.id, ChatMessage.role == "user")
            .order_by(ChatMessage.created_at.desc())
        )
        unresolved = UnresolvedQuestion(
            workspace_id=workspace_id,
            chat_session_id=session.id,
            chat_message_id=latest_user_message.id if latest_user_message else None,
            question=message or (latest_user_message.content if latest_user_message else "Human handoff requested."),
            normalized_question=" ".join((message or (latest_user_message.content if latest_user_message else "")).lower().split())[:500],
            reason=reason or "human_handoff_requested",
            status="open",
        )
        db.add(unresolved)
        db.commit()
        if background_tasks is not None and workspace is not None:
            self.notification_service.queue_handoff_requested(
                background_tasks,
                workspace=workspace,
                chatbot_setting=setting,
                session_id=str(session.id),
                reason=reason,
                user_question=message or (latest_user_message.content if latest_user_message else "Human handoff requested."),
            )
        return HumanHandoffResponse(
            message=(handoff_config.get("custom_message") or settings.lead_capture_manual_handoff_text),
            needs_human_review=True,
            lead_prompt=LeadCapturePrompt(
                should_prompt=True,
                trigger="manual_handoff",
                message=(handoff_config.get("custom_message") or settings.lead_capture_manual_handoff_text),
                schedule_call_enabled=bool(setting and setting.schedule_call_enabled),
                high_intent=True,
                scheduling_intent_detected=True,
            ),
        )

    def create_lead(
        self,
        db: Session,
        current_user: User | None,
        payload: LeadCreateRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> Lead:
        if current_user is not None:
            get_workspace_member(payload.workspace_id, current_user, db)
        self._validate_email(payload.email)
        self._enforce_spam_limit(db, payload.workspace_id, payload.email)

        workspace = db.get(Workspace, payload.workspace_id)
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

        session = None
        repeated_attempts = 0
        chatbot_setting = db.scalar(select(ChatbotSetting).where(ChatbotSetting.workspace_id == payload.workspace_id))
        if payload.chat_session_id:
            session = self._get_session(db, payload.workspace_id, payload.chat_session_id)
            session.needs_human_review = True
            repeated_attempts = db.scalar(
                select(func.count(UnresolvedQuestion.id)).where(UnresolvedQuestion.chat_session_id == session.id)
            ) or 0
        transcript = self._build_transcript(db, payload.chat_session_id) if payload.chat_session_id else []

        qualification = self.qualification_service.qualify(
            message=payload.message or "",
            use_case=payload.use_case,
            repeated_attempts=int(repeated_attempts),
        )

        lead = Lead(
            workspace_id=payload.workspace_id,
            chat_session_id=payload.chat_session_id,
            name=payload.name.strip(),
            email=payload.email.strip().lower(),
            phone=payload.phone.strip() if payload.phone else None,
            company=payload.company.strip() if payload.company else None,
            use_case=payload.use_case.strip() if payload.use_case else None,
            message=(payload.message or "").strip() or None,
            source=payload.source,
            status="new",
            priority=qualification["priority"],
            tag=qualification["tag"],
            high_intent=bool(qualification["high_intent"]),
            metadata_json={
                "priority_score": qualification["score"],
                "schedule_call_requested": payload.schedule_call_requested,
                "admin_notification_email": chatbot_setting.admin_notification_email if chatbot_setting else None,
                "notification_webhook_url": chatbot_setting.notification_webhook_url if chatbot_setting else None,
                "chat_transcript": transcript,
                "auto_response_message": chatbot_setting.lead_auto_response_message if chatbot_setting else None,
                "lead_notifications_enabled": chatbot_setting.lead_notifications_enabled if chatbot_setting else True,
            },
        )
        db.add(lead)
        self.event_tracker.track_lead_created(db, lead=lead, current_user=current_user)
        db.commit()
        db.refresh(lead)
        logger.info("Lead created", extra={"lead_id": str(lead.id), "priority": lead.priority, "tag": lead.tag})
        if background_tasks is not None and (lead.metadata_json or {}).get("lead_notifications_enabled", True):
            self.notification_service.queue_lead_created(
                background_tasks,
                lead=lead,
                workspace=workspace,
                chatbot_setting=chatbot_setting,
            )
        return lead

    def list_leads(
        self,
        db: Session,
        current_user: User,
        *,
        workspace_id: uuid.UUID,
        status_filter: str | None,
        priority_filter: str | None,
        search: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> LeadListResponse:
        get_workspace_member(workspace_id, current_user, db)
        query = select(Lead).where(Lead.workspace_id == workspace_id)
        if status_filter:
            query = query.where(Lead.status == status_filter)
        if priority_filter:
            query = query.where(Lead.priority == priority_filter)
        if search:
            like = f"%{search.strip()}%"
            query = query.where(
                or_(Lead.name.ilike(like), Lead.email.ilike(like), Lead.company.ilike(like), Lead.message.ilike(like))
            )
        if date_from:
            query = query.where(Lead.created_at >= date_from)
        if date_to:
            query = query.where(Lead.created_at <= date_to)
        items = db.scalars(query.order_by(Lead.created_at.desc())).all()
        booked_lead_ids = {
            lead_id
            for lead_id in db.scalars(
                select(Booking.lead_id).where(
                    Booking.workspace_id == workspace_id,
                    Booking.lead_id.is_not(None),
                    Booking.status.in_(["pending", "confirmed", "rescheduled", "completed"]),
                )
            ).all()
            if lead_id is not None
        }
        items.sort(key=lambda item: (item.id not in booked_lead_ids, -item.created_at.timestamp()))
        return LeadListResponse(items=[self.serialize_lead(item) for item in items], total=len(items))

    def export_leads_csv(self, db: Session, current_user: User, payload: LeadExportRequest) -> str:
        listing = self.list_leads(
            db,
            current_user,
            workspace_id=payload.workspace_id,
            status_filter=payload.status,
            priority_filter=payload.priority,
            search=payload.search,
            date_from=payload.date_from,
            date_to=payload.date_to,
        )
        buffer = StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "id",
                "workspace_id",
                "chat_session_id",
                "name",
                "email",
                "phone",
                "company",
                "use_case",
                "message",
                "source",
                "status",
                "priority",
                "tag",
                "high_intent",
                "notes",
                "created_at",
                "updated_at",
                "metadata_json",
            ],
        )
        writer.writeheader()
        for item in listing.items:
            writer.writerow(item.model_dump(mode="json"))
        return buffer.getvalue()

    def get_lead_detail(self, db: Session, current_user: User, *, workspace_id: uuid.UUID, lead_id: uuid.UUID) -> LeadDetailResponse:
        get_workspace_member(workspace_id, current_user, db)
        lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id))
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")
        conversation: list[ConversationMessageSummary] = []
        bookings: list[dict] = []
        if lead.chat_session_id:
            messages = db.scalars(
                select(ChatMessage)
                .where(ChatMessage.chat_session_id == lead.chat_session_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            ).all()
            conversation = [
                ConversationMessageSummary(id=message.id, role=message.role, content=message.content, created_at=message.created_at)
                for message in messages
            ]
        for booking in db.scalars(select(Booking).where(Booking.lead_id == lead.id).order_by(Booking.start_time_utc.desc())).all():
            meeting_type = db.get(MeetingType, booking.meeting_type_id)
            bookings.append(
                {
                    "id": str(booking.id),
                    "meeting_type_title": meeting_type.title if meeting_type else "Meeting",
                    "start_time_utc": booking.start_time_utc.isoformat(),
                    "end_time_utc": booking.end_time_utc.isoformat(),
                    "status": booking.status,
                    "meeting_link": booking.meeting_link,
                    "assigned_user_id": str(booking.assigned_user_id) if booking.assigned_user_id else None,
                }
            )
        return LeadDetailResponse(lead=self.serialize_lead(lead), conversation=conversation, bookings=bookings)

    def update_lead_status(
        self,
        db: Session,
        current_user: User,
        payload: LeadStatusUpdateRequest,
    ) -> LeadSummary:
        return self.update_lead(
            db,
            current_user,
            workspace_id=payload.workspace_id,
            lead_id=payload.lead_id,
            payload=LeadUpdateRequest(status=payload.status),
        )

    def assign_note(
        self,
        db: Session,
        current_user: User,
        payload: LeadNoteRequest,
    ) -> LeadSummary:
        return self.update_lead(
            db,
            current_user,
            workspace_id=payload.workspace_id,
            lead_id=payload.lead_id,
            payload=LeadUpdateRequest(notes=payload.notes),
        )

    def update_lead(
        self,
        db: Session,
        current_user: User,
        *,
        workspace_id: uuid.UUID,
        lead_id: uuid.UUID,
        payload: LeadUpdateRequest,
    ) -> LeadSummary:
        get_workspace_member(workspace_id, current_user, db)
        lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id))
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")
        if payload.status is not None:
            previous_status = lead.status
            lead.status = payload.status
        else:
            previous_status = None
        if payload.priority is not None:
            lead.priority = payload.priority
        if payload.notes is not None:
            lead.notes = payload.notes.strip() or None
        if payload.status == "converted" and previous_status != "converted":
            self.event_tracker.track_lead_converted(
                db,
                lead=lead,
                current_user=current_user,
                previous_status=previous_status,
            )
        db.commit()
        db.refresh(lead)
        return self.serialize_lead(lead)

    def get_settings(self, db: Session, current_user: User, workspace_id: uuid.UUID) -> LeadCaptureSettingsResponse:
        get_workspace_member(workspace_id, current_user, db)
        setting = db.scalar(select(ChatbotSetting).where(ChatbotSetting.workspace_id == workspace_id))
        if not setting:
            setting = ChatbotSetting(
                workspace_id=workspace_id,
                display_name="Workspace Assistant",
                lead_capture_enabled=False,
                lead_capture_on_first_message=False,
                lead_capture_after_message_count=settings.lead_capture_default_after_messages,
                lead_capture_on_low_confidence=True,
                force_lead_before_chat=False,
                lead_required_fields_json=["name", "email"],
                schedule_call_enabled=False,
                lead_notifications_enabled=True,
                lead_auto_response_message="Thanks, our team will follow up shortly.",
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return LeadCaptureSettingsResponse(
            workspace_id=workspace_id,
            lead_capture_enabled=setting.lead_capture_enabled,
            lead_capture_on_first_message=setting.lead_capture_on_first_message,
            lead_capture_after_message_count=setting.lead_capture_after_message_count,
            lead_capture_on_low_confidence=setting.lead_capture_on_low_confidence,
            force_lead_before_chat=setting.force_lead_before_chat,
            required_fields=setting.lead_required_fields_json or ["name", "email"],
            schedule_call_enabled=setting.schedule_call_enabled,
            lead_notifications_enabled=setting.lead_notifications_enabled,
            admin_notification_email=setting.admin_notification_email,
            notification_webhook_url=setting.notification_webhook_url,
            auto_response_message=setting.lead_auto_response_message,
            notification_triggers=setting.notification_triggers_json or {},
            notification_template_overrides=setting.notification_template_overrides_json or {},
        )

    def update_settings(
        self,
        db: Session,
        current_user: User,
        payload: LeadCaptureSettingsUpdateRequest,
    ) -> LeadCaptureSettingsResponse:
        get_workspace_member(payload.workspace_id, current_user, db)
        setting = db.scalar(select(ChatbotSetting).where(ChatbotSetting.workspace_id == payload.workspace_id))
        if not setting:
            setting = ChatbotSetting(
                workspace_id=payload.workspace_id,
                display_name="Workspace Assistant",
            )
            db.add(setting)
            db.flush()
        setting.lead_capture_enabled = payload.lead_capture_enabled
        setting.lead_capture_on_first_message = payload.lead_capture_on_first_message
        setting.lead_capture_after_message_count = payload.lead_capture_after_message_count
        setting.lead_capture_on_low_confidence = payload.lead_capture_on_low_confidence
        setting.force_lead_before_chat = payload.force_lead_before_chat
        setting.lead_required_fields_json = payload.required_fields
        setting.schedule_call_enabled = payload.schedule_call_enabled
        setting.lead_notifications_enabled = payload.lead_notifications_enabled
        setting.admin_notification_email = payload.admin_notification_email.strip() if payload.admin_notification_email else None
        setting.notification_webhook_url = payload.notification_webhook_url.strip() if payload.notification_webhook_url else None
        setting.lead_auto_response_message = payload.auto_response_message.strip() if payload.auto_response_message else None
        setting.notification_triggers_json = {
            key: value.model_dump() for key, value in payload.notification_triggers.items()
        }
        setting.notification_template_overrides_json = {
            key: value.model_dump(exclude_none=True) for key, value in payload.notification_template_overrides.items()
        }
        db.commit()
        return self.get_settings(db, current_user, payload.workspace_id)

    def serialize_lead(self, lead: Lead) -> LeadSummary:
        return LeadSummary(
            id=lead.id,
            workspace_id=lead.workspace_id,
            chat_session_id=lead.chat_session_id,
            name=lead.name,
            email=lead.email,
            phone=lead.phone,
            company=lead.company,
            use_case=lead.use_case,
            message=lead.message,
            source=lead.source,
            status=lead.status,
            priority=lead.priority,
            tag=lead.tag,
            high_intent=lead.high_intent,
            notes=lead.notes,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            metadata_json=lead.metadata_json,
        )

    def _validate_email(self, email: str) -> None:
        if not EMAIL_RE.match(email.strip()):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid email address is required.")

    def _enforce_spam_limit(self, db: Session, workspace_id: uuid.UUID, email: str) -> None:
        recent_count = db.scalar(
            select(func.count(Lead.id)).where(
                Lead.workspace_id == workspace_id,
                Lead.email == email.strip().lower(),
                Lead.created_at >= datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=10),
            )
        ) or 0
        if recent_count >= 3:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Please wait before submitting another lead request.")

    def _build_transcript(self, db: Session, chat_session_id: uuid.UUID | None) -> list[dict]:
        if not chat_session_id:
            return []
        messages = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        ).all()
        return [
            {"role": message.role, "content": message.content, "created_at": message.created_at.isoformat()}
            for message in messages
        ]

    def _get_session(self, db: Session, workspace_id: uuid.UUID, session_id: uuid.UUID) -> ChatSession:
        session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.workspace_id == workspace_id))
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
        return session
