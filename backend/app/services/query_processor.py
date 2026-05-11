from __future__ import annotations

import logging
import re
from collections import OrderedDict
from dataclasses import dataclass

from app.services.embedder import OpenAIEmbedder

logger = logging.getLogger(__name__)


@dataclass
class ProcessedQuery:
    original_query: str
    normalized_query: str
    keywords: list[str]
    embedding: list[float]


class QueryProcessor:
    _embedding_cache: "OrderedDict[str, list[float]]" = OrderedDict()

    def __init__(self, embedder: OpenAIEmbedder, cache_size: int = 256) -> None:
        self.embedder = embedder
        self.cache_size = cache_size

    def process(self, query: str) -> ProcessedQuery:
        normalized_query = self.normalize(query)
        keywords = self._extract_keywords(normalized_query)
        embedding = self._get_or_create_embedding(normalized_query)
        logger.info("Processed query", extra={"normalized_query": normalized_query, "keywords": keywords})
        return ProcessedQuery(
            original_query=query,
            normalized_query=normalized_query,
            keywords=keywords,
            embedding=embedding,
        )

    def normalize(self, query: str) -> str:
        lowered = query.lower().strip()
        lowered = re.sub(r"[^\w\s:/.-]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.strip()

    def _extract_keywords(self, normalized_query: str) -> list[str]:
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "to",
            "for",
            "of",
            "on",
            "in",
            "and",
            "or",
            "with",
            "please",
            "show",
            "me",
        }
        keywords = [token for token in normalized_query.split() if token not in stopwords]
        return keywords or normalized_query.split()

    def _get_or_create_embedding(self, normalized_query: str) -> list[float]:
        cache = self.__class__._embedding_cache
        if normalized_query in cache:
            cache.move_to_end(normalized_query)
            logger.info("Query embedding cache hit", extra={"query": normalized_query})
            return cache[normalized_query]

        logger.info("Query embedding cache miss", extra={"query": normalized_query})
        embedding = self.embedder.embed_texts([normalized_query])[0]
        cache[normalized_query] = embedding
        while len(cache) > self.cache_size:
            cache.popitem(last=False)
        return embedding

