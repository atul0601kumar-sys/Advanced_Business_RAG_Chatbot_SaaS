from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.services.faq_generator import GeneratedFAQCandidate, SourceMaterial

SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"api[_ -]?key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
]


class FAQValidator:
    def normalize_question(self, question: str) -> str:
        normalized = re.sub(r"[^a-z0-9 ]+", " ", question.lower())
        normalized = " ".join(normalized.split())
        return normalized[:500]

    def validate_candidate(self, candidate: GeneratedFAQCandidate, source: SourceMaterial) -> GeneratedFAQCandidate | None:
        question = " ".join(candidate.question.strip().split())
        answer = " ".join(candidate.answer.strip().split())
        category = " ".join(candidate.category.strip().split()) or "General"
        if len(question) < 8 or len(answer) < 16:
            return None
        if not question.endswith("?"):
            question = question.rstrip(".") + "?"
        if any(pattern.search(answer) or pattern.search(question) for pattern in SENSITIVE_PATTERNS):
            return None
        if not self._is_grounded(answer, source):
            return None
        candidate.question = question[:500]
        candidate.answer = answer[:4000]
        candidate.category = category[:255]
        candidate.confidence_score = max(0.0, min(1.0, float(candidate.confidence_score)))
        return candidate

    def deduplicate_candidates(
        self,
        candidates: list[GeneratedFAQCandidate],
        *,
        existing_normalized_questions: set[str] | None = None,
    ) -> list[GeneratedFAQCandidate]:
        existing = existing_normalized_questions or set()
        unique: list[GeneratedFAQCandidate] = []
        seen_normalized: list[str] = []
        for candidate in sorted(candidates, key=lambda item: item.confidence_score, reverse=True):
            normalized = self.normalize_question(candidate.question)
            if not normalized or normalized in existing:
                continue
            if any(self._is_similar(normalized, prior) for prior in seen_normalized):
                continue
            seen_normalized.append(normalized)
            unique.append(candidate)
        return unique

    def _is_grounded(self, answer: str, source: SourceMaterial) -> bool:
        support_text = " ".join(excerpt.text.lower() for excerpt in source.excerpts[:15])
        answer_terms = [term for term in re.findall(r"[a-z0-9]{4,}", answer.lower()) if term not in {"that", "with", "from", "this"}]
        if not answer_terms:
            return False
        overlap = sum(1 for term in set(answer_terms) if term in support_text)
        return overlap >= max(2, int(len(set(answer_terms)) * 0.18))

    def _is_similar(self, left: str, right: str) -> bool:
        if left == right:
            return True
        if left in right or right in left:
            return True
        return SequenceMatcher(None, left, right).ratio() >= 0.86
