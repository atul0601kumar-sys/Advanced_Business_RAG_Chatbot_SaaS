from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.faq_generator import OpenAIJsonClient, SourceMaterial

settings = get_settings()

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "your",
    "about",
    "have",
    "will",
    "what",
    "when",
    "where",
    "which",
    "while",
    "their",
    "there",
    "they",
    "them",
    "been",
    "were",
    "also",
    "than",
    "then",
    "only",
    "such",
    "using",
    "use",
    "can",
    "our",
}


@dataclass
class ExtractedTopic:
    name: str
    summary: str
    keywords: list[str] = field(default_factory=list)


class TopicExtractor:
    def __init__(self, json_client: OpenAIJsonClient | None = None) -> None:
        self.json_client = json_client or OpenAIJsonClient(settings.openai_api_key)

    def extract_topics(self, source: SourceMaterial) -> list[ExtractedTopic]:
        try:
            return self._llm_extract(source)
        except Exception:
            return self._fallback_extract(source)

    def _llm_extract(self, source: SourceMaterial) -> list[ExtractedTopic]:
        excerpt_block = "\n\n".join(
            f"[{excerpt.index}] {(excerpt.file_name or excerpt.url or 'source')}\n{excerpt.text[:700].strip()}"
            for excerpt in source.excerpts[:12]
        )
        payload = self.json_client.complete_json(
            system_prompt=(
                "You extract non-overlapping business knowledge topics from source content.\n"
                "Return JSON with a top-level 'topics' array.\n"
                "Each item must contain: name, summary, keywords.\n"
                "Topics must be grounded in the source and avoid duplication."
            ),
            user_prompt=(
                f"Source: {source.source_label}\n"
                "Review the excerpts and identify the strongest business-relevant topics.\n"
                f"{excerpt_block}"
            ),
        )
        topics = payload.get("topics") or []
        extracted: list[ExtractedTopic] = []
        for item in topics[:8]:
            name = str(item.get("name", "")).strip()
            summary = str(item.get("summary", "")).strip()
            keywords = [str(keyword).strip() for keyword in item.get("keywords", []) if str(keyword).strip()]
            if not name or not summary:
                continue
            extracted.append(ExtractedTopic(name=name, summary=summary, keywords=keywords[:8]))
        return extracted

    def _fallback_extract(self, source: SourceMaterial) -> list[ExtractedTopic]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9\\-]{3,}", source.content.lower())
        frequency = Counter(token for token in tokens if token not in STOPWORDS)
        common_keywords = [keyword for keyword, _ in frequency.most_common(12)]
        if not common_keywords:
            return []
        topics: list[ExtractedTopic] = []
        for offset in range(0, min(len(common_keywords), 9), 3):
            keyword_group = common_keywords[offset : offset + 3]
            if not keyword_group:
                continue
            label = " / ".join(keyword.title() for keyword in keyword_group[:2])
            related_excerpt = next(
                (excerpt for excerpt in source.excerpts if any(keyword in excerpt.text.lower() for keyword in keyword_group)),
                None,
            )
            summary = related_excerpt.text[:260].strip() if related_excerpt else source.content[:260].strip()
            topics.append(ExtractedTopic(name=label, summary=summary, keywords=keyword_group))
        return topics[:5]
