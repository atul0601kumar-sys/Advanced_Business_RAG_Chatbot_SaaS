from __future__ import annotations

from datetime import UTC, datetime
import time
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies.auth import get_workspace_member
from app.models import ChatbotSetting, User
from app.schemas.settings import (
    AccessControlSettings,
    AnalyticsPreferencesSettings,
    ChatBehaviorSettings,
    ChatbotIdentitySettings,
    ChatbotSettingsResponse,
    ChatbotSettingsUpdateRequest,
    HumanHandoffSettings,
    KnowledgeBaseSettings,
    LeadCaptureCustomizationSettings,
    NotificationChannelSettings,
    PromptCustomizationSettings,
    PublicChatbotSettingsResponse,
    VoiceSettings,
    WidgetCustomizationSettings,
)
from app.services.settings_validator import SettingsValidator
from app.services.widget_auth import WidgetAuthService
from app.services.widget_configurator import WidgetConfigurator


def build_default_settings_payload(
    workspace_id: uuid.UUID,
    *,
    setting: ChatbotSetting | None = None,
) -> ChatbotSettingsResponse:
    display_name = setting.display_name if setting else "Workspace Assistant"
    welcome_message = (
        setting.welcome_message
        if setting and setting.welcome_message
        else "Ask grounded questions about your documents and website sources. I will answer only from indexed knowledge and cite my sources."
    )
    identity = ChatbotIdentitySettings(
        bot_name=(setting.identity_config_json or {}).get("bot_name") if setting and setting.identity_config_json else display_name,
        bot_avatar=(setting.identity_config_json or {}).get("bot_avatar") if setting and setting.identity_config_json else None,
        brand_color_primary=(setting.identity_config_json or {}).get("brand_color_primary") if setting and setting.identity_config_json else "#0ea5e9",
        brand_color_secondary=(setting.identity_config_json or {}).get("brand_color_secondary") if setting and setting.identity_config_json else "#0369a1",
        logo=(setting.identity_config_json or {}).get("logo") if setting and setting.identity_config_json else None,
        tagline=(setting.identity_config_json or {}).get("tagline") if setting and setting.identity_config_json else "Grounded answers for your business knowledge",
        welcome_message=(setting.identity_config_json or {}).get("welcome_message") if setting and setting.identity_config_json else welcome_message,
    )
    behavior = ChatBehaviorSettings(
        **((setting.behavior_config_json or {}) if setting else {})
    )
    prompt = PromptCustomizationSettings(
        custom_system_prompt=setting.system_prompt if setting and setting.system_prompt else ((setting.prompt_config_json or {}).get("custom_system_prompt") if setting and setting.prompt_config_json else None),
        company_instructions=((setting.prompt_config_json or {}).get("company_instructions") if setting and setting.prompt_config_json else None),
        business_rules=((setting.prompt_config_json or {}).get("business_rules") if setting and setting.prompt_config_json else None),
    )
    lead_capture = LeadCaptureCustomizationSettings(
        enabled=setting.lead_capture_enabled if setting else False,
        force_before_chat=setting.force_lead_before_chat if setting else False,
        trigger_on_first_message=setting.lead_capture_on_first_message if setting else False,
        trigger_on_low_confidence=setting.lead_capture_on_low_confidence if setting else True,
        trigger_after_n_messages=setting.lead_capture_after_message_count if setting else 4,
        required_fields=(setting.lead_required_fields_json or ["name", "email"]) if setting else ["name", "email"],
        custom_form_message=((setting.lead_capture_config_json or {}).get("custom_form_message") if setting and setting.lead_capture_config_json else None),
        auto_response_message=setting.lead_auto_response_message if setting else "Thanks, our team will be in touch shortly.",
    )
    handoff = HumanHandoffSettings(
        enabled=((setting.handoff_config_json or {}).get("enabled") if setting and setting.handoff_config_json else True),
        custom_message=((setting.handoff_config_json or {}).get("custom_message") if setting and setting.handoff_config_json else "A human teammate can take over from here."),
        enable_scheduling=setting.schedule_call_enabled if setting else False,
        escalate_on_low_confidence=((setting.handoff_config_json or {}).get("escalate_on_low_confidence") if setting and setting.handoff_config_json else True),
        escalate_on_repeated_failures=((setting.handoff_config_json or {}).get("escalate_on_repeated_failures") if setting and setting.handoff_config_json else True),
    )
    voice = VoiceSettings(**((setting.voice_config_json or {}) if setting else {}))
    widget_payload = ((setting.widget_config_json or {}) if setting else {}).copy()
    if setting and setting.allowed_domains_json is not None:
        widget_payload["allowed_origins"] = setting.allowed_domains_json
    widget = WidgetCustomizationSettings(**widget_payload)
    access_control = AccessControlSettings(**((setting.access_control_config_json or {}) if setting else {}))
    knowledge_base = KnowledgeBaseSettings(**((setting.knowledge_base_config_json or {}) if setting else {}))
    analytics = AnalyticsPreferencesSettings(**((setting.analytics_config_json or {}) if setting else {}))
    notifications = NotificationChannelSettings(
        enabled=setting.notifications_enabled if setting else True,
        notification_types=list((setting.notification_triggers_json or {}).keys()) if setting and setting.notification_triggers_json else ["new_lead", "high_priority_lead", "handoff_requested", "negative_feedback"],
        email_recipients=(setting.notification_email_recipients_json or []) if setting else [],
        webhook_endpoints=(setting.notification_webhook_urls_json or []) if setting else [],
        retry_attempts=setting.notification_retry_attempts if setting else 3,
        triggers=(setting.notification_triggers_json or {}) if setting else {},
        template_overrides=(setting.notification_template_overrides_json or {}) if setting else {},
    )
    return ChatbotSettingsResponse(
        workspace_id=workspace_id,
        identity=identity,
        behavior=behavior,
        prompt=prompt,
        lead_capture=lead_capture,
        handoff=handoff,
        voice=voice,
        widget=widget,
        access_control=access_control,
        knowledge_base=knowledge_base,
        analytics=analytics,
        notifications=notifications,
        updated_at=setting.updated_at if setting else datetime.now(UTC),
    )


class SettingsService:
    _cache: dict[str, tuple[float, ChatbotSettingsResponse]] = {}
    _ttl_seconds = 30.0

    def __init__(
        self,
        validator: SettingsValidator | None = None,
        widget_configurator: WidgetConfigurator | None = None,
        widget_auth_service: WidgetAuthService | None = None,
    ) -> None:
        self.validator = validator or SettingsValidator()
        self.widget_configurator = widget_configurator or WidgetConfigurator()
        self.widget_auth_service = widget_auth_service or WidgetAuthService()

    def get_settings(self, db: Session, current_user: User, workspace_id: uuid.UUID) -> ChatbotSettingsResponse:
        get_workspace_member(workspace_id, current_user, db)
        return self._get_cached_or_build(db, workspace_id)

    def update_settings(self, db: Session, current_user: User, payload: ChatbotSettingsUpdateRequest) -> ChatbotSettingsResponse:
        membership = get_workspace_member(payload.workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        self.validator.validate_update(payload)
        setting = self._get_or_create_setting(db, payload.workspace_id)
        setting.display_name = payload.identity.bot_name.strip()
        setting.welcome_message = payload.identity.welcome_message.strip()
        setting.system_prompt = payload.prompt.custom_system_prompt.strip() if payload.prompt.custom_system_prompt else None
        setting.lead_capture_enabled = payload.lead_capture.enabled
        setting.force_lead_before_chat = payload.lead_capture.force_before_chat
        setting.lead_capture_on_first_message = payload.lead_capture.trigger_on_first_message
        setting.lead_capture_on_low_confidence = payload.lead_capture.trigger_on_low_confidence
        setting.lead_capture_after_message_count = payload.lead_capture.trigger_after_n_messages
        setting.lead_required_fields_json = payload.lead_capture.required_fields
        setting.lead_auto_response_message = payload.lead_capture.auto_response_message
        setting.schedule_call_enabled = payload.handoff.enable_scheduling
        setting.notifications_enabled = payload.notifications.enabled
        setting.notification_email_recipients_json = payload.notifications.email_recipients
        setting.notification_webhook_urls_json = payload.notifications.webhook_endpoints
        setting.notification_retry_attempts = payload.notifications.retry_attempts
        setting.notification_triggers_json = {
            key: value.model_dump() for key, value in payload.notifications.triggers.items()
        }
        setting.notification_template_overrides_json = {
            key: value.model_dump(exclude_none=True) for key, value in payload.notifications.template_overrides.items()
        }
        setting.identity_config_json = payload.identity.model_dump()
        setting.behavior_config_json = payload.behavior.model_dump()
        setting.prompt_config_json = payload.prompt.model_dump()
        setting.lead_capture_config_json = payload.lead_capture.model_dump()
        setting.handoff_config_json = payload.handoff.model_dump()
        setting.voice_config_json = payload.voice.model_dump()
        setting.widget_config_json = payload.widget.model_dump()
        setting.allowed_domains_json = payload.widget.allowed_origins
        setting.access_control_config_json = payload.access_control.model_dump()
        setting.knowledge_base_config_json = payload.knowledge_base.model_dump(mode="json")
        setting.analytics_config_json = payload.analytics.model_dump()
        db.commit()
        db.refresh(setting)
        self._invalidate(payload.workspace_id)
        return self._get_cached_or_build(db, payload.workspace_id, force=True)

    def reset_defaults(self, db: Session, current_user: User, workspace_id: uuid.UUID) -> ChatbotSettingsResponse:
        membership = get_workspace_member(workspace_id, current_user, db)
        if membership.role not in {"admin", "team_member"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role.")
        defaults = build_default_settings_payload(workspace_id)
        payload = ChatbotSettingsUpdateRequest(**defaults.model_dump(exclude={"updated_at"}))
        return self.update_settings(db, current_user, payload)

    def get_public_settings(self, db: Session, workspace_id: uuid.UUID, *, origin: str | None = None) -> PublicChatbotSettingsResponse:
        payload = self._get_cached_or_build(db, workspace_id)
        if payload.access_control.chatbot_mode != "public" or not payload.access_control.allow_guest_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public widget access is disabled.")
        self.widget_auth_service.validate_origin(origin=origin, allowed_origins=payload.widget.allowed_origins)
        token, expires_in_seconds = self.widget_auth_service.build_token(workspace_id=workspace_id, origin=origin)
        return self.widget_configurator.build_public_payload(payload, auth_token=token, expires_in_seconds=expires_in_seconds)

    def get_setting_for_runtime(self, db: Session, workspace_id: uuid.UUID) -> ChatbotSetting:
        return self._get_or_create_setting(db, workspace_id)

    def _get_or_create_setting(self, db: Session, workspace_id: uuid.UUID) -> ChatbotSetting:
        setting = db.scalar(select(ChatbotSetting).where(ChatbotSetting.workspace_id == workspace_id))
        if setting:
            return setting
        defaults = build_default_settings_payload(workspace_id)
        setting = ChatbotSetting(
            workspace_id=workspace_id,
            display_name=defaults.identity.bot_name,
            welcome_message=defaults.identity.welcome_message,
            system_prompt=defaults.prompt.custom_system_prompt,
            lead_capture_enabled=defaults.lead_capture.enabled,
            force_lead_before_chat=defaults.lead_capture.force_before_chat,
            lead_capture_on_first_message=defaults.lead_capture.trigger_on_first_message,
            lead_capture_after_message_count=defaults.lead_capture.trigger_after_n_messages,
            lead_capture_on_low_confidence=defaults.lead_capture.trigger_on_low_confidence,
            schedule_call_enabled=defaults.handoff.enable_scheduling,
            lead_required_fields_json=defaults.lead_capture.required_fields,
            lead_auto_response_message=defaults.lead_capture.auto_response_message,
            notifications_enabled=defaults.notifications.enabled,
            notification_email_recipients_json=defaults.notifications.email_recipients,
            notification_webhook_urls_json=defaults.notifications.webhook_endpoints,
            notification_retry_attempts=defaults.notifications.retry_attempts,
            notification_triggers_json={key: value.model_dump() for key, value in defaults.notifications.triggers.items()},
            notification_template_overrides_json={key: value.model_dump(exclude_none=True) for key, value in defaults.notifications.template_overrides.items()},
            identity_config_json=defaults.identity.model_dump(),
            behavior_config_json=defaults.behavior.model_dump(),
            prompt_config_json=defaults.prompt.model_dump(),
            lead_capture_config_json=defaults.lead_capture.model_dump(),
            handoff_config_json=defaults.handoff.model_dump(),
            voice_config_json=defaults.voice.model_dump(),
            widget_config_json=defaults.widget.model_dump(),
            allowed_domains_json=defaults.widget.allowed_origins,
            access_control_config_json=defaults.access_control.model_dump(),
            knowledge_base_config_json=defaults.knowledge_base.model_dump(mode="json"),
            analytics_config_json=defaults.analytics.model_dump(),
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
        return setting

    def _get_cached_or_build(self, db: Session, workspace_id: uuid.UUID, force: bool = False) -> ChatbotSettingsResponse:
        cache_key = str(workspace_id)
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached and not force and now - cached[0] <= self._ttl_seconds:
            return cached[1]
        setting = self._get_or_create_setting(db, workspace_id)
        payload = build_default_settings_payload(workspace_id, setting=setting)
        self._cache[cache_key] = (now, payload)
        return payload

    def _invalidate(self, workspace_id: uuid.UUID) -> None:
        self._cache.pop(str(workspace_id), None)
