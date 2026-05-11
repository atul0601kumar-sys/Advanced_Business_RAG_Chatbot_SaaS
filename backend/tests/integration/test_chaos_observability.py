from __future__ import annotations

import asyncio
import logging
import time

import pytest
from sqlalchemy import select

from app.core.audit_logger import AuditAction
from app.models import AccessLog, AuditLog
from app.schemas.retrieval import RetrievalResponse, RetrievalResultItem, RetrievalResultMetadata
from app.services.prompt_builder import FALLBACK_ANSWER
from app.services.query_processor import ProcessedQuery
from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievalService


class StubProcessedQueryProcessor:
    def process(self, query: str) -> ProcessedQuery:
        return ProcessedQuery(
            original_query=query,
            normalized_query=query.lower(),
            embedding=[0.1, 0.2, 0.3],
        )


class FailingVectorSearcher:
    def search(self, db, query_embedding, filters, top_k):  # noqa: ARG002
        raise RuntimeError("vector store temporarily unavailable")


class EmptySearcher:
    def search(self, db, query_embedding, filters, top_k):  # noqa: ARG002
        return type("SearchResult", (), {"hits": []})()


class EmptyReranker:
    def rerank(self, query, hits):  # noqa: ARG002
        return []


class StaticRuntimeSettingsService:
    def get_setting_for_runtime(self, db, workspace_id):  # noqa: ARG002
        return type("RuntimeSetting", (), {"knowledge_base_config_json": {}, "analytics_config_json": {}})()


class EmptyRetrievalService:
    async def retrieve(self, db, workspace_id, query, request_filters):  # noqa: ARG002
        return RetrievalResponse(query=query, results=[], final_chunks_count=0)


class ConflictingRetrievalService:
    async def retrieve(self, db, workspace_id, query, request_filters):  # noqa: ARG002
        return RetrievalResponse(
            query=query,
            final_chunks_count=2,
            results=[
                RetrievalResultItem(
                    chunk_id="chunk-a",
                    text="Revenue decreased by 10 percent in Q1.",
                    vector_score=0.91,
                    keyword_score=0.61,
                    hybrid_score=0.82,
                    rerank_score=0.88,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-a",
                        file_name="finance-a.txt",
                        page_number=1,
                        workspace_id=str(workspace_id),
                    ),
                ),
                RetrievalResultItem(
                    chunk_id="chunk-b",
                    text="Revenue increased by 18 percent in Q1.",
                    vector_score=0.89,
                    keyword_score=0.64,
                    hybrid_score=0.84,
                    rerank_score=0.86,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-b",
                        file_name="finance-b.txt",
                        page_number=2,
                        workspace_id=str(workspace_id),
                    ),
                ),
            ],
        )


class FailingChatClient:
    def complete(self, messages):  # noqa: ARG002
        raise RuntimeError("llm provider timeout")

    def stream(self, messages, stop_event=None):  # noqa: ARG002
        raise RuntimeError("llm streaming unavailable")


@pytest.mark.integration
def test_vector_database_drop_returns_empty_retrieval_result(db_session, seeded_workspace):
    service = RetrievalService(
        query_processor=StubProcessedQueryProcessor(),
        vector_searcher=FailingVectorSearcher(),
        keyword_searcher=EmptySearcher(),
        reranker=EmptyReranker(),
        settings_service=StaticRuntimeSettingsService(),
    )

    response = asyncio.run(service.retrieve(db_session, seeded_workspace.workspace_id, "revenue status", None))

    assert response.results == []
    assert response.final_chunks_count == 0


@pytest.mark.integration
def test_llm_completion_failure_returns_safe_fallback_answer(db_session, seeded_workspace):
    service = RagService(
        retrieval_service=ConflictingRetrievalService(),
        chat_client=FailingChatClient(),
    )

    response = asyncio.run(
        service.generate_answer(
            db_session,
            seeded_workspace.workspace_id,
            "Which report is right?",
            "detailed",
            None,
            memory=type("Memory", (), {"summary": None, "recent_messages": [], "updated_summary": None})(),
            prior_messages=[],
        )
    )

    assert response.answer == FALLBACK_ANSWER
    assert len(response.citations) == 2
    assert response.metadata.retrieved_chunks == 2


@pytest.mark.integration
def test_llm_stream_failure_terminates_cleanly_with_safe_fallback(db_session, seeded_workspace):
    service = RagService(
        retrieval_service=ConflictingRetrievalService(),
        chat_client=FailingChatClient(),
    )

    # `stream_answer` expects a threading.Event-compatible object. A tiny shim keeps the test offline and deterministic.
    stop_event = type("StopEvent", (), {"is_set": lambda self: False})()
    events = asyncio.run(
        _collect_stream_events(
            service,
            db_session,
            seeded_workspace.workspace_id,
            "Resolve the contradiction.",
            stop_event,
        )
    )

    assert [event.event_type for event in events] == ["final"]
    assert events[-1].result is not None
    assert events[-1].result.answer == FALLBACK_ANSWER
    assert events[-1].result.metadata.stopped is False


async def _collect_stream_events(service: RagService, db_session, workspace_id, query: str, stop_event):
    events = []
    async for event in service.stream_answer(
        db_session,
        workspace_id,
        query,
        "detailed",
        None,
        memory=type("Memory", (), {"summary": None, "recent_messages": [], "updated_summary": None})(),
        prior_messages=[],
        stop_event=stop_event,
    ):
        events.append(event)
    return events


@pytest.mark.integration
def test_access_logs_record_successful_requests(api_client, auth_headers, db_session, seeded_workspace):
    response = api_client.get(
        f"/api/v1/workspaces/{seeded_workspace.workspace_id}/documents",
        headers=auth_headers,
    )

    assert response.status_code == 200
    db_session.expire_all()
    access_log = db_session.scalar(
        select(AccessLog)
        .where(AccessLog.path == f"/api/v1/workspaces/{seeded_workspace.workspace_id}/documents")
        .order_by(AccessLog.created_at.desc())
    )
    assert access_log is not None
    assert access_log.status_code == 200
    assert access_log.workspace_id == seeded_workspace.workspace_id
    assert access_log.request_id
    assert access_log.latency_ms >= 0


@pytest.mark.integration
def test_auth_audit_events_are_captured_in_audit_logs(api_client, db_session, seeded_workspace):
    response = api_client.post(
        "/api/v1/auth/login",
        headers={"User-Agent": "pytest-client"},
        json={"email": "owner@example.com", "password": "CorrectHorseBatteryStaple!"},
    )

    assert response.status_code == 200
    db_session.expire_all()
    audit_log = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == AuditAction.LOGIN_SUCCESS)
        .order_by(AuditLog.created_at.desc())
    )
    assert audit_log is not None
    assert audit_log.user_agent == "pytest-client"


@pytest.mark.integration
def test_error_logs_and_slow_request_latency_are_captured(api_client, auth_headers, db_session, seeded_workspace, monkeypatch, caplog):
    def slow_failure(*args, **kwargs):  # noqa: ARG001
        time.sleep(0.03)
        raise RuntimeError("analytics backend unavailable")

    monkeypatch.setattr("app.api.v1.routes.analytics.AnalyticsService.get_overview", slow_failure)

    with caplog.at_level(logging.ERROR):
        response = api_client.get(
            f"/api/v1/analytics/overview?workspace_id={seeded_workspace.workspace_id}",
            headers=auth_headers,
        )

    assert response.status_code == 500
    assert any("Unhandled application error" in record.getMessage() for record in caplog.records)

    db_session.expire_all()
    access_log = db_session.scalar(
        select(AccessLog)
        .where(AccessLog.path == "/api/v1/analytics/overview")
        .order_by(AccessLog.created_at.desc())
    )
    assert access_log is not None
    assert access_log.status_code == 500
    assert access_log.latency_ms >= 20
