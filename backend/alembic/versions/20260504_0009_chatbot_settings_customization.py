"""chatbot settings customization

Revision ID: 20260504_0009
Revises: 20260504_0008
Create Date: 2026-05-04 16:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260504_0009"
down_revision: str | None = "20260504_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chatbot_settings", sa.Column("identity_config_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("behavior_config_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("prompt_config_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("lead_capture_config_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("handoff_config_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("voice_config_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("widget_config_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("access_control_config_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("knowledge_base_config_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("analytics_config_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chatbot_settings", "analytics_config_json")
    op.drop_column("chatbot_settings", "knowledge_base_config_json")
    op.drop_column("chatbot_settings", "access_control_config_json")
    op.drop_column("chatbot_settings", "widget_config_json")
    op.drop_column("chatbot_settings", "voice_config_json")
    op.drop_column("chatbot_settings", "handoff_config_json")
    op.drop_column("chatbot_settings", "lead_capture_config_json")
    op.drop_column("chatbot_settings", "prompt_config_json")
    op.drop_column("chatbot_settings", "behavior_config_json")
    op.drop_column("chatbot_settings", "identity_config_json")
