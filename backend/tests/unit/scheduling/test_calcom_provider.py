from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError

import pytest
from fastapi import HTTPException

from app.services.calcom_provider import CALCOM_API_VERSION, CalComProvider


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_calcom_slots_return_empty_without_event_metadata():
    provider = CalComProvider()
    start = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)
    end = datetime(2026, 1, 2, 18, 0, tzinfo=UTC)

    assert provider.get_busy_slots(
        connection_metadata={"access_token": "token"},
        start_time_utc=start,
        end_time_utc=end,
        timezone="UTC",
        meeting_type_metadata={},
    ) == []
    assert provider.get_available_slots(
        connection_metadata={"access_token": "token"},
        start_time_utc=start,
        end_time_utc=end,
        timezone="UTC",
        meeting_type_metadata={},
    ) == []


def test_calcom_busy_slots_parse_range_payload(monkeypatch):
    provider = CalComProvider()
    start = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)
    end = datetime(2026, 1, 2, 18, 0, tzinfo=UTC)

    def fake_request(method, path, connection_metadata, body):
        assert method == "GET"
        assert "eventTypeId=42" in path
        assert "duration=30" in path
        assert body is None
        assert connection_metadata["access_token"] == "token"
        return {
            "data": {
                "2026-01-02": [
                    {"start": "2026-01-02T09:00:00Z", "end": "2026-01-02T09:30:00Z"},
                    {"start": "2026-01-02T10:00:00Z"},
                ]
            }
        }

    monkeypatch.setattr(provider, "_request", fake_request)

    busy = provider.get_busy_slots(
        connection_metadata={"access_token": "token"},
        start_time_utc=start,
        end_time_utc=end,
        timezone="UTC",
        meeting_type_metadata={"calcom_event_type_id": 42, "calcom_duration_minutes": 30},
    )

    assert len(busy) == 1
    assert busy[0].start_time_utc == datetime(2026, 1, 2, 9, 0, tzinfo=UTC)
    assert busy[0].end_time_utc == datetime(2026, 1, 2, 9, 30, tzinfo=UTC)


def test_calcom_available_slots_parse_slug_payload(monkeypatch):
    provider = CalComProvider()
    start = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)
    end = datetime(2026, 1, 2, 18, 0, tzinfo=UTC)

    def fake_request(method, path, connection_metadata, body):
        assert method == "GET"
        assert "eventTypeSlug=sales-demo" in path
        assert "username=alpha-team" in path
        assert "teamSlug=revops" in path
        assert "organizationSlug=acme" in path
        assert body is None
        return {
            "data": {
                "2026-01-02": [
                    {"start": "2026-01-02T15:00:00Z", "end": "2026-01-02T15:30:00Z"},
                    {"start": "2026-01-02T16:00:00Z"},
                ]
            }
        }

    monkeypatch.setattr(provider, "_request", fake_request)

    slots = provider.get_available_slots(
        connection_metadata={"access_token": "token"},
        start_time_utc=start,
        end_time_utc=end,
        timezone="America/New_York",
        meeting_type_metadata={
            "calcom_event_type_slug": "sales-demo",
            "calcom_username": "alpha-team",
            "calcom_team_slug": "revops",
            "calcom_organization_slug": "acme",
        },
    )

    assert len(slots) == 2
    assert slots[0].provider == "calcom"
    assert slots[0].timezone == "America/New_York"
    assert slots[0].display_time == "Fri, Jan 02 at 10:00 AM"
    assert slots[1].end_time_utc == slots[1].start_time_utc


def test_calcom_booking_actions_map_provider_payload(monkeypatch):
    provider = CalComProvider()
    seen: list[tuple[str, str, dict | None]] = []

    def fake_request(method, path, connection_metadata, body):
        seen.append((method, path, body))
        if path == "/v2/bookings":
            return {"data": {"uid": "evt-1", "meetingUrl": "https://meet.example.com/create"}}
        if path.endswith("/reschedule"):
            return {"data": {"uid": "evt-2", "meetingUrl": "https://meet.example.com/reschedule"}}
        return {"data": {}}

    monkeypatch.setattr(provider, "_request", fake_request)

    created = provider.create_booking(
        connection_metadata={"access_token": "token"},
        booking_payload={"meetingUrl": "https://fallback.example.com/create"},
    )
    rescheduled = provider.reschedule_booking(
        connection_metadata={"access_token": "token"},
        external_event_id="evt-1",
        booking_payload={"meetingUrl": "https://fallback.example.com/reschedule"},
    )
    provider.cancel_booking(
        connection_metadata={"access_token": "token"},
        external_event_id="evt-2",
        reason="Customer requested cancellation",
    )

    assert created.external_event_id == "evt-1"
    assert created.meeting_link == "https://meet.example.com/create"
    assert rescheduled.external_event_id == "evt-2"
    assert rescheduled.meeting_link == "https://meet.example.com/reschedule"
    assert seen[-1] == (
        "POST",
        "/v2/bookings/evt-2/cancel",
        {"reason": "Customer requested cancellation"},
    )


def test_calcom_request_uses_auth_headers_and_json_body(monkeypatch):
    provider = CalComProvider()
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        headers = {key.lower(): value for key, value in request.header_items()}
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["auth"] = headers.get("authorization")
        captured["api_version"] = headers.get("cal-api-version")
        captured["content_type"] = headers.get("content-type")
        captured["body"] = request.data.decode("utf-8") if request.data else None
        captured["timeout"] = timeout
        return _FakeResponse({"data": {"ok": True}})

    monkeypatch.setattr("app.services.calcom_provider.urlopen", fake_urlopen)

    payload = provider._request(
        "POST",
        "/v2/bookings",
        {"access_token": "secret-token", "base_url": "https://api.example.com/"},
        {"title": "Sales Demo"},
    )

    assert payload == {"data": {"ok": True}}
    assert captured == {
        "url": "https://api.example.com/v2/bookings",
        "method": "POST",
        "auth": "Bearer secret-token",
        "api_version": CALCOM_API_VERSION,
        "content_type": "application/json",
        "body": '{"title": "Sales Demo"}',
        "timeout": 15,
    }


def test_calcom_request_handles_missing_token_and_transport_errors(monkeypatch):
    provider = CalComProvider()

    with pytest.raises(HTTPException, match="missing an access token"):
        provider._request("GET", "/v2/slots", {}, None)

    def raise_http_error(request, timeout):
        raise HTTPError(
            url=request.full_url,
            code=500,
            msg="server exploded",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"calendar unavailable"}'),
        )

    monkeypatch.setattr("app.services.calcom_provider.urlopen", raise_http_error)
    with pytest.raises(HTTPException, match="Cal.com request failed"):
        provider._request("GET", "/v2/slots", {"access_token": "token"}, None)

    def raise_url_error(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("app.services.calcom_provider.urlopen", raise_url_error)
    with pytest.raises(HTTPException, match="Cal.com is unreachable: connection refused"):
        provider._request("GET", "/v2/slots", {"access_token": "token"}, None)
