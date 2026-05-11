"""Add lead capture and human handoff fields.

Revision ID: 20260503_0004
Revises: 20260503_0003
Create Date: 2026-05-03 05:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260503_0004"
down_revision = "20260503_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("needs_human_review", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("leads", sa.Column("use_case", sa.String(length=255), nullable=True))
    op.add_column("leads", sa.Column("source", sa.String(length=50), nullable=False, server_default="chatbot"))
    op.add_column("leads", sa.Column("priority", sa.String(length=20), nullable=False, server_default="low"))
    op.add_column("leads", sa.Column("tag", sa.String(length=50), nullable=False, server_default="general"))
    op.add_column("leads", sa.Column("high_intent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("leads", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index("ix_leads_priority", "leads", ["priority"], unique=False)
    op.create_index("ix_leads_tag", "leads", ["tag"], unique=False)

    op.add_column("chatbot_settings", sa.Column("lead_capture_on_first_message", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("chatbot_settings", sa.Column("lead_capture_after_message_count", sa.Integer(), nullable=False, server_default=sa.text("4")))
    op.add_column("chatbot_settings", sa.Column("lead_capture_on_low_confidence", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("chatbot_settings", sa.Column("schedule_call_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("chatbot_settings", sa.Column("admin_notification_email", sa.String(length=255), nullable=True))
    op.add_column("chatbot_settings", sa.Column("notification_webhook_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("chatbot_settings", "notification_webhook_url")
    op.drop_column("chatbot_settings", "admin_notification_email")
    op.drop_column("chatbot_settings", "schedule_call_enabled")
    op.drop_column("chatbot_settings", "lead_capture_on_low_confidence")
    op.drop_column("chatbot_settings", "lead_capture_after_message_count")
    op.drop_column("chatbot_settings", "lead_capture_on_first_message")

    op.drop_index("ix_leads_tag", table_name="leads")
    op.drop_index("ix_leads_priority", table_name="leads")
    op.drop_column("leads", "notes")
    op.drop_column("leads", "high_intent")
    op.drop_column("leads", "tag")
    op.drop_column("leads", "priority")
    op.drop_column("leads", "source")
    op.drop_column("leads", "use_case")

    op.drop_column("chat_sessions", "needs_human_review")
