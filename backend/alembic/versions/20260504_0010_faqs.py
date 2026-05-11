"""faq generation and review

Revision ID: 20260504_0010
Revises: 20260504_0009
Create Date: 2026-05-04 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260504_0010"
down_revision: str | None = "20260504_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "faqs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=2048), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("normalized_question", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("generation_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("citations_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_faqs")),
    )
    op.create_index(op.f("ix_faqs_workspace_id"), "faqs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_faqs_category"), "faqs", ["category"], unique=False)
    op.create_index(op.f("ix_faqs_status"), "faqs", ["status"], unique=False)
    op.create_index(op.f("ix_faqs_normalized_question"), "faqs", ["normalized_question"], unique=False)
    op.create_index(op.f("ix_faqs_generation_fingerprint"), "faqs", ["generation_fingerprint"], unique=False)
    op.create_index("ix_faqs_workspace_status_category", "faqs", ["workspace_id", "status", "category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_faqs_workspace_status_category", table_name="faqs")
    op.drop_index(op.f("ix_faqs_generation_fingerprint"), table_name="faqs")
    op.drop_index(op.f("ix_faqs_normalized_question"), table_name="faqs")
    op.drop_index(op.f("ix_faqs_status"), table_name="faqs")
    op.drop_index(op.f("ix_faqs_category"), table_name="faqs")
    op.drop_index(op.f("ix_faqs_workspace_id"), table_name="faqs")
    op.drop_table("faqs")
