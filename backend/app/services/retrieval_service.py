from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.retrieval import RetrievalResponse, RetrievalResultItem, RetrievalResultMetadata
from app.services.context_builder import ContextBuilder
from app.services.embedder import OpenAIEmbedder
from app.services.filter_engine import FilterEngine
from app.services.hybrid_search import HybridSearcher
from app.services.keyword_search import KeywordSearcher
from app.services.query_processor import QueryProcessor
from app.services.reranker import OpenAIReranker
from app.services.retrieval_types import SearchHit
from app.services.settings_service import SettingsService
from app.services.vector_search import VectorSearcher
from app.services.vector_store import QdrantVectorStore

settings = get_settings()
logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(
        self,
        query_processor: QueryProcessor | None = None,
        vector_searcher: VectorSearcher | None = None,
        keyword_searcher: KeywordSearcher | None = None,
        hybrid_searcher: HybridSearcher | None = None,
        reranker: OpenAIReranker | None = None,
        filter_engine: FilterEngine | None = None,
        context_builder: ContextBuilder | None = None,
        settings_service: SettingsService | None = None,
    ) -> None:
        embedder = OpenAIEmbedder(api_key=settings.openai_api_key)
        self.filter_engine = filter_engine or FilterEngine()
        self.query_processor = query_processor or QueryProcessor(embedder)
        self.vector_searcher = vector_searcher or VectorSearcher(QdrantVectorStore())
        self.keyword_searcher = keyword_searcher or KeywordSearcher(self.filter_engine)
        self.hybrid_searcher = hybrid_searcher or HybridSearcher()
        self.reranker = reranker or OpenAIReranker(api_key=settings.openai_api_key)
        self.context_builder = context_builder or ContextBuilder(settings.retrieval_context_token_limit)
        self.settings_service = settings_service or SettingsService()

    async def retrieve(self, db: Session, workspace_id, query: str, request_filters) -> RetrievalResponse:
        filters = self.filter_engine.build_filters(workspace_id, request_filters)
        chatbot_setting = self.settings_service.get_setting_for_runtime(db, workspace_id)
        knowledge_settings = chatbot_setting.knowledge_base_config_json or {}
        try:
            processed = await asyncio.to_thread(self.query_processor.process, query)
            vector_result = self.vector_searcher.search(
                db,
                processed.embedding,
                filters,
                settings.retrieval_vector_top_k,
            )
            keyword_result = self.keyword_searcher.search(
                db,
                processed.normalized_query,
                filters,
                settings.retrieval_keyword_top_k,
            )

            hybrid_hits = self.hybrid_searcher.combine(
                vector_result.hits,
                keyword_result.hits,
                settings.retrieval_hybrid_top_k,
            )
            rerank_scores = await asyncio.to_thread(self.reranker.rerank, processed.normalized_query, hybrid_hits)

            for hit, rerank_score in zip(hybrid_hits, rerank_scores, strict=False):
                hit.rerank_score = float(rerank_score)

            hybrid_hits = self._apply_workspace_knowledge_settings(hybrid_hits, knowledge_settings)
            reranked_hits = sorted(
                hybrid_hits,
                key=lambda hit: (hit.rerank_score, hit.hybrid_score),
                reverse=True,
            )[: settings.retrieval_final_top_k]

            _ = self.context_builder.build(reranked_hits)
            logger.info(
                "Retrieval completed",
                extra={
                    "workspace_id": str(workspace_id),
                    "query": processed.normalized_query,
                    "vector_candidates": len(vector_result.hits),
                    "keyword_candidates": len(keyword_result.hits),
                    "selected_chunks": [hit.chunk_id for hit in reranked_hits],
                },
            )
            return RetrievalResponse(
                query=query,
                results=[self._serialize_hit(hit) for hit in reranked_hits],
                final_chunks_count=len(reranked_hits),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Retrieval failed", extra={"workspace_id": str(workspace_id), "query": query})
            return RetrievalResponse(query=query, results=[], final_chunks_count=0)

    def _apply_workspace_knowledge_settings(self, hits: list[SearchHit], config: dict) -> list[SearchHit]:
        disabled_document_ids = {str(item) for item in config.get("disabled_document_ids", [])}
        prioritized_document_ids = {str(item) for item in config.get("prioritized_document_ids", [])}
        disabled_urls = {item.strip() for item in config.get("disabled_urls", []) if item}
        prioritized_urls = {item.strip() for item in config.get("prioritized_urls", []) if item}
        threshold = float(config.get("chunk_relevance_threshold", 0.15))
        filtered: list[SearchHit] = []
        for hit in hits:
            metadata = hit.metadata or {}
            document_id = str(metadata.get("document_id") or "")
            url = str(metadata.get("url") or metadata.get("source_location") or "")
            if document_id and document_id in disabled_document_ids:
                continue
            if url and url in disabled_urls:
                continue
            if hit.rerank_score < threshold and hit.hybrid_score < threshold:
                continue
            if document_id and document_id in prioritized_document_ids:
                hit.rerank_score += 0.1
                hit.hybrid_score += 0.05
            if url and url in prioritized_urls:
                hit.rerank_score += 0.1
                hit.hybrid_score += 0.05
            filtered.append(hit)
        return filtered

    def _serialize_hit(self, hit: SearchHit) -> RetrievalResultItem:
        metadata = hit.metadata or {}
        return RetrievalResultItem(
            chunk_id=hit.chunk_id,
            text=hit.text,
            vector_score=float(hit.vector_score),
            keyword_score=float(hit.keyword_score),
            hybrid_score=float(hit.hybrid_score),
            rerank_score=float(hit.rerank_score),
            metadata=RetrievalResultMetadata(
                document_id=metadata.get("document_id"),
                file_name=metadata.get("file_name"),
                page_number=metadata.get("page_number"),
                url=metadata.get("url") or metadata.get("source_location"),
                workspace_id=metadata.get("workspace_id"),
            ),
        )
