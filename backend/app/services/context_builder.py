from __future__ import annotations

import logging
import re

from app.services.chunker import SmartChunker
from app.services.retrieval_types import SearchHit

logger = logging.getLogger(__name__)


class ContextBuilder:
    def __init__(self, token_limit: int) -> None:
        self.token_limit = token_limit
        self.token_estimator = SmartChunker().estimate_tokens

    def build(self, hits: list[SearchHit]) -> str:
        ordered_hits = sorted(
            hits,
            key=lambda hit: (
                hit.metadata.get("document_id", ""),
                hit.metadata.get("chunk_index", 0),
            ),
        )
        selected_segments: list[str] = []
        seen_hashes: set[str] = set()
        total_tokens = 0

        for hit in ordered_hits:
            normalized = re.sub(r"\s+", " ", hit.text).strip().lower()
            content_hash = hit.metadata.get("content_hash") or normalized
            if content_hash in seen_hashes:
                continue
            estimated_tokens = self.token_estimator(hit.text)
            if total_tokens + estimated_tokens > self.token_limit:
                break
            seen_hashes.add(content_hash)
            total_tokens += estimated_tokens
            selected_segments.append(hit.text.strip())

        logger.info("Context builder selected chunks", extra={"selected_count": len(selected_segments), "total_tokens": total_tokens})
        return "\n\n".join(selected_segments)

