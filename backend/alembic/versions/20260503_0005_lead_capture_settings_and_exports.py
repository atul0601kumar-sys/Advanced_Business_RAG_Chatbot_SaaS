"""Add lead capture settings fields.

Revision ID: 20260503_0005
Revises: 20260503_0004
Create Date: 2026-05-03 06:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260503_0005"
down_revision = "20260503_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chatbot_settings", sa.Column("force_lead_before_chat", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("chatbot_settings", sa.Column("lead_required_fields_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("lead_notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("chatbot_settings", sa.Column("lead_auto_response_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chatbot_settings", "lead_auto_response_message")
    op.drop_column("chatbot_settings", "lead_notifications_enabled")
    op.drop_column("chatbot_settings", "lead_required_fields_json")
    op.drop_column("chatbot_settings", "force_lead_before_chat")
