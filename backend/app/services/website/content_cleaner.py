from __future__ import annotations

import re

from app.services.text_extractor import ExtractedSection

BOILERPLATE_PHRASES = {
    "all rights reserved",
    "privacy policy",
    "terms of service",
    "cookie policy",
    "subscribe to our newsletter",
    "accept cookies",
}


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_sections(sections: list[ExtractedSection]) -> list[ExtractedSection]:
    cleaned: list[ExtractedSection] = []
    seen_texts: set[str] = set()

    for section in sections:
        normalized = normalize_whitespace(section.text)
        if not normalized:
            continue
        stable_key = stable_text_key(normalized)
        lowered = normalized.lower()
        if stable_key in seen_texts:
            continue
        if looks_like_boilerplate(lowered):
            continue
        seen_texts.add(stable_key)
        cleaned.append(
            ExtractedSection(
                text=normalized,
                order=len(cleaned),
                section_type=section.section_type,
                page_number=section.page_number,
                metadata=dict(section.metadata),
            )
        )
    return cleaned


def looks_like_boilerplate(lowered_text: str) -> bool:
    if any(phrase in lowered_text for phrase in BOILERPLATE_PHRASES):
        return True
    if len(lowered_text.split()) <= 4 and any(hint in lowered_text for hint in {"menu", "home", "search", "login", "sign up"}):
        return True
    return False


def stable_text_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()
