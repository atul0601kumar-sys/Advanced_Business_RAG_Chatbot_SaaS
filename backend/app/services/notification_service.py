from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.dependencies.auth import get_workspace_member
from app.models import (
    ChatMessage,
    ChatbotSetting,
    Feedback,
    Lead,
    NotificationLog,
    User,
    Workspace,
)
from app.services.email_service import EmailDeliveryRequest
from app.schemas.notification import (
    NotificationLogItem,
    NotificationLogsResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
    NotificationTestEmailRequest,
    NotificationWebhookRequest,
)
from app.services.notification_queue import NotificationQueue, shared_notification_queue
from app.services.template_engine import get_template
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)

DEFAULT_TRIGGER_RULES: dict[str, dict[str, Any]] = {
    "lead.created": {"enabled": True, "channels": ["email", "webhook"]},
    "lead.high_priority": {"enabled": True, "channels": ["email", "webhook"]},
    "lead.handoff_requested": {"enabled": True, "channels": ["email", "webhook"]},
    "feedback.negative": {"enabled": True, "channels": ["email", "webhook"]},
    "system.error": {"enabled": False, "channels": ["email", "webhook"]},
    "custom.default": {"enabled": True, "channels": ["webhook"]},
    "notification.test": {"enabled": True, "channels": ["email"]},
}


class NotificationService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        queue: NotificationQueue | None = None,
        webhook_service: WebhookService | None = None,
        session_factory=SessionLocal,
    ) -> None:
        self.settings = settings or get_settings()
        self.queue = queue or shared_notification_queue
        self.webhook_service = webhook_service or WebhookService(settings=self.settings)
        self.session_factory = session_factory

    def queue_lead_created(
        self,
        background_tasks: BackgroundTasks,
        *,
        lead: Lead,
        workspace: Workspace,
        chatbot_setting: ChatbotSetting | None,
    ) -> None:
        background_tasks.add_task(
            self.enqueue_lead_created,
            self._serialize_lead(lead),
            self._serialize_workspace(workspace),
            self._serialize_chatbot_setting(chatbot_setting),
        )

    def enqueue_lead_created(
        self,
        lead_data: dict[str, Any],
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
    ) -> int:
        envelopes = self._build_lead_created_envelopes(
            lead_data=lead_data,
            workspace_data=workspace_data,
            setting_data=setting_data,
        )
        return self._persist_envelopes(envelopes, uuid.UUID(workspace_data["id"]), setting_data)

    def send_lead_created(
        self,
        lead_data: dict[str, Any],
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
    ) -> None:
        envelopes = self._build_lead_created_envelopes(
            lead_data=lead_data,
            workspace_data=workspace_data,
            setting_data=setting_data,
        )
        self._dispatch_immediately(envelopes)

    def queue_handoff_requested(
        self,
        background_tasks: BackgroundTasks,
        *,
        workspace: Workspace,
        chatbot_setting: ChatbotSetting | None,
        session_id: str,
        reason: str | None,
        user_question: str,
    ) -> None:
        background_tasks.add_task(
            self.enqueue_handoff_requested,
            self._serialize_workspace(workspace),
            self._serialize_chatbot_setting(chatbot_setting),
            {
                "session_id": session_id,
                "reason": reason or "human_handoff_requested",
                "user_question": user_question,
            },
        )

    def enqueue_handoff_requested(
        self,
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        handoff_data: dict[str, Any],
    ) -> int:
        envelopes = self._build_handoff_envelopes(workspace_data, setting_data, handoff_data)
        return self._persist_envelopes(envelopes, uuid.UUID(workspace_data["id"]), setting_data)

    def send_handoff_requested(
        self,
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        handoff_data: dict[str, Any],
    ) -> None:
        self._dispatch_immediately(self._build_handoff_envelopes(workspace_data, setting_data, handoff_data))

    def queue_negative_feedback(
        self,
        background_tasks: BackgroundTasks,
        *,
        feedback: Feedback,
        workspace: Workspace,
        chatbot_setting: ChatbotSetting | None,
        message: ChatMessage,
        current_user: User,
    ) -> None:
        background_tasks.add_task(
            self.enqueue_negative_feedback,
            self._serialize_feedback(feedback),
            self._serialize_workspace(workspace),
            self._serialize_chatbot_setting(chatbot_setting),
            self._serialize_chat_message(message),
            self._serialize_user(current_user),
        )

    def enqueue_negative_feedback(
        self,
        feedback_data: dict[str, Any],
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        message_data: dict[str, Any],
        user_data: dict[str, Any],
    ) -> int:
        envelopes = self._build_feedback_envelopes(
            feedback_data,
            workspace_data,
            setting_data,
            message_data,
            user_data,
        )
        return self._persist_envelopes(envelopes, uuid.UUID(workspace_data["id"]), setting_data)

    def send_negative_feedback(
        self,
        feedback_data: dict[str, Any],
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        message_data: dict[str, Any],
        user_data: dict[str, Any],
    ) -> None:
        self._dispatch_immediately(
            self._build_feedback_envelopes(feedback_data, workspace_data, setting_data, message_data, user_data)
        )

    def queue_system_error(
        self,
        background_tasks: BackgroundTasks,
        *,
        workspace: Workspace,
        chatbot_setting: ChatbotSetting | None,
        error_title: str,
        error_details: str,
    ) -> None:
        background_tasks.add_task(
            self.enqueue_system_error,
            self._serialize_workspace(workspace),
            self._serialize_chatbot_setting(chatbot_setting),
            {"error_title": error_title, "error_details": error_details},
        )

    def enqueue_system_error(
        self,
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        error_data: dict[str, Any],
    ) -> int:
        envelopes = self._build_system_error_envelopes(workspace_data, setting_data, error_data)
        return self._persist_envelopes(envelopes, uuid.UUID(workspace_data["id"]), setting_data)

    def queue_custom_trigger(
        self,
        background_tasks: BackgroundTasks,
        *,
        workspace: Workspace,
        chatbot_setting: ChatbotSetting | None,
        trigger_name: str,
        summary: str,
        details: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        background_tasks.add_task(
            self.enqueue_custom_trigger,
            self._serialize_workspace(workspace),
            self._serialize_chatbot_setting(chatbot_setting),
            {
                "trigger_name": trigger_name,
                "summary": summary,
                "details": details,
                "payload": payload or {},
            },
        )

    def enqueue_custom_trigger(
        self,
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        trigger_data: dict[str, Any],
    ) -> int:
        envelopes = self._build_custom_envelopes(workspace_data, setting_data, trigger_data)
        return self._persist_envelopes(envelopes, uuid.UUID(workspace_data["id"]), setting_data)

    def send_custom_trigger(
        self,
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        trigger_data: dict[str, Any],
    ) -> None:
        self._dispatch_immediately(self._build_custom_envelopes(workspace_data, setting_data, trigger_data))

    def get_settings(self, db: Session, current_user: User, workspace_id: uuid.UUID) -> NotificationSettingsResponse:
        self._require_admin(workspace_id, current_user, db)
        setting = self._get_or_create_setting(db, workspace_id)
        return NotificationSettingsResponse(
            workspace_id=workspace_id,
            notifications_enabled=setting.notifications_enabled,
            email_recipients=setting.notification_email_recipients_json or self._default_admin_recipients(self._serialize_chatbot_setting(setting)),
            webhook_urls=setting.notification_webhook_urls_json or self._default_webhook_urls(self._serialize_chatbot_setting(setting)),
            retry_attempts=setting.notification_retry_attempts,
            rate_limit_count=setting.notification_rate_limit_count,
            rate_limit_window_seconds=setting.notification_rate_limit_window_seconds,
            event_rules=setting.notification_triggers_json or {},
            template_overrides=setting.notification_template_overrides_json or {},
        )

    def update_settings(
        self,
        db: Session,
        current_user: User,
        payload: NotificationSettingsUpdateRequest,
    ) -> NotificationSettingsResponse:
        self._require_admin(payload.workspace_id, current_user, db)
        self._validate_email_recipients(payload.email_recipients)
        self._validate_webhook_urls(payload.webhook_urls)
        for rule in payload.event_rules.values():
            self._validate_email_recipients(rule.email_recipients)
            self._validate_webhook_urls(rule.webhook_urls)
        setting = self._get_or_create_setting(db, payload.workspace_id)
        setting.notifications_enabled = payload.notifications_enabled
        setting.notification_email_recipients_json = payload.email_recipients
        setting.notification_webhook_urls_json = payload.webhook_urls
        setting.notification_retry_attempts = payload.retry_attempts
        setting.notification_rate_limit_count = payload.rate_limit_count
        setting.notification_rate_limit_window_seconds = payload.rate_limit_window_seconds
        setting.notification_triggers_json = {key: value.model_dump() for key, value in payload.event_rules.items()}
        setting.notification_template_overrides_json = {
            key: value.model_dump(exclude_none=True) for key, value in payload.template_overrides.items()
        }
        db.commit()
        return self.get_settings(db, current_user, payload.workspace_id)

    def list_logs(
        self,
        db: Session,
        current_user: User,
        *,
        workspace_id: uuid.UUID,
        limit: int = 50,
    ) -> NotificationLogsResponse:
        self._require_admin(workspace_id, current_user, db)
        logs = db.scalars(
            select(NotificationLog)
            .where(NotificationLog.workspace_id == workspace_id)
            .order_by(NotificationLog.updated_at.desc())
            .limit(limit)
        ).all()
        return NotificationLogsResponse(
            items=[
                NotificationLogItem(
                    id=log.id,
                    notification_id=log.notification_id,
                    type=log.type,
                    channel=log.channel,
                    status=log.status,
                    error_message=log.error_message,
                    retry_count=log.retry_count,
                    response_code=log.response_code,
                    response_body=log.response_body,
                    target=log.target,
                    timestamp=log.updated_at,
                )
                for log in logs
            ],
            total=len(logs),
        )

    def queue_test_email(self, db: Session, current_user: User, payload: NotificationTestEmailRequest) -> int:
        self._require_admin(payload.workspace_id, current_user, db)
        setting = self._get_or_create_setting(db, payload.workspace_id)
        recipients = payload.to_addresses or (setting.notification_email_recipients_json or [])
        self._validate_email_recipients(recipients)
        if not recipients:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No email recipients configured.")
        workspace = db.get(Workspace, payload.workspace_id)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        setting_data = self._serialize_chatbot_setting(setting)
        envelopes = [
            self._build_email_job_payload(
                event_name="notification.test",
                template_id="notification.test",
                context={"workspace_name": workspace.name},
                to_addresses=recipients,
                template_override=((setting.notification_template_overrides_json or {}).get("notification.test")),
                dedupe_key="",
            )
        ]
        return self._persist_envelopes(envelopes, workspace.id, setting_data)

    def queue_manual_webhook(self, db: Session, current_user: User, payload: NotificationWebhookRequest) -> int:
        self._require_admin(payload.workspace_id, current_user, db)
        setting = self._get_or_create_setting(db, payload.workspace_id)
        targets = payload.webhook_urls or (setting.notification_webhook_urls_json or [])
        self._validate_webhook_urls(targets)
        if not targets:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No webhook URLs configured.")
        workspace = db.get(Workspace, payload.workspace_id)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        setting_data = self._serialize_chatbot_setting(setting)
        envelopes = [
            self._build_webhook_job_payload(
                event_name=payload.event_name,
                payload={"event": payload.event_name, "workspace": self._serialize_workspace(workspace), "data": payload.payload},
                target=url,
                dedupe_key="",
            )
            for url in targets
        ]
        return self._persist_envelopes(envelopes, workspace.id, setting_data)

    def _build_lead_created_envelopes(
        self,
        *,
        lead_data: dict[str, Any],
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        base_context = {
            "workspace_name": workspace_data["name"],
            "lead_name": lead_data.get("name") or lead_data.get("email") or "New lead",
            "lead_email": lead_data.get("email") or "",
            "lead_phone": lead_data.get("phone") or "Not provided",
            "lead_company": lead_data.get("company") or "Not provided",
            "lead_message": lead_data.get("message") or "No message provided.",
            "lead_priority": (lead_data.get("priority") or "").upper(),
            "dashboard_url": self._leads_dashboard_url(),
            "chat_dashboard_url": self._chat_dashboard_url(),
        }
        payload = {"event": "lead_created", "workspace": workspace_data, "lead": lead_data}
        envelopes: list[dict[str, Any]] = []
        admin_email = self._build_email_job_payload(
            event_name="lead.created",
            template_id="lead.created.admin",
            context=base_context,
            to_addresses=self._event_email_recipients("lead.created", setting_data),
            template_override=self._template_override("lead.created.admin", setting_data),
            dedupe_key=f"lead.created:email:{lead_data['id']}",
        )
        admin_webhooks = self._build_webhook_job_payloads(
            event_name="lead.created",
            payload=payload,
            urls=self._event_webhook_urls("lead.created", setting_data),
            dedupe_prefix=f"lead.created:webhook:{lead_data['id']}",
        )
        if admin_email is not None:
            envelopes.append(admin_email)
        envelopes.extend(admin_webhooks)

        if (lead_data.get("priority") or "").lower() == "high":
            high_email = self._build_email_job_payload(
                event_name="lead.high_priority",
                template_id="lead.high_priority.admin",
                context=base_context,
                to_addresses=self._event_email_recipients("lead.high_priority", setting_data),
                template_override=self._template_override("lead.high_priority.admin", setting_data),
                dedupe_key=f"lead.high_priority:email:{lead_data['id']}",
            )
            high_webhooks = self._build_webhook_job_payloads(
                event_name="lead.high_priority",
                payload={**payload, "event": "high_priority_lead"},
                urls=self._event_webhook_urls("lead.high_priority", setting_data),
                dedupe_prefix=f"lead.high_priority:webhook:{lead_data['id']}",
            )
            if high_email is not None:
                envelopes.append(high_email)
            envelopes.extend(high_webhooks)

        if lead_data.get("email"):
            user_email = self._build_email_job_payload(
                event_name="lead.user_confirmation",
                template_id="lead.user_confirmation",
                context=base_context,
                to_addresses=[lead_data["email"]],
                template_override=self._template_override("lead.user_confirmation", setting_data),
                dedupe_key=f"lead.user_confirmation:{lead_data['id']}",
            )
            if user_email is not None:
                envelopes.append(user_email)
        return envelopes

    def _build_handoff_envelopes(
        self,
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        handoff_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        context = {
            "workspace_name": workspace_data["name"],
            "session_id": handoff_data["session_id"],
            "handoff_reason": handoff_data.get("reason") or "human_handoff_requested",
            "user_question": handoff_data.get("user_question") or "",
            "chat_session_url": self._chat_session_url(handoff_data["session_id"]),
        }
        email_job = self._build_email_job_payload(
            event_name="lead.handoff_requested",
            template_id="lead.handoff.admin",
            context=context,
            to_addresses=self._event_email_recipients("lead.handoff_requested", setting_data),
            template_override=self._template_override("lead.handoff.admin", setting_data),
            dedupe_key=f"lead.handoff_requested:email:{handoff_data['session_id']}",
        )
        webhook_jobs = self._build_webhook_job_payloads(
            event_name="lead.handoff_requested",
            payload={"event": "handoff_requested", "workspace": workspace_data, "handoff": handoff_data},
            urls=self._event_webhook_urls("lead.handoff_requested", setting_data),
            dedupe_prefix=f"lead.handoff_requested:webhook:{handoff_data['session_id']}",
        )
        items = []
        if email_job is not None:
            items.append(email_job)
        items.extend(webhook_jobs)
        return items

    def _build_feedback_envelopes(
        self,
        feedback_data: dict[str, Any],
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        message_data: dict[str, Any],
        user_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        context = {
            "workspace_name": workspace_data["name"],
            "user_email": user_data.get("email") or "unknown",
            "feedback_category": feedback_data.get("category") or "uncategorized",
            "feedback_comment": feedback_data.get("comment") or "No comment provided.",
            "message_context": message_data.get("content") or "",
            "chat_session_url": self._chat_session_url(feedback_data.get("chat_session_id")),
        }
        email_job = self._build_email_job_payload(
            event_name="feedback.negative",
            template_id="feedback.negative.admin",
            context=context,
            to_addresses=self._event_email_recipients("feedback.negative", setting_data),
            template_override=self._template_override("feedback.negative.admin", setting_data),
            dedupe_key=f"feedback.negative:email:{feedback_data['id']}",
        )
        webhook_jobs = self._build_webhook_job_payloads(
            event_name="feedback.negative",
            payload={
                "event": "feedback_submitted",
                "workspace": workspace_data,
                "feedback": feedback_data,
                "message": message_data,
                "user": user_data,
            },
            urls=self._event_webhook_urls("feedback.negative", setting_data),
            dedupe_prefix=f"feedback.negative:webhook:{feedback_data['id']}",
        )
        items = []
        if email_job is not None:
            items.append(email_job)
        items.extend(webhook_jobs)
        return items

    def _build_system_error_envelopes(
        self,
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        error_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        context = {
            "workspace_name": workspace_data["name"],
            "error_title": error_data["error_title"],
            "error_details": error_data["error_details"],
        }
        email_job = self._build_email_job_payload(
            event_name="system.error",
            template_id="system.error.admin",
            context=context,
            to_addresses=self._event_email_recipients("system.error", setting_data),
            template_override=self._template_override("system.error.admin", setting_data),
            dedupe_key=f"system.error:email:{workspace_data['id']}:{error_data['error_title']}",
        )
        webhook_jobs = self._build_webhook_job_payloads(
            event_name="system.error",
            payload={"event": "system_error", "workspace": workspace_data, "error": error_data},
            urls=self._event_webhook_urls("system.error", setting_data),
            dedupe_prefix=f"system.error:webhook:{workspace_data['id']}:{error_data['error_title']}",
        )
        items = []
        if email_job is not None:
            items.append(email_job)
        items.extend(webhook_jobs)
        return items

    def _build_custom_envelopes(
        self,
        workspace_data: dict[str, Any],
        setting_data: dict[str, Any] | None,
        trigger_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        event_name = f"custom.{trigger_data['trigger_name']}"
        context = {
            "workspace_name": workspace_data["name"],
            "event_name": event_name,
            "event_summary": trigger_data["summary"],
            "event_details": trigger_data["details"],
        }
        email_job = self._build_email_job_payload(
            event_name=event_name,
            template_id="custom.event.admin",
            context=context,
            to_addresses=self._event_email_recipients(event_name, setting_data),
            template_override=self._template_override("custom.event.admin", setting_data),
            dedupe_key=f"{event_name}:email:{workspace_data['id']}:{trigger_data['summary']}",
        )
        webhook_jobs = self._build_webhook_job_payloads(
            event_name=event_name,
            payload={"event": event_name, "workspace": workspace_data, "details": trigger_data},
            urls=self._event_webhook_urls(event_name, setting_data),
            dedupe_prefix=f"{event_name}:webhook:{workspace_data['id']}:{trigger_data['summary']}",
        )
        items = []
        if email_job is not None:
            items.append(email_job)
        items.extend(webhook_jobs)
        return items

    def _build_email_job_payload(
        self,
        *,
        event_name: str,
        template_id: str,
        context: dict[str, Any],
        to_addresses: list[str],
        template_override: dict[str, Any] | None,
        dedupe_key: str,
    ) -> dict[str, Any] | None:
        rule = self._trigger_rule(event_name, None)
        if not to_addresses:
            return None
        return {
            "channel": "email",
            "event_name": event_name,
            "payload": {
                "template_id": template_id,
                "context": context,
                "to_addresses": to_addresses,
                "template_override": template_override,
            },
            "dedupe_key": dedupe_key,
            "target": ",".join(sorted(to_addresses)),
        }

    def _build_webhook_job_payloads(
        self,
        *,
        event_name: str,
        payload: dict[str, Any],
        urls: list[str],
        dedupe_prefix: str,
    ) -> list[dict[str, Any]]:
        return [
            self._build_webhook_job_payload(
                event_name=event_name,
                payload=payload,
                target=url,
                dedupe_key=f"{dedupe_prefix}:{url}",
            )
            for url in urls
        ]

    def _build_webhook_job_payload(
        self,
        *,
        event_name: str,
        payload: dict[str, Any],
        target: str,
        dedupe_key: str,
    ) -> dict[str, Any]:
        return {
            "channel": "webhook",
            "event_name": event_name,
            "payload": payload,
            "dedupe_key": dedupe_key,
            "target": target,
        }

    def _persist_envelopes(
        self,
        envelopes: list[dict[str, Any]],
        workspace_id: uuid.UUID,
        setting_data: dict[str, Any] | None,
    ) -> int:
        if not self._notifications_enabled(setting_data):
            return 0
        queued = 0
        with self.session_factory() as db:
            for envelope in envelopes:
                if not self._event_enabled(envelope["event_name"], setting_data):
                    continue
                if not self._channel_enabled(envelope["event_name"], envelope["channel"], setting_data):
                    continue
                job = self.queue.enqueue_job(
                    db,
                    workspace_id=workspace_id,
                    event_name=envelope["event_name"],
                    channel=envelope["channel"],
                    payload=envelope["payload"],
                    dedupe_key=envelope.get("dedupe_key"),
                    max_retries=self._retry_attempts(setting_data),
                    target=envelope.get("target"),
                    rate_limit_count=self._rate_limit_count(setting_data),
                    rate_limit_window_seconds=self._rate_limit_window_seconds(setting_data),
                )
                if job is not None:
                    queued += 1
            db.commit()
        return queued

    def _dispatch_immediately(self, envelopes: list[dict[str, Any]]) -> None:
        # This path is kept for tests and local verification. Production flows queue jobs instead.
        for envelope in envelopes:
            if envelope["channel"] == "email":
                rendered = get_template(envelope["payload"]["template_id"]).render(
                    envelope["payload"]["context"],
                    envelope["payload"].get("template_override"),
                )
                self.queue.email_service.send(
                    EmailDeliveryRequest(
                        to_addresses=envelope["payload"]["to_addresses"],
                        subject=rendered.subject,
                        text_body=rendered.text_body,
                        html_body=rendered.html_body,
                        reply_to=envelope["payload"].get("reply_to"),
                    )
                )
            elif envelope["channel"] == "webhook":
                self.queue.webhook_service.send(envelope["target"], envelope["payload"])

    def _notifications_enabled(self, setting_data: dict[str, Any] | None) -> bool:
        if setting_data is None:
            return True
        return bool(setting_data.get("notifications_enabled", setting_data.get("lead_notifications_enabled", True)))

    def _trigger_rule(self, event_name: str, setting_data: dict[str, Any] | None) -> dict[str, Any]:
        rules = (setting_data or {}).get("notification_triggers") or {}
        if event_name in rules:
            return {**DEFAULT_TRIGGER_RULES.get(event_name, DEFAULT_TRIGGER_RULES.get("custom.default", {})), **rules[event_name]}
        if event_name.startswith("custom."):
            return dict(DEFAULT_TRIGGER_RULES["custom.default"])
        return dict(DEFAULT_TRIGGER_RULES.get(event_name, {"enabled": True, "channels": ["email", "webhook"]}))

    def _event_enabled(self, event_name: str, setting_data: dict[str, Any] | None) -> bool:
        return bool(self._trigger_rule(event_name, setting_data).get("enabled", True))

    def _channel_enabled(self, event_name: str, channel: str, setting_data: dict[str, Any] | None) -> bool:
        channels = self._normalize_string_list(self._trigger_rule(event_name, setting_data).get("channels"))
        return not channels or channel in channels

    def _event_email_recipients(self, event_name: str, setting_data: dict[str, Any] | None) -> list[str]:
        rule = self._trigger_rule(event_name, setting_data)
        recipients = self._normalize_string_list(rule.get("email_recipients"))
        if recipients:
            return recipients
        return self._normalize_string_list(
            (setting_data or {}).get("notification_email_recipients")
        ) or self._default_admin_recipients(setting_data)

    def _event_webhook_urls(self, event_name: str, setting_data: dict[str, Any] | None) -> list[str]:
        rule = self._trigger_rule(event_name, setting_data)
        urls = self._normalize_string_list(rule.get("webhook_urls"))
        if urls:
            return urls
        return self._normalize_string_list(
            (setting_data or {}).get("notification_webhook_urls")
        ) or self._default_webhook_urls(setting_data)

    def _template_override(self, template_id: str, setting_data: dict[str, Any] | None) -> dict[str, Any] | None:
        return ((setting_data or {}).get("notification_template_overrides") or {}).get(template_id)

    def _retry_attempts(self, setting_data: dict[str, Any] | None) -> int:
        if setting_data is None:
            return self.settings.notification_email_max_retries
        return int(setting_data.get("notification_retry_attempts", self.settings.notification_email_max_retries))

    def _rate_limit_count(self, setting_data: dict[str, Any] | None) -> int:
        if setting_data is None:
            return 20
        return int(setting_data.get("notification_rate_limit_count", 20))

    def _rate_limit_window_seconds(self, setting_data: dict[str, Any] | None) -> int:
        if setting_data is None:
            return 60
        return int(setting_data.get("notification_rate_limit_window_seconds", 60))

    def _get_or_create_setting(self, db: Session, workspace_id: uuid.UUID) -> ChatbotSetting:
        setting = db.scalar(select(ChatbotSetting).where(ChatbotSetting.workspace_id == workspace_id))
        if setting is None:
            setting = ChatbotSetting(
                workspace_id=workspace_id,
                display_name="Workspace Assistant",
                lead_capture_enabled=False,
                lead_capture_on_first_message=False,
                lead_capture_after_message_count=4,
                lead_capture_on_low_confidence=True,
                force_lead_before_chat=False,
                lead_required_fields_json=["name", "email"],
                schedule_call_enabled=False,
                lead_notifications_enabled=True,
                notifications_enabled=True,
                notification_retry_attempts=3,
                notification_rate_limit_count=20,
                notification_rate_limit_window_seconds=60,
                lead_auto_response_message="Thanks, our team will follow up shortly.",
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return setting

    def _require_admin(self, workspace_id: uuid.UUID, current_user: User, db: Session) -> None:
        membership = get_workspace_member(workspace_id, current_user, db)
        if membership.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")

    def _validate_email_recipients(self, recipients: list[str]) -> None:
        invalid = [item for item in recipients if "@" not in item]
        if invalid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email recipient provided.")

    def _validate_webhook_urls(self, urls: list[str]) -> None:
        for url in urls:
            try:
                self.webhook_service.validate_url(url)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    def _default_admin_recipients(self, setting_data: dict[str, Any] | None) -> list[str]:
        value = (setting_data or {}).get("admin_notification_email")
        return [value] if value else []

    def _default_webhook_urls(self, setting_data: dict[str, Any] | None) -> list[str]:
        default_url = (setting_data or {}).get("notification_webhook_url") or self.settings.admin_notification_webhook_url
        return [default_url] if default_url else []

    def _leads_dashboard_url(self) -> str:
        return f"{self.settings.frontend_url}/dashboard/leads"

    def _chat_dashboard_url(self) -> str:
        return f"{self.settings.frontend_url}/dashboard/chat"

    def _chat_session_url(self, session_id: str | None) -> str:
        if not session_id:
            return self._chat_dashboard_url()
        return f"{self.settings.frontend_url}/dashboard/chat-history?sessionId={session_id}"

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _serialize_workspace(workspace: Workspace) -> dict[str, Any]:
        return {"id": str(workspace.id), "name": workspace.name, "slug": workspace.slug}

    @staticmethod
    def _serialize_chatbot_setting(chatbot_setting: ChatbotSetting | None) -> dict[str, Any] | None:
        if chatbot_setting is None:
            return None
        return {
            "lead_notifications_enabled": chatbot_setting.lead_notifications_enabled,
            "admin_notification_email": chatbot_setting.admin_notification_email,
            "notification_webhook_url": chatbot_setting.notification_webhook_url,
            "notifications_enabled": chatbot_setting.notifications_enabled,
            "notification_email_recipients": chatbot_setting.notification_email_recipients_json or [],
            "notification_webhook_urls": chatbot_setting.notification_webhook_urls_json or [],
            "notification_retry_attempts": chatbot_setting.notification_retry_attempts,
            "notification_rate_limit_count": chatbot_setting.notification_rate_limit_count,
            "notification_rate_limit_window_seconds": chatbot_setting.notification_rate_limit_window_seconds,
            "notification_triggers": chatbot_setting.notification_triggers_json or {},
            "notification_template_overrides": chatbot_setting.notification_template_overrides_json or {},
        }

    @staticmethod
    def _serialize_lead(lead: Lead) -> dict[str, Any]:
        return {
            "id": str(lead.id),
            "workspace_id": str(lead.workspace_id),
            "chat_session_id": str(lead.chat_session_id) if lead.chat_session_id else None,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company,
            "message": lead.message,
            "priority": lead.priority,
            "tag": lead.tag,
            "high_intent": lead.high_intent,
        }

    @staticmethod
    def _serialize_feedback(feedback: Feedback) -> dict[str, Any]:
        return {
            "id": str(feedback.id),
            "workspace_id": str(feedback.workspace_id),
            "chat_session_id": str(feedback.chat_session_id) if feedback.chat_session_id else None,
            "chat_message_id": str(feedback.chat_message_id) if feedback.chat_message_id else None,
            "rating": feedback.rating,
            "category": feedback.category,
            "comment": feedback.comment,
        }

    @staticmethod
    def _serialize_chat_message(message: ChatMessage) -> dict[str, Any]:
        return {"id": str(message.id), "role": message.role, "content": message.content}

    @staticmethod
    def _serialize_user(user: User) -> dict[str, Any]:
        return {"id": str(user.id), "email": user.email, "full_name": user.full_name}
