from __future__ import annotations

from fastapi import BackgroundTasks

from app.models import ChatSession, ChatbotSetting, User
from app.schemas.lead import LeadCreateRequest, LeadUpdateRequest
from app.services.lead_qualification import LeadQualificationService
from app.services.lead_service import LeadService


class FakeNotificationService:
    def __init__(self) -> None:
        self.lead_created_calls: list[dict] = []
        self.handoff_calls: list[dict] = []

    def queue_lead_created(self, background_tasks, *, lead, workspace, chatbot_setting) -> None:
        self.lead_created_calls.append(
            {
                "background_tasks": background_tasks,
                "lead_id": str(lead.id),
                "workspace_id": str(workspace.id),
                "setting_id": str(chatbot_setting.id) if chatbot_setting else None,
            }
        )

    def queue_handoff_requested(self, background_tasks, *, workspace, chatbot_setting, session_id, reason, user_question) -> None:
        self.handoff_calls.append(
            {
                "background_tasks": background_tasks,
                "workspace_id": str(workspace.id),
                "session_id": session_id,
                "reason": reason,
                "user_question": user_question,
            }
        )


def test_qualification_marks_high_intent_sales_lead():
    result = LeadQualificationService().qualify(
        message="We want pricing, a demo, and need to buy this urgently.",
        use_case="sales",
        repeated_attempts=2,
    )
    assert result["priority"] == "high"
    assert result["tag"] == "sales"
    assert result["high_intent"] is True


def test_capture_prompt_triggers_on_first_message(db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    session = db_session.get(ChatSession, seeded_workspace.session_id)
    assert user is not None
    assert session is not None

    prompt = LeadService().evaluate_capture_prompt(
        db_session,
        session,
        query="Can someone contact me about pricing?",
        confidence="High",
    )
    assert prompt.should_prompt is True
    assert prompt.trigger == "human_request"


def test_create_lead_persists_priority_and_tag(db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None
    notifications = FakeNotificationService()
    setting = db_session.query(ChatbotSetting).filter(ChatbotSetting.workspace_id == seeded_workspace.workspace_id).one()
    setting.lead_notifications_enabled = True
    db_session.commit()

    lead = LeadService(notification_service=notifications).create_lead(
        db_session,
        user,
        LeadCreateRequest(
            workspace_id=seeded_workspace.workspace_id,
            chat_session_id=seeded_workspace.session_id,
            name="Priya",
            email="priya@example.com",
            company="Example Corp",
            use_case="demo",
            message="We need a pricing demo urgently for our team.",
        ),
        BackgroundTasks(),
    )

    assert lead.priority == "high"
    assert lead.tag == "sales"
    assert lead.high_intent is True
    assert len(notifications.lead_created_calls) == 1


def test_handoff_marks_session_for_human_review(db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None
    notifications = FakeNotificationService()

    response = LeadService(notification_service=notifications).register_handoff(
        db_session,
        user,
        workspace_id=seeded_workspace.workspace_id,
        session_id=seeded_workspace.session_id,
        reason="manual_handoff",
        message="Need a human follow-up",
        background_tasks=BackgroundTasks(),
    )

    session = db_session.get(ChatSession, seeded_workspace.session_id)
    assert session is not None
    assert session.needs_human_review is True
    assert response.lead_prompt.should_prompt is True
    assert len(notifications.handoff_calls) == 1


def test_update_lead_notes_and_status(db_session, seeded_workspace):
    user = db_session.get(User, seeded_workspace.user_id)
    assert user is not None

    lead = LeadService().create_lead(
        db_session,
        user,
        LeadCreateRequest(
            workspace_id=seeded_workspace.workspace_id,
            chat_session_id=seeded_workspace.session_id,
            name="Priya",
            email="priya@example.com",
            message="Please contact me.",
        ),
    )

    updated = LeadService().update_lead(
        db_session,
        user,
        workspace_id=seeded_workspace.workspace_id,
        lead_id=lead.id,
        payload=LeadUpdateRequest(status="contacted", notes="Reached out by email."),
    )
    assert updated.status == "contacted"
    assert updated.notes == "Reached out by email."


def test_force_before_chat_prompt_is_supported(db_session, seeded_workspace):
    setting = db_session.query(ChatbotSetting).filter(ChatbotSetting.workspace_id == seeded_workspace.workspace_id).one()
    setting.force_lead_before_chat = True
    setting.lead_capture_on_first_message = False
    db_session.commit()

    session = db_session.get(ChatSession, seeded_workspace.session_id)
    assert session is not None
    prompt = LeadService().evaluate_capture_prompt(
        db_session,
        session,
        query="Need help understanding pricing",
        confidence="High",
    )
    assert prompt.should_prompt is False
