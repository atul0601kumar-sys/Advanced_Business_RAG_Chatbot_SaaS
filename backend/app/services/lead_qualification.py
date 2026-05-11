from __future__ import annotations

import re

from app.schemas.lead import LeadPriority, LeadTag

SALES_KEYWORDS = {"pricing", "demo", "buy", "purchase", "enterprise", "quote", "sales"}
SUPPORT_KEYWORDS = {"support", "issue", "error", "bug", "help", "trouble", "problem"}
HIGH_INTENT_KEYWORDS = {"pricing", "demo", "buy", "purchase", "enterprise", "urgent"}


class LeadQualificationService:
    def qualify(
        self,
        *,
        message: str,
        use_case: str | None,
        repeated_attempts: int,
    ) -> dict[str, object]:
        normalized = " ".join((message or "").lower().split())
        use_case_text = (use_case or "").lower()
        haystack = f"{normalized} {use_case_text}".strip()
        words = set(re.findall(r"[a-z0-9']+", haystack))

        score = 0
        if words & SALES_KEYWORDS:
            score += 4
        if words & SUPPORT_KEYWORDS:
            score += 3
        if len((message or "").split()) >= 20:
            score += 2
        if repeated_attempts >= 2:
            score += 2
        if words & HIGH_INTENT_KEYWORDS:
            score += 3

        tag: LeadTag = "general"
        if words & SALES_KEYWORDS:
            tag = "sales"
        elif words & SUPPORT_KEYWORDS:
            tag = "support"

        priority: LeadPriority = "low"
        if score >= 7:
            priority = "high"
        elif score >= 4:
            priority = "medium"

        return {
            "priority": priority,
            "tag": tag,
            "high_intent": bool(words & HIGH_INTENT_KEYWORDS),
            "score": score,
        }
