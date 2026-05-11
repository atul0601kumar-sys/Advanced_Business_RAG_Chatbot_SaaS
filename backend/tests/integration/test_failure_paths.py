from __future__ import annotations

import asyncio

import pytest

from app.services.filter_engine import FilterEngine
from app.services.query_processor import ProcessedQuery
from app.services.retrieval_service import RetrievalService


class FailingQueryProcessor:
    def process(self, query: str) -> ProcessedQuery:  # noqa: ARG002
        raise RuntimeError("embedding provider offline")


class EmptySearcher:
    def search(self, db, query_embedding, filters, top_k):  # noqa: ARG002
        return type("EmptyResult", (), {"hits": []})()


class EmptyReranker:
    def rerank(self, query, hits):  # noqa: ARG002
        return []


@pytest.mark.integration
def test_retrieval_service_falls_back_cleanly_when_embedding_generation_fails(db_session, seeded_workspace):
    service = RetrievalService(
        query_processor=FailingQueryProcessor(),
        vector_searcher=EmptySearcher(),
        keyword_searcher=EmptySearcher(),
        reranker=EmptyReranker(),
        filter_engine=FilterEngine(),
    )
    response = asyncio.run(service.retrieve(db_session, seeded_workspace.workspace_id, "revenue", None))
    assert response.results == []
    assert response.final_chunks_count == 0


@pytest.mark.integration
def test_global_exception_handler_returns_safe_500(api_client, auth_headers, seeded_workspace, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.api.v1.routes.analytics.AnalyticsService.get_overview", boom)
    response = api_client.get(f"/api/v1/analytics/overview?workspace_id={seeded_workspace.workspace_id}", headers=auth_headers)
    assert response.status_code == 500
    assert response.json()["detail"] == "An internal server error occurred."
