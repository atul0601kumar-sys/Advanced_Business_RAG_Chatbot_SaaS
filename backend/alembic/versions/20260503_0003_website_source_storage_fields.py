"""Add website source storage fields and chunk linkage.

Revision ID: 20260503_0003
Revises: 20260503_0002
Create Date: 2026-05-03 02:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260503_0003"
down_revision = "20260503_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("website_sources", sa.Column("domain", sa.String(length=255), nullable=True))
    op.add_column("website_sources", sa.Column("page_title", sa.String(length=255), nullable=True))
    op.add_column("website_sources", sa.Column("crawl_date", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_website_sources_domain", "website_sources", ["domain"], unique=False)

    op.add_column("document_chunks", sa.Column("website_source_id", sa.Uuid(), nullable=True))
    op.create_index("ix_document_chunks_website_source_id", "document_chunks", ["website_source_id"], unique=False)
    op.create_foreign_key(
        "fk_document_chunks_website_source_id",
        "document_chunks",
        "website_sources",
        ["website_source_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_document_chunks_website_source_id", "document_chunks", type_="foreignkey")
    op.drop_index("ix_document_chunks_website_source_id", table_name="document_chunks")
    op.drop_column("document_chunks", "website_source_id")

    op.drop_index("ix_website_sources_domain", table_name="website_sources")
    op.drop_column("website_sources", "crawl_date")
    op.drop_column("website_sources", "page_title")
    op.drop_column("website_sources", "domain")
