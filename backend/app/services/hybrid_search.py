from __future__ import annotations

import logging

from app.services.retrieval_types import SearchHit

logger = logging.getLogger(__name__)


class HybridSearcher:
    def combine(
        self,
        vector_hits: list[SearchHit],
        keyword_hits: list[SearchHit],
        top_k: int = 10,
    ) -> list[SearchHit]:
        normalized_vector_scores = self._normalize_scores([hit.vector_score for hit in vector_hits])
        normalized_keyword_scores = self._normalize_scores([hit.keyword_score for hit in keyword_hits])

        merged: dict[str, SearchHit] = {}
        for hit, normalized_score in zip(vector_hits, normalized_vector_scores, strict=False):
            merged[hit.chunk_id] = SearchHit(
                chunk_id=hit.chunk_id,
                text=hit.text,
                vector_score=normalized_score,
                keyword_score=0.0,
                metadata=hit.metadata,
            )

        for hit, normalized_score in zip(keyword_hits, normalized_keyword_scores, strict=False):
            existing = merged.get(hit.chunk_id)
            if existing:
                existing.keyword_score = normalized_score
            else:
                merged[hit.chunk_id] = SearchHit(
                    chunk_id=hit.chunk_id,
                    text=hit.text,
                    vector_score=0.0,
                    keyword_score=normalized_score,
                    metadata=hit.metadata,
                )

        combined = list(merged.values())
        for hit in combined:
            hit.hybrid_score = (0.7 * hit.vector_score) + (0.3 * hit.keyword_score)

        combined.sort(key=lambda hit: hit.hybrid_score, reverse=True)
        logger.info("Hybrid search combined results", extra={"combined_count": len(combined)})
        return combined[:top_k]

    def _normalize_scores(self, scores: list[float]) -> list[float]:
        if not scores:
            return []
        min_score = min(scores)
        max_score = max(scores)
        if max_score == min_score:
            return [1.0 if score > 0 else 0.0 for score in scores]
        return [(score - min_score) / (max_score - min_score) for score in scores]

