from __future__ import annotations

from datetime import UTC, datetime

from app.models import Booking, CalendarConnection, MeetingType, User
from app.services.booking_service import BookingService


class _FakeCryptoService:
    def encrypt(self, value: str | None) -> str | None:
        return f"enc::{value}" if value else None

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return value.removeprefix("enc::")


def test_booking_service_provider_descriptors_and_helper_payloads(db_session, seeded_workspace):
    service = BookingService(crypto_service=_FakeCryptoService())

    providers = {item.provider: item for item in service.list_providers()}
    assert set(providers) == {"google", "outlook", "calcom", "external_link"}
    assert providers["calcom"].supports_event_creation is True
    assert providers["external_link"].supports_busy_lookup is False

    slug = service._slugify("Sales Demo / Enterprise + LATAM")
    assert slug == "sales-demo-enterprise-latam"
    assert len(service._hash_management_token("token-123")) == 64
    naive = datetime(2026, 1, 1, 15, 0)
    assert service._ensure_utc(naive).tzinfo == UTC

    meeting_type = MeetingType(
        workspace_id=seeded_workspace.workspace_id,
        title="Sales Demo",
        slug="sales-demo",
        description="Talk through the platform",
        duration_minutes=45,
        location_type="external_url",
        assignment_mode="specific",
        provider_preference="calcom",
        external_location_url="https://meet.example.com/default",
        booking_link_token="book-token",
        metadata_json={
            "calcom_event_type_id": 42,
            "calcom_event_type_slug": "sales-demo",
            "calcom_username": "alpha-team",
            "calcom_team_slug": "revenue",
            "calcom_organization_slug": "acme",
        },
    )
    booking = Booking(
        workspace_id=seeded_workspace.workspace_id,
        meeting_type_id=meeting_type.id,
        visitor_name="Jordan Buyer",
        visitor_email="jordan@example.com",
        visitor_phone="+15555550101",
        start_time_utc=datetime(2026, 1, 2, 15, 0, tzinfo=UTC),
        end_time_utc=datetime(2026, 1, 2, 15, 45, tzinfo=UTC),
        timezone="America/New_York",
        status="confirmed",
        provider="calcom",
        management_token_hash="hash",
    )

    payload = service._provider_booking_payload(booking, meeting_type)
    assert payload["eventTypeId"] == 42
    assert payload["eventTypeSlug"] == "sales-demo"
    assert payload["username"] == "alpha-team"
    assert payload["teamSlug"] == "revenue"
    assert payload["organizationSlug"] == "acme"
    assert payload["meetingUrl"] == "https://meet.example.com/default"
    assert payload["attendee"]["email"] == "jordan@example.com"


def test_booking_service_resolve_location_and_connection_metadata(db_session, seeded_workspace):
    service = BookingService(crypto_service=_FakeCryptoService())
    assigned_user = db_session.get(User, seeded_workspace.user_id)
    assert assigned_user is not None

    connection = CalendarConnection(
        workspace_id=seeded_workspace.workspace_id,
        user_id=seeded_workspace.user_id,
        provider="calcom",
        status="connected",
        access_token_encrypted="enc::secret-token",
        external_account_email="owner@example.com",
        metadata_json={"base_url": "https://api.cal.com", "access_token": "raw-secret"},
    )
    db_session.add(connection)
    db_session.commit()

    runtime_metadata = service._connection_runtime_metadata(connection)
    serialized = service._serialize_connection(connection)

    assert runtime_metadata["access_token"] == "secret-token"
    assert serialized.metadata == {"base_url": "https://api.cal.com"}

    meeting_external = MeetingType(
        workspace_id=seeded_workspace.workspace_id,
        title="External",
        slug="external",
        duration_minutes=30,
        location_type="external_url",
        assignment_mode="specific",
        external_location_url="https://meet.example.com/external",
        booking_link_token="external-token",
    )
    meeting_manual = MeetingType(
        workspace_id=seeded_workspace.workspace_id,
        title="Manual",
        slug="manual",
        duration_minutes=30,
        location_type="manual",
        assignment_mode="specific",
        manual_location_text="Front desk",
        booking_link_token="manual-token",
    )
    meeting_phone = MeetingType(
        workspace_id=seeded_workspace.workspace_id,
        title="Phone",
        slug="phone",
        duration_minutes=30,
        location_type="phone",
        assignment_mode="specific",
        booking_link_token="phone-token",
    )
    meeting_fallback = MeetingType(
        workspace_id=seeded_workspace.workspace_id,
        title="Fallback",
        slug="fallback",
        duration_minutes=30,
        location_type="google_meet",
        assignment_mode="specific",
        manual_location_text="Shared later",
        booking_link_token="fallback-token",
    )
    booking = Booking(
        workspace_id=seeded_workspace.workspace_id,
        meeting_type_id=meeting_external.id,
        assigned_user_id=assigned_user.id,
        visitor_name="Jamie Caller",
        visitor_email="jamie@example.com",
        visitor_phone="+14445556666",
        start_time_utc=datetime(2026, 1, 2, 15, 0, tzinfo=UTC),
        end_time_utc=datetime(2026, 1, 2, 15, 30, tzinfo=UTC),
        timezone="UTC",
        status="confirmed",
        provider="internal",
        management_token_hash="hash-2",
    )

    assert service._resolve_meeting_link(meeting_external, booking) == "https://meet.example.com/external"
    assert service._resolve_meeting_link(meeting_manual, booking) == "Front desk"
    assert service._resolve_meeting_link(meeting_phone, booking) == "+14445556666"
    assert service._resolve_meeting_link(meeting_fallback, booking) == "Shared later"
