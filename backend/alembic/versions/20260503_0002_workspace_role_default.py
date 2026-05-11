"""Update workspace member role default.

Revision ID: 20260503_0002
Revises: 20260503_0001
Create Date: 2026-05-03 00:20:00
"""

from alembic import op


revision = "20260503_0002"
down_revision = "20260503_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE workspace_members ALTER COLUMN role SET DEFAULT 'team_member'")
    op.execute("UPDATE workspace_members SET role = 'team_member' WHERE role = 'member'")
    op.execute("UPDATE workspace_members SET role = 'admin' WHERE role = 'owner'")


def downgrade() -> None:
    op.execute("ALTER TABLE workspace_members ALTER COLUMN role SET DEFAULT 'member'")
    op.execute("UPDATE workspace_members SET role = 'member' WHERE role = 'team_member'")
