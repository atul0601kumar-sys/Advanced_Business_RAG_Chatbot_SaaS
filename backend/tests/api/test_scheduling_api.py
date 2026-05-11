from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from app.schemas.scheduling import AvailableSlot
from app.services.calendar_provider_base import ProviderBookingResult


def _tomorrow_window():
    tomorrow = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return tomorrow, tomorrow.replace(hour=23, minute=59, second=59)


def test_scheduling_create_slot_book_and_manage(api_client, auth_headers, seeded_workspace):
    tomorrow_start, tomorrow_end = _tomorrow_window()

    meeting_type = api_client.post(
        "/api/v1/meeting-types/create",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "title": "Sales Demo",
            "description": "Talk through the product",
            "duration_minutes": 30,
            "location_type": "manual",
            "assignment_mode": "specific",
            "assigned_user_id": str(seeded_workspace.user_id),
            "manual_location_text": "https://meet.example.com/demo",
            "provider_preference": "external_link",
        },
    )
    assert meeting_type.status_code == 200, meeting_type.text
    meeting_type_id = meeting_type.json()["id"]

    availability = api_client.post(
        "/api/v1/availability/set",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "rules": [
                {
                    "weekday": tomorrow_start.weekday(),
                    "start_time": "09:00",
                    "end_time": "11:00",
                    "is_enabled": True,
                }
            ],
            "settings": {
                "timezone": "UTC",
                "buffer_before_minutes": 0,
                "buffer_after_minutes": 0,
                "duration_options": [30],
                "max_bookings_per_day": 10,
                "minimum_notice_minutes": 0,
                "future_booking_window_days": 30,
                "fallback_owner_user_id": str(seeded_workspace.user_id),
                "reminder_in_app_enabled": False,
            },
        },
    )
    assert availability.status_code == 200, availability.text

    slots = api_client.get(
        "/api/v1/booking/slots",
        headers=auth_headers,
        params={
            "workspace_id": str(seeded_workspace.workspace_id),
            "meeting_type_id": meeting_type_id,
            "timezone": "UTC",
            "start_date": tomorrow_start.isoformat(),
            "end_date": tomorrow_end.isoformat(),
        },
    )
    assert slots.status_code == 200, slots.text
    slot_payload = slots.json()["slots"]
    assert slot_payload
    selected_slot = slot_payload[0]["start_time_utc"]

    booking = api_client.post(
        "/api/v1/booking/create",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "meeting_type_id": meeting_type_id,
            "chat_session_id": str(seeded_workspace.session_id),
            "visitor_name": "Jordan Buyer",
            "visitor_email": "jordan@example.com",
            "visitor_phone": "+15555550101",
            "start_time_utc": selected_slot,
            "timezone": "UTC",
        },
    )
    assert booking.status_code == 200, booking.text
    booking_payload = booking.json()
    token = urlparse(booking_payload["management_url"]).path.rsplit("/", 1)[-1]
    assert token

    conflict = api_client.post(
        "/api/v1/booking/create",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "meeting_type_id": meeting_type_id,
            "visitor_name": "Alex Buyer",
            "visitor_email": "alex@example.com",
            "start_time_utc": selected_slot,
            "timezone": "UTC",
        },
    )
    assert conflict.status_code == 409, conflict.text

    token_lookup = api_client.get(f"/api/v1/booking/manage/{token}")
    assert token_lookup.status_code == 200, token_lookup.text
    assert token_lookup.json()["id"] == booking_payload["id"]

    api_client.cookies.clear()

    cancel = api_client.post(
        "/api/v1/booking/cancel",
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "token": token,
            "reason": "Need to move this later",
        },
    )
    assert cancel.status_code == 200, cancel.text


def test_scheduling_workspace_isolation(api_client, auth_headers, seeded_workspace):
    response = api_client.get(
        "/api/v1/booking/list",
        headers=auth_headers,
        params={"workspace_id": str(seeded_workspace.unaffiliated_workspace_id)},
    )
    assert response.status_code == 403, response.text


def test_scheduling_provider_sync_and_reschedule(api_client, auth_headers, seeded_workspace, monkeypatch):
    tomorrow_start, tomorrow_end = _tomorrow_window()
    synced = {"created": 0, "rescheduled": 0, "cancelled": 0}

    def mock_get_slots(self, **_kwargs):
        return [
            AvailableSlot(
                start_time_utc=tomorrow_start.replace(hour=9, minute=0),
                end_time_utc=tomorrow_start.replace(hour=9, minute=30),
                display_time="9:00 AM",
                timezone="UTC",
                provider="calcom",
                assigned_user_id=None,
            ),
            AvailableSlot(
                start_time_utc=tomorrow_start.replace(hour=10, minute=0),
                end_time_utc=tomorrow_start.replace(hour=10, minute=30),
                display_time="10:00 AM",
                timezone="UTC",
                provider="calcom",
                assigned_user_id=None,
            ),
        ]

    def mock_create_booking(self, **_kwargs):
        synced["created"] += 1
        return ProviderBookingResult(
            external_event_id="evt-create-1",
            meeting_link="https://video.example.com/create",
        )

    def mock_reschedule_booking(self, **_kwargs):
        synced["rescheduled"] += 1
        return ProviderBookingResult(
            external_event_id="evt-rescheduled-1",
            meeting_link="https://video.example.com/rescheduled",
        )

    def mock_cancel_booking(self, **_kwargs):
        synced["cancelled"] += 1

    monkeypatch.setattr("app.services.calcom_provider.CalComProvider.get_available_slots", mock_get_slots)
    monkeypatch.setattr("app.services.calcom_provider.CalComProvider.create_booking", mock_create_booking)
    monkeypatch.setattr("app.services.calcom_provider.CalComProvider.reschedule_booking", mock_reschedule_booking)
    monkeypatch.setattr("app.services.calcom_provider.CalComProvider.cancel_booking", mock_cancel_booking)

    connect = api_client.post(
        "/api/v1/calendar/connect",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "provider": "calcom",
            "api_key": "cal_test_key",
            "external_account_email": "owner@example.com",
            "metadata": {
                "username": "alpha-team",
                "calcom_event_type_slug": "sales-demo",
            },
        },
    )
    assert connect.status_code == 200, connect.text

    meeting_type = api_client.post(
        "/api/v1/meeting-types/create",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "title": "Support Call",
            "description": "Talk with support",
            "duration_minutes": 30,
            "location_type": "external_url",
            "assignment_mode": "specific",
            "assigned_user_id": str(seeded_workspace.user_id),
            "external_location_url": "https://video.example.com/default",
            "provider_preference": "calcom",
            "metadata": {
                "calcom_event_type_slug": "support-call",
                "calcom_username": "alpha-team",
            },
        },
    )
    assert meeting_type.status_code == 200, meeting_type.text
    meeting_type_id = meeting_type.json()["id"]

    availability = api_client.post(
        "/api/v1/availability/set",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "rules": [
                {
                    "weekday": tomorrow_start.weekday(),
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "is_enabled": True,
                }
            ],
            "settings": {
                "timezone": "UTC",
                "buffer_before_minutes": 0,
                "buffer_after_minutes": 0,
                "duration_options": [30],
                "max_bookings_per_day": 10,
                "minimum_notice_minutes": 0,
                "future_booking_window_days": 30,
                "fallback_owner_user_id": str(seeded_workspace.user_id),
                "reminder_in_app_enabled": False,
            },
        },
    )
    assert availability.status_code == 200, availability.text

    slots = api_client.get(
        "/api/v1/booking/slots",
        headers=auth_headers,
        params={
            "workspace_id": str(seeded_workspace.workspace_id),
            "meeting_type_id": meeting_type_id,
            "timezone": "UTC",
            "start_date": tomorrow_start.isoformat(),
            "end_date": tomorrow_end.isoformat(),
        },
    )
    assert slots.status_code == 200, slots.text
    selected_slot = slots.json()["slots"][0]["start_time_utc"]

    booking = api_client.post(
        "/api/v1/booking/create",
        headers=auth_headers,
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "meeting_type_id": meeting_type_id,
            "visitor_name": "Taylor Support",
            "visitor_email": "taylor@example.com",
            "start_time_utc": selected_slot,
            "timezone": "UTC",
        },
    )
    assert booking.status_code == 200, booking.text
    booking_payload = booking.json()
    assert booking_payload["external_event_id"] == "evt-create-1"
    assert booking_payload["meeting_link"] == "https://video.example.com/create"
    assert synced["created"] == 1

    token = urlparse(booking_payload["management_url"]).path.rsplit("/", 1)[-1]
    new_start = tomorrow_start.replace(hour=10, minute=0).isoformat()
    api_client.cookies.clear()

    reschedule = api_client.post(
        "/api/v1/booking/reschedule",
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "token": token,
            "start_time_utc": new_start,
            "timezone": "UTC",
        },
    )
    assert reschedule.status_code == 200, reschedule.text
    rescheduled_payload = reschedule.json()
    assert rescheduled_payload["status"] == "rescheduled"
    assert rescheduled_payload["external_event_id"] == "evt-rescheduled-1"
    assert rescheduled_payload["meeting_link"] == "https://video.example.com/rescheduled"
    assert synced["rescheduled"] == 1

    cancel = api_client.post(
        "/api/v1/booking/cancel",
        json={
            "workspace_id": str(seeded_workspace.workspace_id),
            "token": token,
            "reason": "Resolved asynchronously",
        },
    )
    assert cancel.status_code == 200, cancel.text
    assert synced["cancelled"] == 1
