"""add export jobs

Revision ID: 20260504_0011
Revises: 20260504_0010
Create Date: 2026-05-04 15:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260504_0011"
down_revision = "20260504_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table(
        "export_jobs",
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("requested_by_user_id", uuid_type, nullable=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("export_format", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("file_url", sa.String(length=1024), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("filters_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_export_jobs")),
    )
    op.create_index(op.f("ix_export_jobs_workspace_id"), "export_jobs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_export_jobs_requested_by_user_id"), "export_jobs", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_export_jobs_job_type"), "export_jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_export_jobs_status"), "export_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_export_jobs_status"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_job_type"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_requested_by_user_id"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_workspace_id"), table_name="export_jobs")
    op.drop_table("export_jobs")
