from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentChunk
from app.services.filter_engine import FilterEngine
from app.services.retrieval_types import RetrievalFilters, SearchHit

logger = logging.getLogger(__name__)


@dataclass
class KeywordSearchResult:
    hits: list[SearchHit]


class KeywordSearcher:
    def __init__(self, filter_engine: FilterEngine) -> None:
        self.filter_engine = filter_engine

    def search(
        self,
        db: Session,
        normalized_query: str,
        filters: RetrievalFilters,
        top_k: int = 20,
    ) -> KeywordSearchResult:
        statement = select(DocumentChunk)
        statement = self.filter_engine.apply_sql_filters(statement, filters)
        chunks = db.scalars(statement).all()
        if not chunks:
            logger.info("Keyword search found no candidate chunks", extra={"workspace_id": filters.workspace_id})
            return KeywordSearchResult(hits=[])

        query_terms = self._tokenize(normalized_query)
        if not query_terms:
            return KeywordSearchResult(hits=[])

        doc_tokens = [self._tokenize(chunk.content) for chunk in chunks]
        avg_doc_len = sum(len(tokens) for tokens in doc_tokens) / max(len(doc_tokens), 1)
        term_doc_freq = {
            term: sum(1 for tokens in doc_tokens if term in tokens)
            for term in query_terms
        }

        hits: list[SearchHit] = []
        total_docs = len(chunks)
        k1 = 1.5
        b = 0.75

        for chunk, tokens in zip(chunks, doc_tokens, strict=False):
            doc_len = len(tokens) or 1
            term_counts: dict[str, int] = {}
            for token in tokens:
                term_counts[token] = term_counts.get(token, 0) + 1

            score = 0.0
            for term in query_terms:
                if term not in term_counts:
                    continue
                doc_freq = term_doc_freq[term]
                idf = math.log(1 + ((total_docs - doc_freq + 0.5) / (doc_freq + 0.5)))
                tf = term_counts[term]
                score += idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_doc_len))))

            if score <= 0:
                continue

            hits.append(
                SearchHit(
                    chunk_id=chunk.qdrant_point_id or str(chunk.id),
                    text=chunk.content,
                    keyword_score=float(score),
                    metadata=chunk.metadata_json or {},
                )
            )

        hits.sort(key=lambda hit: hit.keyword_score, reverse=True)
        logger.info(
            "Keyword search completed",
            extra={"workspace_id": filters.workspace_id, "candidate_count": len(hits)},
        )
        return KeywordSearchResult(hits=hits[:top_k])

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

