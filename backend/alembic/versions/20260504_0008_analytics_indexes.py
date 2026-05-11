"""analytics indexes

Revision ID: 20260504_0008
Revises: 20260504_0007
Create Date: 2026-05-04 10:30:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260504_0008"
down_revision: str | None = "20260504_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_analytics_events_event_name", "analytics_events", ["event_name"], unique=False)
    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"], unique=False)
    op.create_index(
        "ix_analytics_events_workspace_name_occurred_at",
        "analytics_events",
        ["workspace_id", "event_name", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_events_workspace_type_occurred_at",
        "analytics_events",
        ["workspace_id", "event_type", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_events_workspace_type_occurred_at", table_name="analytics_events")
    op.drop_index("ix_analytics_events_workspace_name_occurred_at", table_name="analytics_events")
    op.drop_index("ix_analytics_events_event_type", table_name="analytics_events")
    op.drop_index("ix_analytics_events_event_name", table_name="analytics_events")
