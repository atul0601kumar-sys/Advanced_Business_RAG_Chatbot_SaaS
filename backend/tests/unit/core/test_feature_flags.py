from __future__ import annotations

from sqlalchemy import select

from app.models import ChatSession, User
from app.schemas.settings import ChatbotSettingsUpdateRequest
from app.services.lead_service import LeadService
from app.services.settings_service import SettingsService, build_default_settings_payload


def test_settings_service_persists_voice_and_lead_capture_feature_toggles(db_session, seeded_workspace):
    current_user = db_session.get(User, seeded_workspace.user_id)
    assert current_user is not None
    service = SettingsService()

    defaults = build_default_settings_payload(seeded_workspace.workspace_id)
    payload_dict = defaults.model_dump(mode="json", exclude={"updated_at"})
    payload_dict["voice"]["voice_input_enabled"] = True
    payload_dict["voice"]["voice_output_enabled"] = True
    payload_dict["lead_capture"]["enabled"] = True
    payload_dict["lead_capture"]["trigger_on_first_message"] = True

    updated = service.update_settings(
        db_session,
        current_user,
        ChatbotSettingsUpdateRequest(**payload_dict),
    )
    assert updated.voice.voice_input_enabled is True
    assert updated.voice.voice_output_enabled is True
    assert updated.lead_capture.enabled is True

    payload_dict["voice"]["voice_input_enabled"] = False
    payload_dict["voice"]["voice_output_enabled"] = False
    payload_dict["lead_capture"]["enabled"] = False

    updated_again = service.update_settings(
        db_session,
        current_user,
        ChatbotSettingsUpdateRequest(**payload_dict),
    )
    assert updated_again.voice.voice_input_enabled is False
    assert updated_again.voice.voice_output_enabled is False
    assert updated_again.lead_capture.enabled is False


def test_lead_capture_toggle_changes_runtime_prompt_behavior(db_session, seeded_workspace):
    current_user = db_session.get(User, seeded_workspace.user_id)
    chat_session = db_session.scalar(
        select(ChatSession).where(ChatSession.id == seeded_workspace.session_id)
    )
    assert current_user is not None
    assert chat_session is not None

    service = LeadService()
    enabled_prompt = service.evaluate_capture_prompt(
        db_session,
        chat_session,
        query="Give me a product summary.",
        confidence="High",
    )
    assert enabled_prompt.should_prompt is True

    runtime_setting = SettingsService().get_setting_for_runtime(db_session, seeded_workspace.workspace_id)
    runtime_setting.lead_capture_enabled = False
    runtime_setting.lead_capture_on_first_message = False
    runtime_setting.lead_capture_on_low_confidence = False
    db_session.commit()

    disabled_prompt = service.evaluate_capture_prompt(
        db_session,
        chat_session,
        query="Give me a product summary.",
        confidence="High",
    )
    assert disabled_prompt.should_prompt is False
