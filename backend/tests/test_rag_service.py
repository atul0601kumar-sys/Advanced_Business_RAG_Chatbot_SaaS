import asyncio
import uuid

from app.schemas.retrieval import RetrievalResponse, RetrievalResultItem, RetrievalResultMetadata
from app.services.rag_service import RagService


class CompanyKnowledgeRetrievalService:
    async def retrieve(self, db, workspace_id, query, request_filters):  # noqa: ARG002
        return RetrievalResponse(
            query=query,
            final_chunks_count=2,
            results=[
                RetrievalResultItem(
                    chunk_id="company-1",
                    text=(
                        "Characteristics of a company include separate legal entity, perpetual succession, "
                        "limited liability, and transferability of shares."
                    ),
                    vector_score=0.91,
                    keyword_score=0.72,
                    hybrid_score=0.87,
                    rerank_score=0.92,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-company",
                        file_name="Introduction to Company.pdf",
                        page_number=15,
                        workspace_id=str(workspace_id),
                    ),
                ),
                RetrievalResultItem(
                    chunk_id="company-2",
                    text=(
                        "A company also has common seal concepts in traditional formulations and can own property "
                        "in its own name."
                    ),
                    vector_score=0.84,
                    keyword_score=0.61,
                    hybrid_score=0.79,
                    rerank_score=0.81,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-company",
                        file_name="Introduction to Company.pdf",
                        page_number=23,
                        workspace_id=str(workspace_id),
                    ),
                ),
            ],
        )


def _memory_snapshot():
    return type("Memory", (), {"summary": None, "recent_messages": [], "updated_summary": None})()


def test_rag_service_generates_grounded_extractive_answer_without_openai(db_session, seeded_workspace):
    service = RagService(
        retrieval_service=CompanyKnowledgeRetrievalService(),
        chat_provider="extractive",
    )

    response = asyncio.run(
        service.generate_answer(
            db_session,
            seeded_workspace.workspace_id,
            "What are the characteristics of a company?",
            "detailed",
            None,
            memory=_memory_snapshot(),
            prior_messages=[],
        )
    )

    answer_lower = response.answer.lower()
    assert "separate legal entity" in answer_lower
    assert "limited liability" in answer_lower
    assert response.metadata.answer_strategy == "extractive"
    assert response.metadata.retrieved_chunks == 2
    assert len(response.citations) >= 1
