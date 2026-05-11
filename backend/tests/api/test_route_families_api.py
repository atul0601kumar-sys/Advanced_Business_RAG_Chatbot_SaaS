from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.auth_security import hash_password
from app.models import (
    AnalyticsEvent,
    ChatMessage,
    ChatSession,
    ExportJob,
    FAQ,
    Feedback,
    IntegrationConnection,
    IntegrationDelivery,
    NotificationLog,
    User,
    WorkspaceMember,
)
from app.services.base_integration import IntegrationResult
from app.services.widget_auth import WidgetAuthService


@dataclass
class RouteFamilySeedData:
    widget_session_id: uuid.UUID
    widget_message_id: uuid.UUID
    faq_id: uuid.UUID
    other_workspace_faq_id: uuid.UUID
    notification_log_id: uuid.UUID
    export_job_id: uuid.UUID
    isolated_export_job_id: uuid.UUID


@pytest.fixture()
def route_family_seed_data(db_session, seeded_workspace) -> RouteFamilySeedData:
    widget_session = ChatSession(
        workspace_id=seeded_workspace.workspace_id,
        user_id=None,
        title="Website visitor conversation",
        channel="widget",
        status="active",
    )
    widget_message = ChatMessage(
        chat_session=widget_session,
        role="assistant",
        content="We can help automate revenue reporting.",
        token_usage_json={"confidence": "High"},
    )
    faq = FAQ(
        workspace_id=seeded_workspace.workspace_id,
        question="How do I export analytics?",
        answer="Open the analytics dashboard and request a CSV or PDF export.",
        category="Analytics",
        source="operations-playbook.pdf",
        status="draft",
        confidence_score=0.91,
        normalized_question="how do i export analytics",
        source_type="document",
        source_id="operations-playbook",
        citations_json=[{"file_name": "operations-playbook.pdf", "chunk_preview": "Export analytics from the dashboard."}],
    )
    other_workspace_faq = FAQ(
        workspace_id=seeded_workspace.other_workspace_id,
        question="How do Slack notifications work?",
        answer="Slack alerts are delivered through the configured bot token.",
        category="Integrations",
        source="slack-guide.pdf",
        status="approved",
        confidence_score=0.88,
        normalized_question="how do slack notifications work",
        source_type="document",
        source_id="slack-guide",
    )
    notification_log = NotificationLog(
        workspace_id=seeded_workspace.workspace_id,
        notification_id="notif-lead-001",
        type="lead.created",
        channel="email",
        status="delivered",
        retry_count=0,
        response_code=202,
        response_body="accepted",
        target="sales@alpha.example.com",
    )
    export_job = ExportJob(
        workspace_id=seeded_workspace.workspace_id,
        requested_by_user_id=seeded_workspace.user_id,
        job_type="chat",
        export_format="csv",
        status="pending",
        filters_json={"workspace_id": str(seeded_workspace.workspace_id), "source": "widget"},
    )
    isolated_export_job = ExportJob(
        workspace_id=seeded_workspace.unaffiliated_workspace_id,
        requested_by_user_id=seeded_workspace.user_id,
        job_type="faq",
        export_format="json",
        status="completed",
        file_url="https://downloads.example.com/isolated-faqs.json",
        file_name="isolated-faqs.json",
        content_type="application/json",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        filters_json={"workspace_id": str(seeded_workspace.unaffiliated_workspace_id)},
    )

    db_session.add_all([widget_session, widget_message, faq, other_workspace_faq, notification_log, export_job, isolated_export_job])
    db_session.commit()

    return RouteFamilySeedData(
        widget_session_id=widget_session.id,
        widget_message_id=widget_message.id,
        faq_id=faq.id,
        other_workspace_faq_id=other_workspace_faq.id,
        notification_log_id=notification_log.id,
        export_job_id=export_job.id,
        isolated_export_job_id=isolated_export_job.id,
    )


def _widget_headers(workspace_id: uuid.UUID, *, origin: str | None = None) -> dict[str, str]:
    token, _ = WidgetAuthService().build_token(workspace_id=workspace_id, origin=origin)
    headers = {"X-Widget-Token": token}
    if origin:
        headers["Origin"] = origin
    return headers


def _build_settings_update_payload(workspace_id: uuid.UUID) -> dict:
    data_url = "data:image/png;base64,aW1hZ2U="
    return {
        "workspace_id": str(workspace_id),
        "identity": {
            "bot_name": "Revenue Copilot",
            "bot_avatar": data_url,
            "brand_color_primary": "#0f766e",
            "brand_color_secondary": "#115e59",
            "logo": data_url,
            "tagline": "Answers grounded in revenue operations knowledge",
            "welcome_message": "Hi, I can help with revenue analytics, onboarding, and handoff workflows.",
        },
        "behavior": {
            "tone": "professional",
            "response_style": "mixed",
            "max_response_length": 1200,
            "markdown_enabled": True,
            "citations_enabled": True,
            "confidence_score_enabled": True,
        },
        "prompt": {
            "custom_system_prompt": "Answer only from indexed business knowledge.",
            "company_instructions": "Keep responses concise and cite sources.",
            "business_rules": "Escalate pricing exceptions to sales ops.",
        },
        "lead_capture": {
            "enabled": True,
            "force_before_chat": False,
            "trigger_on_first_message": False,
            "trigger_on_low_confidence": True,
            "trigger_after_n_messages": 3,
            "required_fields": ["name", "email", "company"],
            "custom_form_message": "Share your details for a tailored follow-up.",
            "auto_response_message": "Thanks, the revenue team will follow up shortly.",
        },
        "handoff": {
            "enabled": True,
            "custom_message": "A teammate can jump in if you need a deeper walkthrough.",
            "enable_scheduling": True,
            "escalate_on_low_confidence": True,
            "escalate_on_repeated_failures": True,
        },
        "voice": {
            "voice_input_enabled": True,
            "voice_output_enabled": True,
            "voice_style": "alloy",
            "transcript_preview_enabled": True,
            "auto_read_assistant_responses": False,
        },
        "widget": {
            "position": "left",
            "size": "comfortable",
            "theme": "light",
            "welcome_popup_message": "Need help with revenue operations?",
            "launcher_icon": data_url,
            "show_branding": True,
            "delay_before_appearance_seconds": 1,
            "allowed_origins": ["https://portal.example.com"],
        },
        "access_control": {
            "restrict_to_logged_in_users": False,
            "chatbot_mode": "public",
            "allow_guest_access": True,
            "rate_limit_per_user_per_minute": 30,
        },
        "knowledge_base": {
            "disabled_document_ids": [],
            "disabled_urls": [],
            "prioritized_document_ids": [],
            "prioritized_urls": ["https://portal.example.com/pricing"],
            "chunk_relevance_threshold": 0.2,
        },
        "analytics": {
            "tracking_enabled": True,
            "feedback_collection_enabled": True,
            "anonymize_user_data": False,
        },
        "notifications": {
            "enabled": True,
            "notification_types": ["new_lead", "high_priority_lead"],
            "email_recipients": ["sales@alpha.example.com"],
            "webhook_endpoints": ["https://hooks.example.com/chatbot/alerts"],
            "retry_attempts": 4,
            "triggers": {
                "lead.created": {
                    "enabled": True,
                    "channels": ["email", "webhook"],
                    "email_recipients": ["sales@alpha.example.com"],
                    "webhook_urls": ["https://hooks.example.com/chatbot/alerts"],
                }
            },
            "template_overrides": {
                "lead.created.admin": {
                    "subject": "New enterprise lead",
                    "text_body": "A new lead was captured from the widget.",
                }
            },
        },
    }


@pytest.mark.api
@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/api/v1/notifications/settings?workspace_id={workspace_id}", None),
        ("get", "/api/v1/settings?workspace_id={workspace_id}", None),
        ("get", "/api/v1/integrations/list?workspace_id={workspace_id}", None),
        ("get", "/api/v1/faq/list?workspace_id={workspace_id}", None),
        ("post", "/api/v1/export/chat", {"workspace_id": "{workspace_id}", "format": "csv"}),
        ("get", "/api/v1/workspaces", None),
    ],
)
def test_protected_route_families_require_auth(api_client, seeded_workspace, method, path, json_body):
    request_path = path.format(workspace_id=seeded_workspace.workspace_id)
    payload = None
    if json_body is not None:
        payload = {
            key: (value.format(workspace_id=seeded_workspace.workspace_id) if isinstance(value, str) else value)
            for key, value in json_body.items()
        }
    request_kwargs = {"json": payload} if payload is not None else {}
    response = api_client.request(method.upper(), request_path, **request_kwargs)
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


@pytest.mark.api
def test_notifications_routes_cover_admin_access_updates_logs_and_failures(
    api_client,
    auth_headers,
    seeded_workspace,
    route_family_seed_data,
    monkeypatch,
):
    monkeypatch.setattr("app.services.notification_service.NotificationService.queue_test_email", lambda self, db, current_user, payload: 2)
    monkeypatch.setattr("app.services.notification_service.NotificationService.queue_manual_webhook", lambda self, db, current_user, payload: 1)

    unauthorized_role_response = api_client.get(
        f"/api/v1/notifications/settings?workspace_id={seeded_workspace.other_workspace_id}",
        headers=auth_headers,
    )
    assert unauthorized_role_response.status_code == 403
    assert unauthorized_role_response.json()["detail"] == "Admin role required."

    settings_response = api_client.get(
        f"/api/v1/notifications/settings?workspace_id={seeded_workspace.workspace_id}",
        headers=auth_headers,
    )
    assert settings_response.status_code == 200
    assert settings_response.json()["workspace_id"] == str(seeded_workspace.workspace_id)

    update_response = api_client.put(
        "/api/v1/notifications/settings",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "notifications_enabled": True,
            "email_recipients": ["sales@alpha.example.com", "ops@alpha.example.com"],
            "webhook_urls": ["https://hooks.example.com/notify/leads"],
            "retry_attempts": 5,
            "rate_limit_count": 25,
            "rate_limit_window_seconds": 120,
            "event_rules": {
                "lead.created": {
                    "enabled": True,
                    "channels": ["email", "webhook"],
                    "email_recipients": ["sales@alpha.example.com"],
                    "webhook_urls": ["https://hooks.example.com/notify/leads"],
                }
            },
            "template_overrides": {
                "lead.created.admin": {
                    "subject": "New lead from pricing page",
                    "text_body": "Please review the captured buyer details.",
                }
            },
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["email_recipients"] == ["sales@alpha.example.com", "ops@alpha.example.com"]
    assert update_response.json()["retry_attempts"] == 5

    logs_response = api_client.get(
        f"/api/v1/notifications/logs?workspace_id={seeded_workspace.workspace_id}&limit=10",
        headers=auth_headers,
    )
    assert logs_response.status_code == 200
    assert logs_response.json()["total"] == 1
    assert logs_response.json()["items"][0]["id"] == str(route_family_seed_data.notification_log_id)

    no_recipient_response = api_client.post(
        "/api/v1/notifications/test-email",
        headers=auth_headers,
        json={"workspace_id": str(seeded_workspace.workspace_id), "to_addresses": []},
    )
    assert no_recipient_response.status_code == 200
    assert no_recipient_response.json()["queued_jobs"] >= 1

    missing_webhook_response = api_client.post(
        "/api/v1/notifications/webhook",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "event_name": "lead.created",
            "payload": {"lead_name": "Acme Corp"},
            "webhook_urls": [],
        },
    )
    assert missing_webhook_response.status_code == 200
    assert missing_webhook_response.json()["queued_jobs"] >= 1


@pytest.mark.api
def test_settings_routes_cover_updates_public_origin_checks_and_reset(api_client, auth_headers, seeded_workspace):
    update_payload = _build_settings_update_payload(seeded_workspace.workspace_id)

    update_response = api_client.put(
        "/api/v1/settings/update",
        headers=auth_headers,
        json=update_payload,
    )
    assert update_response.status_code == 200
    assert update_response.json()["identity"]["bot_name"] == "Revenue Copilot"
    assert update_response.json()["widget"]["position"] == "left"

    viewer_update_response = api_client.put(
        "/api/v1/settings/update",
        headers=auth_headers,
        json={**update_payload, "workspace_id": str(seeded_workspace.other_workspace_id)},
    )
    assert viewer_update_response.status_code == 403
    assert viewer_update_response.json()["detail"] == "Insufficient workspace role."

    get_response = api_client.get(
        f"/api/v1/settings?workspace_id={seeded_workspace.workspace_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["identity"]["logo"] == "data:image/png;base64,aW1hZ2U="

    public_response = api_client.get(
        f"/api/v1/settings/public?workspace_id={seeded_workspace.workspace_id}",
        headers={"Origin": "https://portal.example.com"},
    )
    assert public_response.status_code == 200
    public_body = public_response.json()
    assert public_body["identity"]["bot_name"] == "Revenue Copilot"
    assert public_body["identity"]["brand_color_primary"] == "#0f766e"
    assert public_body["identity"]["welcome_message"].startswith("Hi, I can help")
    assert public_body["widget"]["position"] == "left"
    assert public_body["embed"]["auth_token"]

    blocked_origin_response = api_client.get(
        f"/api/v1/settings/public?workspace_id={seeded_workspace.workspace_id}",
        headers={"Origin": "https://malicious.example.com"},
    )
    assert blocked_origin_response.status_code == 403
    assert blocked_origin_response.json()["detail"] == "Origin is not allowed for this widget."

    reset_response = api_client.post(
        f"/api/v1/settings/reset-default?workspace_id={seeded_workspace.workspace_id}",
        headers=auth_headers,
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["identity"]["bot_name"] == "Workspace Assistant"
    assert reset_response.json()["widget"]["position"] == "right"


@pytest.mark.api
def test_integrations_routes_cover_connection_lifecycle_and_access_control(
    api_client,
    auth_headers,
    seeded_workspace,
    monkeypatch,
):
    monkeypatch.setattr("app.services.integrations.webhook.WebhookIntegration.validate_config", lambda self, **kwargs: None)
    monkeypatch.setattr(
        "app.services.integrations.webhook.WebhookIntegration.connect",
        lambda self, context: IntegrationResult(status_code=200, response_body="connected"),
    )
    monkeypatch.setattr(
        "app.services.integrations.webhook.WebhookIntegration.send_event",
        lambda self, context, *, event_type, payload: IntegrationResult(status_code=202, response_body="accepted"),
    )
    monkeypatch.setattr(
        "app.services.integrations.webhook.WebhookIntegration.disconnect",
        lambda self, context: IntegrationResult(status_code=200, response_body="disconnected"),
    )

    viewer_connect_response = api_client.post(
        "/api/v1/integrations/connect",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.other_workspace_id),
            "integration_type": "webhook",
            "display_name": "Beta Revenue Alerts",
            "credentials": {},
            "config": {"webhook_url": "https://hooks.example.com/beta", "event_types": ["lead_created"]},
        },
    )
    assert viewer_connect_response.status_code == 403
    assert viewer_connect_response.json()["detail"] == "Insufficient workspace role."

    connect_response = api_client.post(
        "/api/v1/integrations/connect",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "integration_type": "webhook",
            "display_name": "Revenue Ops Webhook",
            "credentials": {},
            "config": {
                "webhook_url": "https://hooks.example.com/revenue-ops",
                "event_types": ["lead_created", "feedback_submitted"],
                "rate_limit_count": 40,
                "rate_limit_window_seconds": 60,
            },
        },
    )
    assert connect_response.status_code == 200
    connection_id = connect_response.json()["connection"]["id"]
    assert connect_response.json()["connection"]["display_name"] == "Revenue Ops Webhook"

    list_response = api_client.get(
        f"/api/v1/integrations/list?workspace_id={seeded_workspace.workspace_id}",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    assert any(item["id"] == connection_id for item in list_response.json()["connections"])

    update_response = api_client.put(
        "/api/v1/integrations/update",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "integration_id": connection_id,
            "display_name": "Revenue Ops Alerts",
            "credentials": {},
            "config": {"event_types": ["lead_created"]},
            "status": "paused",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["connection"]["display_name"] == "Revenue Ops Alerts"
    assert update_response.json()["connection"]["status"] == "paused"

    test_response = api_client.post(
        "/api/v1/integrations/test",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "integration_id": connection_id,
            "event_type": "lead_created",
        },
    )
    assert test_response.status_code == 200
    assert test_response.json()["status"] == "success"

    disconnect_response = api_client.request(
        "DELETE",
        "/api/v1/integrations/disconnect",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "integration_id": connection_id,
        },
    )
    assert disconnect_response.status_code == 200
    assert disconnect_response.json()["connection"]["status"] == "inactive"

    unsupported_response = api_client.post(
        "/api/v1/integrations/connect",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "integration_type": "hubspot",
            "display_name": "HubSpot Sync",
            "credentials": {"api_key": "secret"},
            "config": {},
        },
    )
    assert unsupported_response.status_code == 400
    assert "not implemented" in unsupported_response.json()["detail"].lower()


class _FakeSpeechToTextProvider:
    def transcribe(self, *, audio_bytes: bytes, mime_type: str, language: str | None):
        return {"transcript": f"transcribed {mime_type} ({len(audio_bytes)} bytes)", "provider": "fake-stt"}


class _FakeTextToSpeechProvider:
    def synthesize(self, *, text: str, voice_style: str | None, format: str):
        from app.services.voice_service import SynthesizedAudio

        return SynthesizedAudio(
            audio_bytes=f"{voice_style or 'default'}:{text}".encode("utf-8"),
            mime_type=f"audio/{format}",
            provider="fake-tts",
        )


@pytest.mark.api
def test_voice_routes_require_valid_auth_workspace_context_and_realistic_payloads(
    api_client,
    auth_headers,
    seeded_workspace,
    monkeypatch,
):
    monkeypatch.setattr("app.services.voice_service.VoiceService._build_stt_provider", lambda self: _FakeSpeechToTextProvider())
    monkeypatch.setattr("app.services.voice_service.VoiceService._build_tts_provider", lambda self: _FakeTextToSpeechProvider())
    access_token = api_client.cookies.get("access_token")
    assert access_token
    bearer_headers = {
        "User-Agent": "pytest-client",
        "Authorization": f"Bearer {access_token}",
    }
    api_client.cookies.clear()

    missing_auth_response = api_client.post(
        "/api/v1/voice/transcribe",
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "audio_base64": base64.b64encode(b"hello voice").decode("utf-8"),
            "mime_type": "audio/webm",
        },
    )
    assert missing_auth_response.status_code == 401
    assert missing_auth_response.json()["detail"] == "Widget token is required."

    invalid_audio_response = api_client.post(
        "/api/v1/voice/transcribe",
        headers=bearer_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "audio_base64": "not-valid-base64",
            "mime_type": "audio/webm",
        },
    )
    assert invalid_audio_response.status_code == 400
    assert invalid_audio_response.json()["detail"] == "Voice audio payload is invalid."

    synthesize_response = api_client.post(
        "/api/v1/voice/synthesize",
        headers=bearer_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "text": "Summarize quarterly revenue performance.",
            "voice_style": "alloy",
            "format": "mp3",
        },
    )
    assert synthesize_response.status_code == 200
    assert synthesize_response.json()["provider"] == "fake-tts"

    api_client.cookies.clear()
    widget_mismatch_response = api_client.post(
        "/api/v1/voice/synthesize",
        headers=_widget_headers(seeded_workspace.other_workspace_id),
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "text": "Read the welcome message aloud.",
            "voice_style": "alloy",
            "format": "mp3",
        },
    )
    assert widget_mismatch_response.status_code == 403
    assert widget_mismatch_response.json()["detail"] == "Widget workspace mismatch."


@pytest.mark.api
def test_widget_routes_track_events_save_feedback_and_enforce_widget_isolation(
    api_client,
    db_session,
    route_family_seed_data,
    seeded_workspace,
):
    api_client.cookies.clear()

    event_response = api_client.post(
        "/api/v1/widget/event",
        headers=_widget_headers(seeded_workspace.workspace_id),
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "session_id": str(route_family_seed_data.widget_session_id),
            "event": "message_sent",
            "metadata": {"message_length": 42, "page": "/pricing"},
        },
    )
    assert event_response.status_code == 200
    assert event_response.json()["message"] == "Widget event tracked."
    tracked_event = db_session.scalar(
        select(AnalyticsEvent).where(
            AnalyticsEvent.workspace_id == seeded_workspace.workspace_id,
            AnalyticsEvent.chat_session_id == route_family_seed_data.widget_session_id,
            AnalyticsEvent.event_type == "message_sent",
        )
    )
    assert tracked_event is not None
    assert tracked_event.properties_json["source"] == "widget"

    feedback_response = api_client.post(
        "/api/v1/feedback",
        headers=_widget_headers(seeded_workspace.workspace_id),
        json={
            "session_id": str(route_family_seed_data.widget_session_id),
            "message_id": str(route_family_seed_data.widget_message_id),
            "value": "down",
            "category": "accuracy",
            "comment": "The answer skipped the onboarding timeline.",
        },
    )
    assert feedback_response.status_code == 200
    feedback_record = db_session.get(Feedback, uuid.UUID(feedback_response.json()["feedback_id"]))
    assert feedback_record is not None
    assert feedback_record.workspace_id == seeded_workspace.workspace_id
    assert feedback_record.user_id is None

    non_widget_session_response = api_client.post(
        "/api/v1/feedback",
        headers=_widget_headers(seeded_workspace.workspace_id),
        json={
            "session_id": str(seeded_workspace.session_id),
            "message_id": str(route_family_seed_data.widget_message_id),
            "value": "up",
        },
    )
    assert non_widget_session_response.status_code == 404
    assert non_widget_session_response.json()["detail"] == "Chat session not found."

    mismatch_response = api_client.post(
        "/api/v1/widget/event",
        headers=_widget_headers(seeded_workspace.other_workspace_id),
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "session_id": str(route_family_seed_data.widget_session_id),
            "event": "widget_opened",
            "metadata": {"page": "/help-center"},
        },
    )
    assert mismatch_response.status_code == 403
    assert mismatch_response.json()["detail"] == "Widget workspace mismatch."


@pytest.mark.api
def test_faq_routes_cover_generation_listing_updates_exports_deletes_and_isolation(
    api_client,
    auth_headers,
    db_session,
    seeded_workspace,
    route_family_seed_data,
    monkeypatch,
):
    generation_calls: list[dict] = []
    monkeypatch.setattr(
        "app.services.faq_service.FAQService.run_generation_job",
        lambda self, payload: generation_calls.append(payload),
    )

    generate_response = api_client.post(
        "/api/v1/faq/generate",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "document_ids": [],
            "website_source_ids": [],
            "force": True,
            "max_faqs_per_source": 4,
        },
    )
    assert generate_response.status_code == 202
    assert generate_response.json()["generation"]["status"] == "queued"
    assert len(generation_calls) == 1

    list_response = api_client.get(
        f"/api/v1/faq/list?workspace_id={seeded_workspace.workspace_id}&status=draft",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == str(route_family_seed_data.faq_id)

    update_response = api_client.put(
        "/api/v1/faq/update",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "faq_id": str(route_family_seed_data.faq_id),
            "question": "How can I export analytics dashboards?",
            "answer": "Use the export menu in analytics to generate CSV or PDF files.",
            "category": "Reporting",
            "status": "approved",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["category"] == "Reporting"
    assert update_response.json()["status"] == "approved"

    approve_response = api_client.post(
        "/api/v1/faq/approve",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "faq_ids": [str(route_family_seed_data.faq_id)],
            "action": "approve",
        },
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["updated_ids"] == [str(route_family_seed_data.faq_id)]

    export_response = api_client.post(
        "/api/v1/faq/export",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "format": "json",
            "status": "approved",
        },
    )
    assert export_response.status_code == 200
    assert export_response.headers["content-disposition"] == "attachment; filename=faq-export.json"
    assert "export analytics" in export_response.text.lower()

    delete_response = api_client.delete(
        f"/api/v1/faq/delete?workspace_id={seeded_workspace.workspace_id}&faq_ids={route_family_seed_data.faq_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 200
    assert db_session.get(FAQ, route_family_seed_data.faq_id) is None

    isolation_response = api_client.get(
        f"/api/v1/faq/list?workspace_id={seeded_workspace.unaffiliated_workspace_id}",
        headers=auth_headers,
    )
    assert isolation_response.status_code == 403
    assert isolation_response.json()["detail"] == "Workspace access denied."


@pytest.mark.api
def test_export_routes_cover_queue_status_download_and_workspace_isolation(
    api_client,
    auth_headers,
    db_session,
    seeded_workspace,
    route_family_seed_data,
    monkeypatch,
):
    enqueued_job_ids: list[str] = []
    monkeypatch.setattr(
        "app.api.v1.routes.export.shared_export_queue.enqueue",
        lambda job_id: enqueued_job_ids.append(str(job_id)),
    )

    create_response = api_client.post(
        "/api/v1/export/chat",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "format": "csv",
            "source": "widget",
            "session_ids": [str(route_family_seed_data.widget_session_id)],
        },
    )
    assert create_response.status_code == 202
    created_job_id = create_response.json()["job_id"]
    assert created_job_id in enqueued_job_ids

    status_response = api_client.get(f"/api/v1/export/status/{created_job_id}", headers=auth_headers)
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "pending"

    pending_download_response = api_client.get(
        f"/api/v1/export/download/{route_family_seed_data.export_job_id}",
        headers=auth_headers,
        follow_redirects=False,
    )
    assert pending_download_response.status_code == 409
    assert pending_download_response.json()["detail"] == "Export file is not ready for download."

    created_job = db_session.get(ExportJob, uuid.UUID(created_job_id))
    assert created_job is not None
    created_job.status = "completed"
    created_job.file_url = "https://downloads.example.com/chat-history.csv"
    created_job.file_name = "chat-history.csv"
    created_job.content_type = "text/csv"
    created_job.expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.commit()

    download_response = api_client.get(
        f"/api/v1/export/download/{created_job_id}",
        headers=auth_headers,
        follow_redirects=False,
    )
    assert download_response.status_code == 307
    assert download_response.headers["location"] == "https://downloads.example.com/chat-history.csv"

    isolation_response = api_client.get(
        f"/api/v1/export/status/{route_family_seed_data.isolated_export_job_id}",
        headers=auth_headers,
    )
    assert isolation_response.status_code == 403
    assert isolation_response.json()["detail"] == "Workspace access denied."


@pytest.mark.api
def test_workspace_routes_cover_listing_roles_and_member_visibility(
    api_client,
    auth_headers,
    db_session,
    seeded_workspace,
):
    teammate = User(
        email="teammate-reviewer@example.com",
        full_name="Teammate Reviewer",
        password_hash=hash_password("CorrectHorseBatteryStaple!"),
        is_active=True,
        is_superuser=False,
        session_nonce=uuid.uuid4().hex,
    )
    db_session.add(teammate)
    db_session.flush()
    db_session.add(
        WorkspaceMember(
            workspace_id=seeded_workspace.workspace_id,
            user_id=teammate.id,
            role="viewer",
        )
    )
    db_session.commit()

    list_response = api_client.get("/api/v1/workspaces", headers=auth_headers)
    assert list_response.status_code == 200
    listed_ids = {item["id"] for item in list_response.json()}
    assert listed_ids == {str(seeded_workspace.workspace_id), str(seeded_workspace.other_workspace_id)}

    other_workspace_response = api_client.get(
        f"/api/v1/workspaces/{seeded_workspace.other_workspace_id}",
        headers=auth_headers,
    )
    assert other_workspace_response.status_code == 200
    assert other_workspace_response.json()["role"] == "viewer"

    members_response = api_client.get(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/members",
        headers=auth_headers,
    )
    assert members_response.status_code == 200
    assert any(member["email"] == "teammate-reviewer@example.com" for member in members_response.json())

    isolation_response = api_client.get(
        f"/api/v1/workspaces/{seeded_workspace.unaffiliated_workspace_id}",
        headers=auth_headers,
    )
    assert isolation_response.status_code == 403
    assert isolation_response.json()["detail"] == "Workspace access denied."
