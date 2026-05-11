"""integration framework

Revision ID: 20260504_0013
Revises: 20260504_0012
Create Date: 2026-05-04 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260504_0013"
down_revision = "20260504_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_table(
        "integration_connections",
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("integration_type", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.String(length=64), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_connections")),
        sa.UniqueConstraint("workspace_id", "integration_type", "display_name", name="uq_integration_workspace_type_name"),
    )
    op.create_index(op.f("ix_integration_connections_workspace_id"), "integration_connections", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_integration_connections_integration_type"), "integration_connections", ["integration_type"], unique=False)
    op.create_index(op.f("ix_integration_connections_status"), "integration_connections", ["status"], unique=False)

    op.create_table(
        "integration_deliveries",
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("integration_id", uuid_type, nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["integration_id"], ["integration_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_deliveries")),
    )
    op.create_index(op.f("ix_integration_deliveries_workspace_id"), "integration_deliveries", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_integration_deliveries_integration_id"), "integration_deliveries", ["integration_id"], unique=False)
    op.create_index(op.f("ix_integration_deliveries_event_type"), "integration_deliveries", ["event_type"], unique=False)
    op.create_index(op.f("ix_integration_deliveries_status"), "integration_deliveries", ["status"], unique=False)
    op.create_index(op.f("ix_integration_deliveries_next_attempt_at"), "integration_deliveries", ["next_attempt_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_deliveries_next_attempt_at"), table_name="integration_deliveries")
    op.drop_index(op.f("ix_integration_deliveries_status"), table_name="integration_deliveries")
    op.drop_index(op.f("ix_integration_deliveries_event_type"), table_name="integration_deliveries")
    op.drop_index(op.f("ix_integration_deliveries_integration_id"), table_name="integration_deliveries")
    op.drop_index(op.f("ix_integration_deliveries_workspace_id"), table_name="integration_deliveries")
    op.drop_table("integration_deliveries")

    op.drop_index(op.f("ix_integration_connections_status"), table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_integration_type"), table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_workspace_id"), table_name="integration_connections")
    op.drop_table("integration_connections")
