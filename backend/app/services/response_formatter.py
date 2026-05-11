from __future__ import annotations

from app.schemas.chat import ChatAnswerResponse, ChatResponseMetadata, CitationItem, ConfidenceLevel
from app.schemas.lead import LeadCapturePrompt
from app.schemas.retrieval import RetrievalResultItem
from app.services.prompt_builder import FALLBACK_ANSWER


class ResponseFormatter:
    def build_citations(self, results: list[RetrievalResultItem]) -> list[CitationItem]:
        seen_keys: set[tuple[str | None, int | None, str | None]] = set()
        citations: list[CitationItem] = []
        for result in results:
            key = (
                result.metadata.file_name,
                result.metadata.page_number,
                result.metadata.url,
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            citations.append(
                CitationItem(
                    document_id=result.metadata.document_id,
                    file_name=result.metadata.file_name,
                    page_number=result.metadata.page_number,
                    url=result.metadata.url,
                    chunk_preview=result.text[:220].strip(),
                )
            )
        return citations

    def build_confidence(self, results: list[RetrievalResultItem]) -> ConfidenceLevel:
        if not results:
            return "Low"
        avg_vector = sum(item.vector_score for item in results) / len(results)
        avg_rerank = sum(item.rerank_score for item in results) / len(results)
        support_count = len({(item.metadata.file_name, item.metadata.page_number, item.chunk_id) for item in results})
        if avg_vector >= 0.75 and avg_rerank >= 0.75 and support_count >= 2:
            return "High"
        if avg_vector >= 0.5 and avg_rerank >= 0.45:
            return "Medium"
        return "Low"

    def normalize_answer(self, answer: str) -> str:
        cleaned = answer.strip()
        return cleaned or FALLBACK_ANSWER

    def build_response(
        self,
        answer: str,
        results: list[RetrievalResultItem],
        processing_time_ms: int,
        *,
        stopped: bool = False,
        session_id=None,
        message_id=None,
        generation_id: str | None = None,
        lead_capture: LeadCapturePrompt | None = None,
        answer_strategy: str = "rag",
        faq_id=None,
    ) -> ChatAnswerResponse:
        citations = self.build_citations(results)
        confidence = self.build_confidence(results)
        return ChatAnswerResponse(
            answer=self.normalize_answer(answer),
            citations=citations,
            confidence=confidence,
            metadata=ChatResponseMetadata(
                retrieved_chunks=len(results),
                processing_time=processing_time_ms,
                stopped=stopped,
                session_id=session_id,
                message_id=message_id,
                generation_id=generation_id,
                lead_capture=lead_capture,
                answer_strategy=answer_strategy,
                faq_id=faq_id,
            ),
        )
