from __future__ import annotations

import asyncio
import uuid

import pytest

from app.models import ChatMessage
from app.schemas.retrieval import RetrievalResponse, RetrievalResultItem, RetrievalResultMetadata
from app.services.memory_manager import MemoryManager
from app.services.prompt_builder import FALLBACK_ANSWER
from app.services.rag_service import RagService


class EmptyKnowledgeRetrievalService:
    async def retrieve(self, db, workspace_id, query, request_filters):  # noqa: ARG002
        return RetrievalResponse(query=query, results=[], final_chunks_count=0)


class ConflictingKnowledgeRetrievalService:
    async def retrieve(self, db, workspace_id, query, request_filters):  # noqa: ARG002
        return RetrievalResponse(
            query=query,
            final_chunks_count=2,
            results=[
                RetrievalResultItem(
                    chunk_id="conflict-1",
                    text="The contract renewal period is 30 days.",
                    vector_score=0.83,
                    keyword_score=0.56,
                    hybrid_score=0.71,
                    rerank_score=0.78,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-1",
                        file_name="policy-a.txt",
                        page_number=1,
                        workspace_id=str(workspace_id),
                    ),
                ),
                RetrievalResultItem(
                    chunk_id="conflict-2",
                    text="The contract renewal period is 60 days.",
                    vector_score=0.81,
                    keyword_score=0.58,
                    hybrid_score=0.72,
                    rerank_score=0.79,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-2",
                        file_name="policy-b.txt",
                        page_number=2,
                        workspace_id=str(workspace_id),
                    ),
                ),
            ],
        )


class FailingChatClient:
    def complete(self, messages):  # noqa: ARG002
        raise RuntimeError("llm timeout")


def _memory_snapshot():
    return type("Memory", (), {"summary": None, "recent_messages": [], "updated_summary": None})()


def test_memory_manager_summarizes_long_conversations_without_overflow():
    chat_session_id = uuid.uuid4()
    messages = [
        ChatMessage(
            chat_session_id=chat_session_id,
            role="user" if index % 2 == 0 else "assistant",
            content=("Quarterly update " * 4) + str(index),
        )
        for index in range(10)
    ]
    manager = MemoryManager(recent_message_limit=4, token_limit=50, summary_trigger_message_count=3)

    snapshot = manager.build_memory(messages, None, summarizer=lambda existing, older: "summarized history")  # noqa: ARG005

    assert snapshot.updated_summary == "summarized history"
    assert len(snapshot.recent_messages) <= 4
    assert sum(manager.token_estimator(message.content) for message in snapshot.recent_messages) <= 50


@pytest.mark.parametrize(
    "query",
    [
        " ".join(["revenue"] * 400),
        "Can you clarify that?",
        "What does the knowledge base say here?",
    ],
)
def test_rag_service_uses_safe_fallback_for_empty_irrelevant_and_ambiguous_queries(db_session, seeded_workspace, query):
    service = RagService(retrieval_service=EmptyKnowledgeRetrievalService())

    response = asyncio.run(
        service.generate_answer(
            db_session,
            seeded_workspace.workspace_id,
            query,
            "detailed",
            None,
            memory=_memory_snapshot(),
            prior_messages=[],
        )
    )

    assert response.answer == FALLBACK_ANSWER
    assert response.citations == []
    assert response.metadata.retrieved_chunks == 0


def test_rag_service_returns_safe_fallback_for_conflicting_sources_when_llm_fails(db_session, seeded_workspace):
    service = RagService(
        retrieval_service=ConflictingKnowledgeRetrievalService(),
        chat_client=FailingChatClient(),
    )

    response = asyncio.run(
        service.generate_answer(
            db_session,
            seeded_workspace.workspace_id,
            "What is the renewal period?",
            "detailed",
            None,
            memory=_memory_snapshot(),
            prior_messages=[],
        )
    )

    assert response.answer == FALLBACK_ANSWER
    assert len(response.citations) == 2
    assert response.metadata.retrieved_chunks == 2
