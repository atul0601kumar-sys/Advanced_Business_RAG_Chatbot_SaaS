"""Add notification queue, logs, and settings fields.

Revision ID: 20260504_0007
Revises: 20260503_0006
Create Date: 2026-05-04 09:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260504_0007"
down_revision = "20260503_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chatbot_settings", sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("chatbot_settings", sa.Column("notification_email_recipients_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("notification_webhook_urls_json", sa.JSON(), nullable=True))
    op.add_column("chatbot_settings", sa.Column("notification_retry_attempts", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("chatbot_settings", sa.Column("notification_rate_limit_count", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("chatbot_settings", sa.Column("notification_rate_limit_window_seconds", sa.Integer(), nullable=False, server_default="60"))

    op.create_table(
        "notification_jobs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("event_name", sa.String(length=100), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("target", sa.String(length=500), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_jobs")),
    )
    op.create_index(op.f("ix_notification_jobs_workspace_id"), "notification_jobs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_notification_jobs_event_name"), "notification_jobs", ["event_name"], unique=False)
    op.create_index(op.f("ix_notification_jobs_channel"), "notification_jobs", ["channel"], unique=False)
    op.create_index(op.f("ix_notification_jobs_status"), "notification_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_notification_jobs_dedupe_key"), "notification_jobs", ["dedupe_key"], unique=False)
    op.create_index(op.f("ix_notification_jobs_next_attempt_at"), "notification_jobs", ["next_attempt_at"], unique=False)

    op.create_table(
        "notification_logs",
        sa.Column("notification_job_id", sa.Uuid(), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("target", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["notification_job_id"], ["notification_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_logs")),
    )
    op.create_index(op.f("ix_notification_logs_notification_job_id"), "notification_logs", ["notification_job_id"], unique=False)
    op.create_index(op.f("ix_notification_logs_workspace_id"), "notification_logs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_notification_logs_notification_id"), "notification_logs", ["notification_id"], unique=False)
    op.create_index(op.f("ix_notification_logs_type"), "notification_logs", ["type"], unique=False)
    op.create_index(op.f("ix_notification_logs_channel"), "notification_logs", ["channel"], unique=False)
    op.create_index(op.f("ix_notification_logs_status"), "notification_logs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_logs_status"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_channel"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_type"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_notification_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_workspace_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_notification_job_id"), table_name="notification_logs")
    op.drop_table("notification_logs")

    op.drop_index(op.f("ix_notification_jobs_next_attempt_at"), table_name="notification_jobs")
    op.drop_index(op.f("ix_notification_jobs_dedupe_key"), table_name="notification_jobs")
    op.drop_index(op.f("ix_notification_jobs_status"), table_name="notification_jobs")
    op.drop_index(op.f("ix_notification_jobs_channel"), table_name="notification_jobs")
    op.drop_index(op.f("ix_notification_jobs_event_name"), table_name="notification_jobs")
    op.drop_index(op.f("ix_notification_jobs_workspace_id"), table_name="notification_jobs")
    op.drop_table("notification_jobs")

    op.drop_column("chatbot_settings", "notification_rate_limit_window_seconds")
    op.drop_column("chatbot_settings", "notification_rate_limit_count")
    op.drop_column("chatbot_settings", "notification_retry_attempts")
    op.drop_column("chatbot_settings", "notification_webhook_urls_json")
    op.drop_column("chatbot_settings", "notification_email_recipients_json")
    op.drop_column("chatbot_settings", "notifications_enabled")
