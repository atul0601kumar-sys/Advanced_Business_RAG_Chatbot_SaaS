from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from app.core.config import get_settings

settings = get_settings()


@dataclass
class SourceExcerpt:
    index: int
    chunk_id: str
    text: str
    file_name: str | None = None
    page_number: int | None = None
    url: str | None = None


@dataclass
class SourceMaterial:
    workspace_id: str
    source_type: str
    source_id: str
    source_label: str
    fingerprint: str
    content: str
    excerpts: list[SourceExcerpt] = field(default_factory=list)


@dataclass
class CitationDraft:
    document_id: str | None = None
    file_name: str | None = None
    page_number: int | None = None
    url: str | None = None
    chunk_preview: str = ""


@dataclass
class GeneratedFAQCandidate:
    question: str
    answer: str
    category: str
    source: str
    confidence_score: float
    citations: list[CitationDraft] = field(default_factory=list)
    source_type: str | None = None
    source_id: str | None = None
    generation_fingerprint: str | None = None


class OpenAIJsonClient:
    def __init__(self, api_key: str, model: str | None = None, endpoint: str = "https://api.openai.com/v1/chat/completions") -> None:
        self.api_key = api_key
        self.model = model or settings.openai_chat_model
        self.endpoint = endpoint

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.api_key or self.api_key == "your_openai_api_key":
            raise RuntimeError("OpenAI API key is not configured.")
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        for attempt in range(settings.openai_max_retries):
            request = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                    content = parsed["choices"][0]["message"]["content"]
                    return json.loads(content)
            except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
                if attempt == settings.openai_max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("OpenAI JSON request exhausted retries.")


class FAQGenerator:
    def __init__(self, json_client: OpenAIJsonClient | None = None) -> None:
        self.json_client = json_client or OpenAIJsonClient(settings.openai_api_key)

    def generate(
        self,
        source: SourceMaterial,
        topics: list,
        *,
        max_faqs_per_source: int = 5,
    ) -> list[GeneratedFAQCandidate]:
        if not topics:
            return self._fallback_generate(source, max_faqs_per_source=max_faqs_per_source)
        try:
            return self._llm_generate(source, topics, max_faqs_per_source=max_faqs_per_source)
        except Exception:
            return self._fallback_generate(source, max_faqs_per_source=max_faqs_per_source, topics=topics)

    def _llm_generate(self, source: SourceMaterial, topics: list, *, max_faqs_per_source: int) -> list[GeneratedFAQCandidate]:
        topic_block = "\n".join(
            f"- {topic.name}: {topic.summary} | keywords: {', '.join(topic.keywords[:5])}"
            for topic in topics[:8]
        )
        excerpt_block = "\n\n".join(
            self._format_excerpt(excerpt) for excerpt in source.excerpts[: min(len(source.excerpts), 14)]
        )
        payload = self.json_client.complete_json(
            system_prompt=(
                "You generate business-grade FAQs grounded only in the provided source excerpts.\n"
                "Return JSON with a top-level 'faqs' array.\n"
                "Each FAQ must contain: question, answer, category, confidence_score, citation_indices.\n"
                "Questions must be specific, practical, and non-generic.\n"
                "Answers must be concise, accurate, and fully supported by cited excerpts.\n"
                "Never invent pricing, policies, SLAs, guarantees, dates, or product capabilities."
            ),
            user_prompt=(
                f"Source label: {source.source_label}\n"
                f"Target FAQ limit: {max_faqs_per_source}\n"
                f"Topics:\n{topic_block}\n\n"
                "Source excerpts:\n"
                f"{excerpt_block}\n\n"
                "Generate useful FAQs that a real buyer, customer, employee, or admin would ask."
            ),
        )
        faqs = payload.get("faqs") or []
        candidates: list[GeneratedFAQCandidate] = []
        for item in faqs[:max_faqs_per_source]:
            citation_indices = [int(idx) for idx in item.get("citation_indices", []) if isinstance(idx, int | float)]
            citations = self._build_citations(source, citation_indices)
            candidates.append(
                GeneratedFAQCandidate(
                    question=str(item.get("question", "")).strip(),
                    answer=str(item.get("answer", "")).strip(),
                    category=str(item.get("category", "General")).strip() or "General",
                    source=source.source_label,
                    confidence_score=self._clamp_score(item.get("confidence_score", 0.6)),
                    citations=citations,
                    source_type=source.source_type,
                    source_id=source.source_id,
                    generation_fingerprint=source.fingerprint,
                )
            )
        return candidates

    def _fallback_generate(self, source: SourceMaterial, max_faqs_per_source: int, topics: list | None = None) -> list[GeneratedFAQCandidate]:
        excerpts = source.excerpts[: max(1, min(len(source.excerpts), max_faqs_per_source))]
        derived_topics = topics or []
        candidates: list[GeneratedFAQCandidate] = []
        for index, excerpt in enumerate(excerpts, start=1):
            topic_name = derived_topics[index - 1].name if index - 1 < len(derived_topics) else "Knowledge Base"
            summary = derived_topics[index - 1].summary if index - 1 < len(derived_topics) else excerpt.text[:280]
            question = f"What should users know about {topic_name.lower()}?"
            candidates.append(
                GeneratedFAQCandidate(
                    question=question,
                    answer=summary.strip().rstrip(".") + ".",
                    category=topic_name,
                    source=source.source_label,
                    confidence_score=0.58,
                    citations=self._build_citations(source, [excerpt.index]),
                    source_type=source.source_type,
                    source_id=source.source_id,
                    generation_fingerprint=source.fingerprint,
                )
            )
        return candidates[:max_faqs_per_source]

    def _build_citations(self, source: SourceMaterial, citation_indices: list[int]) -> list[CitationDraft]:
        citations: list[CitationDraft] = []
        excerpt_by_index = {excerpt.index: excerpt for excerpt in source.excerpts}
        for citation_index in citation_indices:
            excerpt = excerpt_by_index.get(citation_index)
            if excerpt is None:
                continue
            citations.append(
                CitationDraft(
                    file_name=excerpt.file_name,
                    page_number=excerpt.page_number,
                    url=excerpt.url,
                    chunk_preview=excerpt.text[:220].strip(),
                )
            )
        return citations

    def _format_excerpt(self, excerpt: SourceExcerpt) -> str:
        location = excerpt.file_name or excerpt.url or "source"
        if excerpt.page_number is not None:
            location = f"{location} | page {excerpt.page_number}"
        return f"[{excerpt.index}] {location}\n{excerpt.text[:900].strip()}"

    def _clamp_score(self, value: object) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.5
        return max(0.0, min(1.0, math.floor(numeric * 100) / 100))
