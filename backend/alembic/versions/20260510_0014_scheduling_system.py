"""scheduling system

Revision ID: 20260510_0014
Revises: 20260504_0013
Create Date: 2026-05-10 12:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260510_0014"
down_revision = "20260504_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_table(
        "calendar_connections",
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_account_id", sa.String(length=255), nullable=True),
        sa.Column("external_account_email", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_connections")),
        sa.UniqueConstraint("workspace_id", "provider", "user_id", name="uq_calendar_connections_workspace_provider_user"),
    )
    op.create_index(op.f("ix_calendar_connections_workspace_id"), "calendar_connections", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_calendar_connections_user_id"), "calendar_connections", ["user_id"], unique=False)
    op.create_index(op.f("ix_calendar_connections_provider"), "calendar_connections", ["provider"], unique=False)
    op.create_index(op.f("ix_calendar_connections_status"), "calendar_connections", ["status"], unique=False)

    op.create_table(
        "meeting_types",
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("location_type", sa.String(length=50), nullable=False),
        sa.Column("assigned_user_id", uuid_type, nullable=True),
        sa.Column("assignment_mode", sa.String(length=30), nullable=False),
        sa.Column("provider_preference", sa.String(length=50), nullable=True),
        sa.Column("external_location_url", sa.String(length=2000), nullable=True),
        sa.Column("manual_location_text", sa.Text(), nullable=True),
        sa.Column("booking_link_token", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("availability_rules_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meeting_types")),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_meeting_types_workspace_slug"),
    )
    op.create_index(op.f("ix_meeting_types_workspace_id"), "meeting_types", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_meeting_types_slug"), "meeting_types", ["slug"], unique=False)
    op.create_index(op.f("ix_meeting_types_booking_link_token"), "meeting_types", ["booking_link_token"], unique=False)

    op.create_table(
        "availability_rules",
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("meeting_type_id", uuid_type, nullable=True),
        sa.Column("user_id", uuid_type, nullable=True),
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column("rule_type", sa.String(length=30), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("start_minute", sa.Integer(), nullable=True),
        sa.Column("end_minute", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=100), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("settings_json", sa.JSON(), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["meeting_type_id"], ["meeting_types.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_availability_rules")),
    )
    op.create_index(op.f("ix_availability_rules_workspace_id"), "availability_rules", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_availability_rules_meeting_type_id"), "availability_rules", ["meeting_type_id"], unique=False)
    op.create_index(op.f("ix_availability_rules_user_id"), "availability_rules", ["user_id"], unique=False)

    op.create_table(
        "blackout_dates",
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("meeting_type_id", uuid_type, nullable=True),
        sa.Column("user_id", uuid_type, nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("start_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["meeting_type_id"], ["meeting_types.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blackout_dates")),
    )
    op.create_index(op.f("ix_blackout_dates_workspace_id"), "blackout_dates", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_blackout_dates_meeting_type_id"), "blackout_dates", ["meeting_type_id"], unique=False)
    op.create_index(op.f("ix_blackout_dates_user_id"), "blackout_dates", ["user_id"], unique=False)
    op.create_index(op.f("ix_blackout_dates_start_time_utc"), "blackout_dates", ["start_time_utc"], unique=False)
    op.create_index(op.f("ix_blackout_dates_end_time_utc"), "blackout_dates", ["end_time_utc"], unique=False)

    op.create_table(
        "bookings",
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("lead_id", uuid_type, nullable=True),
        sa.Column("chat_session_id", uuid_type, nullable=True),
        sa.Column("meeting_type_id", uuid_type, nullable=False),
        sa.Column("assigned_user_id", uuid_type, nullable=True),
        sa.Column("visitor_name", sa.String(length=255), nullable=False),
        sa.Column("visitor_email", sa.String(length=255), nullable=False),
        sa.Column("visitor_phone", sa.String(length=50), nullable=True),
        sa.Column("start_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=True),
        sa.Column("meeting_link", sa.String(length=2000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("management_token_hash", sa.String(length=128), nullable=False),
        sa.Column("reminder_state_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["meeting_type_id"], ["meeting_types.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
    )
    op.create_index(op.f("ix_bookings_workspace_id"), "bookings", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_bookings_lead_id"), "bookings", ["lead_id"], unique=False)
    op.create_index(op.f("ix_bookings_chat_session_id"), "bookings", ["chat_session_id"], unique=False)
    op.create_index(op.f("ix_bookings_meeting_type_id"), "bookings", ["meeting_type_id"], unique=False)
    op.create_index(op.f("ix_bookings_assigned_user_id"), "bookings", ["assigned_user_id"], unique=False)
    op.create_index(op.f("ix_bookings_visitor_email"), "bookings", ["visitor_email"], unique=False)
    op.create_index(op.f("ix_bookings_start_time_utc"), "bookings", ["start_time_utc"], unique=False)
    op.create_index(op.f("ix_bookings_end_time_utc"), "bookings", ["end_time_utc"], unique=False)
    op.create_index(op.f("ix_bookings_status"), "bookings", ["status"], unique=False)
    op.create_index(op.f("ix_bookings_external_event_id"), "bookings", ["external_event_id"], unique=False)
    op.create_index(op.f("ix_bookings_management_token_hash"), "bookings", ["management_token_hash"], unique=False)

    op.create_table(
        "booking_attendees",
        sa.Column("booking_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("timezone", sa.String(length=100), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_attendees")),
    )
    op.create_index(op.f("ix_booking_attendees_booking_id"), "booking_attendees", ["booking_id"], unique=False)

    op.create_table(
        "booking_event_logs",
        sa.Column("booking_id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_event_logs")),
    )
    op.create_index(op.f("ix_booking_event_logs_booking_id"), "booking_event_logs", ["booking_id"], unique=False)
    op.create_index(op.f("ix_booking_event_logs_workspace_id"), "booking_event_logs", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_booking_event_logs_event_type"), "booking_event_logs", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_booking_event_logs_event_type"), table_name="booking_event_logs")
    op.drop_index(op.f("ix_booking_event_logs_workspace_id"), table_name="booking_event_logs")
    op.drop_index(op.f("ix_booking_event_logs_booking_id"), table_name="booking_event_logs")
    op.drop_table("booking_event_logs")

    op.drop_index(op.f("ix_booking_attendees_booking_id"), table_name="booking_attendees")
    op.drop_table("booking_attendees")

    op.drop_index(op.f("ix_bookings_management_token_hash"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_external_event_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_status"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_end_time_utc"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_start_time_utc"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_visitor_email"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_assigned_user_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_meeting_type_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_chat_session_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_lead_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_workspace_id"), table_name="bookings")
    op.drop_table("bookings")

    op.drop_index(op.f("ix_blackout_dates_end_time_utc"), table_name="blackout_dates")
    op.drop_index(op.f("ix_blackout_dates_start_time_utc"), table_name="blackout_dates")
    op.drop_index(op.f("ix_blackout_dates_user_id"), table_name="blackout_dates")
    op.drop_index(op.f("ix_blackout_dates_meeting_type_id"), table_name="blackout_dates")
    op.drop_index(op.f("ix_blackout_dates_workspace_id"), table_name="blackout_dates")
    op.drop_table("blackout_dates")

    op.drop_index(op.f("ix_availability_rules_user_id"), table_name="availability_rules")
    op.drop_index(op.f("ix_availability_rules_meeting_type_id"), table_name="availability_rules")
    op.drop_index(op.f("ix_availability_rules_workspace_id"), table_name="availability_rules")
    op.drop_table("availability_rules")

    op.drop_index(op.f("ix_meeting_types_booking_link_token"), table_name="meeting_types")
    op.drop_index(op.f("ix_meeting_types_slug"), table_name="meeting_types")
    op.drop_index(op.f("ix_meeting_types_workspace_id"), table_name="meeting_types")
    op.drop_table("meeting_types")

    op.drop_index(op.f("ix_calendar_connections_status"), table_name="calendar_connections")
    op.drop_index(op.f("ix_calendar_connections_provider"), table_name="calendar_connections")
    op.drop_index(op.f("ix_calendar_connections_user_id"), table_name="calendar_connections")
    op.drop_index(op.f("ix_calendar_connections_workspace_id"), table_name="calendar_connections")
    op.drop_table("calendar_connections")
