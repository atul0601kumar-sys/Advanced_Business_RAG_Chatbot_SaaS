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


class NoisyCompanyKnowledgeRetrievalService:
    async def retrieve(self, db, workspace_id, query, request_filters):  # noqa: ARG002
        return RetrievalResponse(
            query=query,
            final_chunks_count=2,
            results=[
                RetrievalResultItem(
                    chunk_id="company-outline",
                    text=(
                        "LESSON 1.0 MEANING 1.1 INTRODUCTION 1.2 MEANING OF COMPANY "
                        "1.3 CHARACTERISTICS OF A COMPANY 1.4 DISTINCTION BETWEEN COMPANY AND PARTNERSHIP"
                    ),
                    vector_score=0.95,
                    keyword_score=0.81,
                    hybrid_score=0.9,
                    rerank_score=0.94,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-company",
                        file_name="Introduction to Company.pdf",
                        page_number=1,
                        workspace_id=str(workspace_id),
                    ),
                ),
                RetrievalResultItem(
                    chunk_id="company-private-heading",
                    text=(
                        "Characteristics or Features of a Private Company. MEANING, CHARACTERISTICS AND TYPES OF "
                        "A COMPANY 1.3 Characteristics of a Company company by altering its Articles in such a "
                        "manner that they no longer include essential clauses."
                    ),
                    vector_score=0.89,
                    keyword_score=0.68,
                    hybrid_score=0.84,
                    rerank_score=0.9,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-company",
                        file_name="Introduction to Company.pdf",
                        page_number=23,
                        workspace_id=str(workspace_id),
                    ),
                ),
                RetrievalResultItem(
                    chunk_id="company-explanation",
                    text=(
                        "The main characteristics of a company include separate legal entity, perpetual succession, "
                        "limited liability, and transferability of shares. A company can also own property in its own name."
                    ),
                    vector_score=0.88,
                    keyword_score=0.64,
                    hybrid_score=0.82,
                    rerank_score=0.86,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-company",
                        file_name="Introduction to Company.pdf",
                        page_number=15,
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


def test_rag_service_prefers_explanatory_sentences_over_outline_noise(db_session, seeded_workspace):
    service = RagService(
        retrieval_service=NoisyCompanyKnowledgeRetrievalService(),
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
    assert "lesson 1.0" not in answer_lower
    assert "characteristics and types of a company" not in answer_lower
    assert "private company" not in answer_lower


class IncompleteLeadInRetrievalService:
    async def retrieve(self, db, workspace_id, query, request_filters):  # noqa: ARG002
        return RetrievalResponse(
            query=query,
            final_chunks_count=1,
            results=[
                RetrievalResultItem(
                    chunk_id="company-leadin",
                    text=(
                        "The main characteristics of a company are : "
                        "A company has separate legal entity, perpetual succession, limited liability, and "
                        "transferability of shares."
                    ),
                    vector_score=0.9,
                    keyword_score=0.7,
                    hybrid_score=0.85,
                    rerank_score=0.91,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-company",
                        file_name="Introduction to Company.pdf",
                        page_number=26,
                        workspace_id=str(workspace_id),
                    ),
                ),
            ],
        )


def test_rag_service_adds_follow_up_after_incomplete_lead_in(db_session, seeded_workspace):
    service = RagService(
        retrieval_service=IncompleteLeadInRetrievalService(),
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
    assert "the main characteristics of a company are" in answer_lower
    assert "separate legal entity" in answer_lower
    assert "limited liability" in answer_lower


class IncludesStyleRetrievalService:
    async def retrieve(self, db, workspace_id, query, request_filters):  # noqa: ARG002
        return RetrievalResponse(
            query=query,
            final_chunks_count=1,
            results=[
                RetrievalResultItem(
                    chunk_id="company-includes",
                    text=(
                        "The main characteristics of a company include separate legal entity, perpetual succession, "
                        "limited liability, and transferability of shares."
                    ),
                    vector_score=0.92,
                    keyword_score=0.74,
                    hybrid_score=0.86,
                    rerank_score=0.93,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-company",
                        file_name="Introduction to Company.pdf",
                        page_number=26,
                        workspace_id=str(workspace_id),
                    ),
                ),
            ],
        )


def test_rag_service_rewrites_direct_answer_from_includes_sentence(db_session, seeded_workspace):
    service = RagService(
        retrieval_service=IncludesStyleRetrievalService(),
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
    assert answer_lower.startswith("the main characteristics of a company are")
    assert "separate legal entity" in answer_lower
    assert "limited liability" in answer_lower


class StubOllamaChatClient:
    def complete(self, messages):  # noqa: ANN001
        return "A company is characterized by separate legal entity, perpetual succession, and limited liability."

    def stream(self, messages, stop_event=None):  # noqa: ANN001
        yield "A company is characterized by separate legal entity, perpetual succession, and limited liability."


def test_rag_service_supports_ollama_provider_with_custom_client(db_session, seeded_workspace):
    service = RagService(
        retrieval_service=CompanyKnowledgeRetrievalService(),
        chat_client=StubOllamaChatClient(),
        chat_provider="ollama",
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
    assert response.metadata.answer_strategy == "rag"
    assert len(response.citations) >= 1


class HeadingOnlyTopHitRetrievalService:
    async def retrieve(self, db, workspace_id, query, request_filters):  # noqa: ARG002
        return RetrievalResponse(
            query=query,
            final_chunks_count=2,
            results=[
                RetrievalResultItem(
                    chunk_id="company-heading-only",
                    text="1.3 Characteristics of a Company",
                    vector_score=0.97,
                    keyword_score=0.82,
                    hybrid_score=0.91,
                    rerank_score=0.96,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-company",
                        file_name="Introduction to Company.pdf",
                        page_number=3,
                        workspace_id=str(workspace_id),
                    ),
                ),
                RetrievalResultItem(
                    chunk_id="company-real-answer",
                    text=(
                        "The main characteristics of a company include separate legal entity, perpetual succession, "
                        "limited liability, and transferability of shares."
                    ),
                    vector_score=0.89,
                    keyword_score=0.7,
                    hybrid_score=0.85,
                    rerank_score=0.9,
                    metadata=RetrievalResultMetadata(
                        document_id="doc-company",
                        file_name="Introduction to Company.pdf",
                        page_number=26,
                        workspace_id=str(workspace_id),
                    ),
                ),
            ],
        )


def test_rag_service_ignores_heading_only_top_hit(db_session, seeded_workspace):
    service = RagService(
        retrieval_service=HeadingOnlyTopHitRetrievalService(),
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
    assert "1.3 characteristics of a company" not in answer_lower
