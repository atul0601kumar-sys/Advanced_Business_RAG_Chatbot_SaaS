from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ProviderBusySlot:
    start_time_utc: datetime
    end_time_utc: datetime


@dataclass
class ProviderBookingResult:
    external_event_id: str | None
    meeting_link: str | None
    raw: dict[str, Any] | None = None


class CalendarProviderBase(ABC):
    provider_name: str

    @abstractmethod
    def get_busy_slots(
        self,
        *,
        connection_metadata: dict[str, Any],
        start_time_utc: datetime,
        end_time_utc: datetime,
        timezone: str,
        meeting_type_metadata: dict[str, Any] | None = None,
    ) -> list[ProviderBusySlot]:
        raise NotImplementedError

    @abstractmethod
    def create_booking(
        self,
        *,
        connection_metadata: dict[str, Any],
        booking_payload: dict[str, Any],
    ) -> ProviderBookingResult:
        raise NotImplementedError

    @abstractmethod
    def reschedule_booking(
        self,
        *,
        connection_metadata: dict[str, Any],
        external_event_id: str,
        booking_payload: dict[str, Any],
    ) -> ProviderBookingResult:
        raise NotImplementedError

    @abstractmethod
    def cancel_booking(
        self,
        *,
        connection_metadata: dict[str, Any],
        external_event_id: str,
        reason: str | None = None,
    ) -> None:
        raise NotImplementedError
