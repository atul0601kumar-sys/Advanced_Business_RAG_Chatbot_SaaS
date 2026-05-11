from __future__ import annotations

from app.schemas.scheduling import SchedulingIntentResponse


class SchedulingIntentDetector:
    BOOKING_TERMS = {
        "book a call",
        "book a demo",
        "schedule a meeting",
        "schedule a call",
        "book a meeting",
        "talk to sales",
        "talk to support",
        "set up a call",
        "demo",
        "meeting",
        "appointment",
        "consultation",
    }

    def detect(self, message: str, *, wants_human_support: bool = False, high_priority: bool = False) -> SchedulingIntentResponse:
        normalized = " ".join((message or "").lower().split())
        if wants_human_support:
            return SchedulingIntentResponse(detected=True, reason="human_support", should_prompt_for_booking=True)
        if high_priority:
            return SchedulingIntentResponse(detected=True, reason="high_priority_lead", should_prompt_for_booking=True)
        if any(term in normalized for term in self.BOOKING_TERMS):
            return SchedulingIntentResponse(detected=True, reason="explicit_booking_request", should_prompt_for_booking=True)
        return SchedulingIntentResponse(detected=False)
