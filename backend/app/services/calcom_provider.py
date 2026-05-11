from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services.calendar_provider_base import CalendarProviderBase, ProviderBookingResult, ProviderBusySlot
from app.schemas.scheduling import AvailableSlot

CALCOM_API_VERSION = "2026-02-25"


class CalComProvider(CalendarProviderBase):
    provider_name = "calcom"

    def __init__(self) -> None:
        self.settings = get_settings()

    def get_busy_slots(
        self,
        *,
        connection_metadata: dict[str, Any],
        start_time_utc: datetime,
        end_time_utc: datetime,
        timezone: str,
        meeting_type_metadata: dict[str, Any] | None = None,
    ) -> list[ProviderBusySlot]:
        event_type_id = (meeting_type_metadata or {}).get("calcom_event_type_id")
        event_type_slug = (meeting_type_metadata or {}).get("calcom_event_type_slug")
        username = (meeting_type_metadata or {}).get("calcom_username")
        team_slug = (meeting_type_metadata or {}).get("calcom_team_slug")
        organization_slug = (meeting_type_metadata or {}).get("calcom_organization_slug")
        duration = (meeting_type_metadata or {}).get("calcom_duration_minutes")
        if not event_type_id and not event_type_slug:
            return []
        params = {
            "start": start_time_utc.isoformat().replace("+00:00", "Z"),
            "end": end_time_utc.isoformat().replace("+00:00", "Z"),
            "timeZone": timezone,
            "format": "range",
        }
        if duration:
            params["duration"] = duration
        if event_type_id:
            params["eventTypeId"] = event_type_id
        else:
            params["eventTypeSlug"] = event_type_slug
            if username:
                params["username"] = username
            if team_slug:
                params["teamSlug"] = team_slug
            if organization_slug:
                params["organizationSlug"] = organization_slug
        payload = self._request("GET", f"/v2/slots?{urlencode(params)}", connection_metadata, None)
        busy_slots: list[ProviderBusySlot] = []
        for day_slots in (payload.get("data") or {}).values():
            for slot in day_slots:
                start_raw = slot.get("start")
                end_raw = slot.get("end")
                if not start_raw or not end_raw:
                    continue
                busy_slots.append(
                    ProviderBusySlot(
                        start_time_utc=datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(UTC),
                        end_time_utc=datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(UTC),
                    )
                )
        return busy_slots

    def get_available_slots(
        self,
        *,
        connection_metadata: dict[str, Any],
        start_time_utc: datetime,
        end_time_utc: datetime,
        timezone: str,
        meeting_type_metadata: dict[str, Any] | None = None,
    ) -> list[AvailableSlot]:
        event_type_id = (meeting_type_metadata or {}).get("calcom_event_type_id")
        event_type_slug = (meeting_type_metadata or {}).get("calcom_event_type_slug")
        username = (meeting_type_metadata or {}).get("calcom_username")
        team_slug = (meeting_type_metadata or {}).get("calcom_team_slug")
        organization_slug = (meeting_type_metadata or {}).get("calcom_organization_slug")
        duration = (meeting_type_metadata or {}).get("calcom_duration_minutes")
        if not event_type_id and not event_type_slug:
            return []
        params = {
            "start": start_time_utc.isoformat().replace("+00:00", "Z"),
            "end": end_time_utc.isoformat().replace("+00:00", "Z"),
            "timeZone": timezone,
            "format": "range",
        }
        if duration:
            params["duration"] = duration
        if event_type_id:
            params["eventTypeId"] = event_type_id
        else:
            params["eventTypeSlug"] = event_type_slug
            if username:
                params["username"] = username
            if team_slug:
                params["teamSlug"] = team_slug
            if organization_slug:
                params["organizationSlug"] = organization_slug
        payload = self._request("GET", f"/v2/slots?{urlencode(params)}", connection_metadata, None)
        slots: list[AvailableSlot] = []
        for day_slots in (payload.get("data") or {}).values():
            for slot in day_slots:
                start_raw = slot.get("start")
                end_raw = slot.get("end")
                if not start_raw:
                    continue
                start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(UTC)
                end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(UTC) if end_raw else start_dt
                slots.append(
                    AvailableSlot(
                        start_time_utc=start_dt,
                        end_time_utc=end_dt,
                        display_time=start_dt.astimezone(ZoneInfo(timezone)).strftime("%a, %b %d at %I:%M %p"),
                        timezone=timezone,
                        provider="calcom",
                        assigned_user_id=None,
                    )
                )
        return slots

    def create_booking(self, *, connection_metadata: dict[str, Any], booking_payload: dict[str, Any]) -> ProviderBookingResult:
        payload = self._request("POST", "/v2/bookings", connection_metadata, booking_payload)
        data = payload.get("data") or {}
        return ProviderBookingResult(
            external_event_id=str(data.get("uid") or data.get("id") or ""),
            meeting_link=data.get("meetingUrl") or booking_payload.get("meetingUrl"),
            raw=data,
        )

    def reschedule_booking(
        self,
        *,
        connection_metadata: dict[str, Any],
        external_event_id: str,
        booking_payload: dict[str, Any],
    ) -> ProviderBookingResult:
        payload = self._request("POST", f"/v2/bookings/{external_event_id}/reschedule", connection_metadata, booking_payload)
        data = payload.get("data") or {}
        return ProviderBookingResult(
            external_event_id=str(data.get("uid") or external_event_id),
            meeting_link=data.get("meetingUrl") or booking_payload.get("meetingUrl"),
            raw=data,
        )

    def cancel_booking(
        self,
        *,
        connection_metadata: dict[str, Any],
        external_event_id: str,
        reason: str | None = None,
    ) -> None:
        self._request("POST", f"/v2/bookings/{external_event_id}/cancel", connection_metadata, {"reason": reason} if reason else {})

    def _request(
        self,
        method: str,
        path: str,
        connection_metadata: dict[str, Any],
        body: dict[str, Any] | None,
    ) -> dict[str, Any]:
        base_url = (connection_metadata.get("base_url") or "https://api.cal.com").rstrip("/")
        token = connection_metadata.get("access_token")
        if not token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cal.com connection is missing an access token.")
        headers = {
            "Authorization": f"Bearer {token}",
            "cal-api-version": CALCOM_API_VERSION,
            "Content-Type": "application/json",
        }
        request = Request(
            f"{base_url}{path}",
            method=method,
            headers=headers,
            data=json.dumps(body or {}).encode("utf-8") if method != "GET" else None,
        )
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Cal.com request failed: {detail or exc.reason}") from exc
        except URLError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Cal.com is unreachable: {exc.reason}") from exc
