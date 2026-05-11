"""Add notification delivery configuration fields.

Revision ID: 20260503_0006
Revises: 20260503_0005
Create Date: 2026-05-03 08:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260503_0006"
down_revision = "20260503_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chatbot_settings", sa.Column("notification_triggers_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("notification_template_overrides_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chatbot_settings", "notification_template_overrides_json")
    op.drop_column("chatbot_settings", "notification_triggers_json")
