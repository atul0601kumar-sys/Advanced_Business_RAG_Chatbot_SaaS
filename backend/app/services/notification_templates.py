from __future__ import annotations

from dataclasses import dataclass
from string import Template
from typing import Any


@dataclass(frozen=True)
class RenderedEmailTemplate:
    subject: str
    text_body: str
    html_body: str


@dataclass(frozen=True)
class EmailTemplateDefinition:
    template_id: str
    subject_template: str
    text_template: str
    html_template: str

    def render(
        self,
        context: dict[str, Any],
        override: dict[str, str] | None = None,
    ) -> RenderedEmailTemplate:
        normalized = {key: self._stringify(value) for key, value in context.items()}
        chosen_subject = (override or {}).get("subject") or self.subject_template
        chosen_text = (override or {}).get("text_body") or self.text_template
        chosen_html = (override or {}).get("html_body") or self.html_template
        return RenderedEmailTemplate(
            subject=Template(chosen_subject).safe_substitute(normalized).strip(),
            text_body=Template(chosen_text).safe_substitute(normalized).strip(),
            html_body=Template(chosen_html).safe_substitute(normalized).strip(),
        )

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)


def _html_shell(title: str, body: str) -> str:
    return f"""
<html>
  <body style="margin:0;padding:0;background:#f4f7fb;font-family:Arial,sans-serif;color:#172033;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="background:#ffffff;border-radius:16px;overflow:hidden;">
            <tr>
              <td style="padding:24px 32px;background:#0f172a;color:#ffffff;">
                <h1 style="margin:0;font-size:22px;">{title}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                {body}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".strip()


TEMPLATES: dict[str, EmailTemplateDefinition] = {
    "lead.created.admin": EmailTemplateDefinition(
        template_id="lead.created.admin",
        subject_template="New lead for ${workspace_name}: ${lead_name}",
        text_template=(
            "A new lead was created for ${workspace_name}.\n\n"
            "Lead name: ${lead_name}\n"
            "Email: ${lead_email}\n"
            "Phone: ${lead_phone}\n"
            "Company: ${lead_company}\n"
            "Message: ${lead_message}\n"
            "Priority: ${lead_priority}\n\n"
            "Open dashboard: ${dashboard_url}\n"
        ),
        html_template=_html_shell(
            "New Lead Notification",
            """
            <p style="margin-top:0;">A new lead was created for <strong>${workspace_name}</strong>.</p>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="8" style="border-collapse:collapse;">
              <tr><td><strong>Lead name</strong></td><td>${lead_name}</td></tr>
              <tr><td><strong>Email</strong></td><td>${lead_email}</td></tr>
              <tr><td><strong>Phone</strong></td><td>${lead_phone}</td></tr>
              <tr><td><strong>Company</strong></td><td>${lead_company}</td></tr>
              <tr><td><strong>Message</strong></td><td>${lead_message}</td></tr>
              <tr><td><strong>Priority</strong></td><td>${lead_priority}</td></tr>
            </table>
            <p><a href="${dashboard_url}">Open the leads dashboard</a></p>
            """,
        ),
    ),
    "lead.high_priority.admin": EmailTemplateDefinition(
        template_id="lead.high_priority.admin",
        subject_template="[HIGH PRIORITY] Lead alert for ${workspace_name}: ${lead_name}",
        text_template=(
            "HIGH PRIORITY lead detected for ${workspace_name}.\n\n"
            "Lead name: ${lead_name}\n"
            "Email: ${lead_email}\n"
            "Phone: ${lead_phone}\n"
            "Company: ${lead_company}\n"
            "Message: ${lead_message}\n"
            "Priority: ${lead_priority}\n\n"
            "Review immediately: ${dashboard_url}\n"
        ),
        html_template=_html_shell(
            "HIGH PRIORITY Lead Alert",
            """
            <p style="margin-top:0;color:#b91c1c;font-weight:700;">HIGH PRIORITY lead detected.</p>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="8" style="border-collapse:collapse;">
              <tr><td><strong>Lead name</strong></td><td>${lead_name}</td></tr>
              <tr><td><strong>Email</strong></td><td>${lead_email}</td></tr>
              <tr><td><strong>Phone</strong></td><td>${lead_phone}</td></tr>
              <tr><td><strong>Company</strong></td><td>${lead_company}</td></tr>
              <tr><td><strong>Message</strong></td><td>${lead_message}</td></tr>
              <tr><td><strong>Priority</strong></td><td>${lead_priority}</td></tr>
            </table>
            <p><a href="${dashboard_url}">Review the lead now</a></p>
            """,
        ),
    ),
    "lead.handoff.admin": EmailTemplateDefinition(
        template_id="lead.handoff.admin",
        subject_template="Human handoff requested in ${workspace_name}",
        text_template=(
            "A human handoff was requested in ${workspace_name}.\n\n"
            "Session ID: ${session_id}\n"
            "Reason: ${handoff_reason}\n"
            "User question: ${user_question}\n\n"
            "Open chat session: ${chat_session_url}\n"
        ),
        html_template=_html_shell(
            "Human Handoff Request",
            """
            <p style="margin-top:0;">A user requested human assistance.</p>
            <p><strong>Session ID:</strong> ${session_id}</p>
            <p><strong>Reason:</strong> ${handoff_reason}</p>
            <p><strong>Full user question:</strong><br />${user_question}</p>
            <p><a href="${chat_session_url}">Open the chat session</a></p>
            """,
        ),
    ),
    "lead.user_confirmation": EmailTemplateDefinition(
        template_id="lead.user_confirmation",
        subject_template="We received your request for ${workspace_name}",
        text_template=(
            "Hi ${lead_name},\n\n"
            "Thank you for contacting ${workspace_name}. We received your request and our team will review it shortly.\n\n"
            "Next steps:\n"
            "- We will review your request.\n"
            "- A teammate will follow up if more detail is needed.\n"
            "- You can continue using the assistant in the meantime.\n\n"
            "Your message: ${lead_message}\n"
            "Chat link: ${chat_dashboard_url}\n"
        ),
        html_template=_html_shell(
            "Thanks For Reaching Out",
            """
            <p style="margin-top:0;">Hi ${lead_name},</p>
            <p>Thank you for contacting <strong>${workspace_name}</strong>. We received your request and our team will review it shortly.</p>
            <p><strong>Next steps</strong></p>
            <ul>
              <li>We will review your request.</li>
              <li>A teammate will follow up if more detail is needed.</li>
              <li>You can continue using the assistant in the meantime.</li>
            </ul>
            <p><strong>Your message:</strong><br />${lead_message}</p>
            <p><a href="${chat_dashboard_url}">Open the chat workspace</a></p>
            """,
        ),
    ),
    "feedback.negative.admin": EmailTemplateDefinition(
        template_id="feedback.negative.admin",
        subject_template="Negative feedback received in ${workspace_name}",
        text_template=(
            "Negative feedback was submitted in ${workspace_name}.\n\n"
            "User: ${user_email}\n"
            "Category: ${feedback_category}\n"
            "Comment: ${feedback_comment}\n"
            "Assistant message: ${message_context}\n\n"
            "Open session: ${chat_session_url}\n"
        ),
        html_template=_html_shell(
            "Negative Feedback Alert",
            """
            <p style="margin-top:0;">Negative feedback was submitted.</p>
            <p><strong>User:</strong> ${user_email}</p>
            <p><strong>Category:</strong> ${feedback_category}</p>
            <p><strong>Comment:</strong><br />${feedback_comment}</p>
            <p><strong>Message context:</strong><br />${message_context}</p>
            <p><a href="${chat_session_url}">Review the conversation</a></p>
            """,
        ),
    ),
    "system.error.admin": EmailTemplateDefinition(
        template_id="system.error.admin",
        subject_template="System error in ${workspace_name}: ${error_title}",
        text_template=(
            "A system error notification was raised.\n\n"
            "Workspace: ${workspace_name}\n"
            "Title: ${error_title}\n"
            "Details: ${error_details}\n"
        ),
        html_template=_html_shell(
            "System Error Alert",
            """
            <p style="margin-top:0;">A system error notification was raised.</p>
            <p><strong>Workspace:</strong> ${workspace_name}</p>
            <p><strong>Title:</strong> ${error_title}</p>
            <p><strong>Details:</strong><br />${error_details}</p>
            """,
        ),
    ),
    "custom.event.admin": EmailTemplateDefinition(
        template_id="custom.event.admin",
        subject_template="Custom notification: ${event_name}",
        text_template=(
            "A custom notification trigger fired.\n\n"
            "Workspace: ${workspace_name}\n"
            "Event: ${event_name}\n"
            "Summary: ${event_summary}\n"
            "Details: ${event_details}\n"
        ),
        html_template=_html_shell(
            "Custom Notification Event",
            """
            <p style="margin-top:0;">A custom notification trigger fired.</p>
            <p><strong>Workspace:</strong> ${workspace_name}</p>
            <p><strong>Event:</strong> ${event_name}</p>
            <p><strong>Summary:</strong> ${event_summary}</p>
            <p><strong>Details:</strong><br />${event_details}</p>
            """,
        ),
    ),
    "notification.test": EmailTemplateDefinition(
        template_id="notification.test",
        subject_template="Test notification for ${workspace_name}",
        text_template=(
            "This is a test notification for ${workspace_name}.\n\n"
            "If you received this email, the notification system is configured correctly.\n"
        ),
        html_template=_html_shell(
            "Test Notification",
            """
            <p style="margin-top:0;">This is a test notification for <strong>${workspace_name}</strong>.</p>
            <p>If you received this email, the notification system is configured correctly.</p>
            """,
        ),
    ),
}


def get_template(template_id: str) -> EmailTemplateDefinition:
    try:
        return TEMPLATES[template_id]
    except KeyError as exc:  # pragma: no cover - protected by tests that use known template ids
        raise ValueError(f"Unknown notification template: {template_id}") from exc
