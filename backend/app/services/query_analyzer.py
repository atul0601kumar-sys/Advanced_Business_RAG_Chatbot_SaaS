from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import re

from app.schemas.analytics import KeywordInsightItem, QueryInsightItem, TopicClusterItem

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "do",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "our",
    "please",
    "the",
    "to",
    "we",
    "what",
    "when",
    "where",
    "with",
    "you",
    "your",
}
TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


@dataclass
class QueryRecord:
    raw_query: str
    normalized_query: str
    occurred_at: datetime | None


class QueryAnalyzer:
    def normalize_query(self, text: str) -> str:
        normalized = " ".join(text.lower().split())
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        return normalized[:500]

    def build_query_records(self, values: list[tuple[str, datetime | None]]) -> list[QueryRecord]:
        records: list[QueryRecord] = []
        for raw_query, occurred_at in values:
            trimmed = " ".join(raw_query.split()).strip()
            if not trimmed:
                continue
            records.append(
                QueryRecord(
                    raw_query=trimmed,
                    normalized_query=self.normalize_query(trimmed),
                    occurred_at=occurred_at,
                )
            )
        return records

    def top_questions(self, records: list[QueryRecord], limit: int = 10) -> list[QueryInsightItem]:
        counter = Counter(record.normalized_query for record in records if record.normalized_query)
        latest_seen: dict[str, datetime | None] = {}
        sample_text: dict[str, str] = {}
        total = sum(counter.values()) or 1
        for record in records:
            if not record.normalized_query:
                continue
            sample_text.setdefault(record.normalized_query, record.raw_query)
            previous = latest_seen.get(record.normalized_query)
            if previous is None or (record.occurred_at and record.occurred_at > previous):
                latest_seen[record.normalized_query] = record.occurred_at
        return [
            QueryInsightItem(
                query=sample_text[key],
                count=count,
                share=round((count / total) * 100, 2),
                last_seen_at=latest_seen.get(key),
            )
            for key, count in counter.most_common(limit)
        ]

    def repeated_queries(self, records: list[QueryRecord], limit: int = 10) -> list[QueryInsightItem]:
        repeated = [item for item in self.top_questions(records, limit=limit * 2) if item.count > 1]
        return repeated[:limit]

    def extract_keywords(self, records: list[QueryRecord], limit: int = 12) -> list[KeywordInsightItem]:
        counts: Counter[str] = Counter()
        for record in records:
            counts.update(self._tokenize(record.normalized_query))
        return [KeywordInsightItem(keyword=keyword, count=count) for keyword, count in counts.most_common(limit)]

    def cluster_topics(self, records: list[QueryRecord], limit: int = 8) -> list[TopicClusterItem]:
        grouped: defaultdict[str, list[str]] = defaultdict(list)
        for record in records:
            tokens = self._tokenize(record.normalized_query)
            topic = tokens[0] if tokens else "general"
            grouped[topic].append(record.raw_query)
        clusters = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
        return [
            TopicClusterItem(
                topic=topic.replace("_", " ").title(),
                count=len(queries),
                sample_queries=queries[:3],
            )
            for topic, queries in clusters[:limit]
        ]

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in TOKEN_RE.findall(text) if token not in STOPWORDS]

