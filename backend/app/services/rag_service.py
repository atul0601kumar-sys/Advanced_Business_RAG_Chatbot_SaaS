from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import AsyncIterator

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ChatMessage
from app.schemas.chat import ChatAnswerResponse, ChatMode
from app.schemas.retrieval import RetrievalFiltersRequest, RetrievalResultItem
from app.services.memory_manager import MemorySnapshot
from app.services.faq_service import FAQService
from app.services.prompt_manager import PromptManager
from app.services.prompt_builder import FALLBACK_ANSWER, PromptBuilder, PromptPayload
from app.services.response_formatter import ResponseFormatter
from app.services.retrieval_service import RetrievalService
from app.services.settings_service import SettingsService

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class PreparedRagRequest:
    query: str
    prompt: PromptPayload
    results: list[RetrievalResultItem]
    fallback_only: bool = False
    faq_response: ChatAnswerResponse | None = None


@dataclass
class RagStreamEvent:
    event_type: str
    token: str = ""
    result: ChatAnswerResponse | None = None


class OpenAIChatClient:
    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        max_retries: int | None = None,
        endpoint: str = "https://api.openai.com/v1/chat/completions",
    ) -> None:
        self.api_key = api_key
        self.model = model or settings.openai_chat_model
        self.max_retries = max_retries or settings.openai_max_retries
        self.endpoint = endpoint

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = self._build_payload(messages, stream=False)
        response_body = self._request(payload, stream=False)
        return response_body["choices"][0]["message"]["content"]

    def stream(self, messages: list[dict[str, str]], stop_event: threading.Event | None = None):
        payload = self._build_payload(messages, stream=True)
        if not self.api_key or self.api_key == "your_openai_api_key":
            raise RuntimeError("OpenAI API key is not configured for chat generation.")
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            for raw_line in response:
                if stop_event and stop_event.is_set():
                    break
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data: "):
                    continue
                data = line.removeprefix("data: ").strip()
                if data == "[DONE]":
                    break
                payload = json.loads(data)
                delta = payload["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta

    def _build_payload(self, messages: list[dict[str, str]], *, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "stream": stream,
        }

    def _request(self, payload: dict, *, stream: bool) -> dict:
        if not self.api_key or self.api_key == "your_openai_api_key":
            raise RuntimeError("OpenAI API key is not configured for chat generation.")
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        for attempt in range(self.max_retries):
            request = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                should_retry = exc.code in {408, 409, 429, 500, 502, 503, 504}
                if not should_retry or attempt == self.max_retries - 1:
                    detail = exc.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Chat generation failed with HTTP {exc.code}: {detail}") from exc
                time.sleep(2 ** attempt)
            except urllib.error.URLError as exc:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Chat generation failed: {exc.reason}") from exc
                time.sleep(2 ** attempt)
        raise RuntimeError("Chat generation exhausted all retries.")


class RagService:
    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        prompt_builder: PromptBuilder | None = None,
        response_formatter: ResponseFormatter | None = None,
        chat_client: OpenAIChatClient | None = None,
        prompt_manager: PromptManager | None = None,
        settings_service: SettingsService | None = None,
        faq_service: FAQService | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service or RetrievalService()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.response_formatter = response_formatter or ResponseFormatter()
        self.chat_client = chat_client or OpenAIChatClient(api_key=settings.openai_api_key)
        self.prompt_manager = prompt_manager or PromptManager()
        self.settings_service = settings_service or SettingsService()
        self.faq_service = faq_service or FAQService()

    async def prepare(
        self,
        db: Session,
        workspace_id,
        query: str,
        mode: ChatMode,
        filters: RetrievalFiltersRequest | None,
        memory: MemorySnapshot,
        prior_messages: list[ChatMessage],
    ) -> PreparedRagRequest:
        faq_match = self.faq_service.find_best_match(db, workspace_id, query)
        if faq_match is not None:
            return PreparedRagRequest(
                query=query,
                prompt=PromptPayload(messages=[], context_text=""),
                results=[],
                fallback_only=False,
                faq_response=self.faq_service.build_chat_response(faq_match, processing_time_ms=0),
            )
        retrieval_response = await self.retrieval_service.retrieve(db, workspace_id, query, filters)
        results = retrieval_response.results[: settings.retrieval_final_top_k]
        if not results:
            logger.info("No retrieval hits found for chat answer", extra={"workspace_id": str(workspace_id), "query": query})
            return PreparedRagRequest(
                query=query,
                prompt=PromptPayload(messages=[], context_text=""),
                results=[],
                fallback_only=True,
            )

        chatbot_setting = self.settings_service.get_setting_for_runtime(db, workspace_id)
        prompt = self.prompt_builder.build(
            query=query,
            mode=mode,
            retrieved_chunks=results,
            conversation_summary=memory.summary,
            recent_messages=prior_messages,
            system_prompt=self.prompt_manager.build_system_prompt(chatbot_setting, mode),
        )
        return PreparedRagRequest(
            query=query,
            prompt=prompt,
            results=results,
            fallback_only=False,
        )

    async def generate_answer(
        self,
        db: Session,
        workspace_id,
        query: str,
        mode: ChatMode,
        filters: RetrievalFiltersRequest | None,
        memory: MemorySnapshot,
        prior_messages: list[ChatMessage],
    ) -> ChatAnswerResponse:
        started = time.perf_counter()
        prepared = await self.prepare(db, workspace_id, query, mode, filters, memory, prior_messages)
        if prepared.faq_response is not None:
            return prepared.faq_response.model_copy(
                update={
                    "metadata": prepared.faq_response.metadata.model_copy(
                        update={"processing_time": int((time.perf_counter() - started) * 1000)}
                    )
                }
            )
        if prepared.fallback_only:
            return self.response_formatter.build_response(
                FALLBACK_ANSWER,
                [],
                processing_time_ms=int((time.perf_counter() - started) * 1000),
            )
        try:
            answer = await asyncio.to_thread(self.chat_client.complete, prepared.prompt.messages)
        except Exception:  # noqa: BLE001
            logger.exception("LLM completion failed for chat answer", extra={"workspace_id": str(workspace_id)})
            answer = FALLBACK_ANSWER
        return self.response_formatter.build_response(
            answer,
            prepared.results,
            processing_time_ms=int((time.perf_counter() - started) * 1000),
        )

    async def stream_answer(
        self,
        db: Session,
        workspace_id,
        query: str,
        mode: ChatMode,
        filters: RetrievalFiltersRequest | None,
        memory: MemorySnapshot,
        prior_messages: list[ChatMessage],
        stop_event: threading.Event,
    ) -> AsyncIterator[RagStreamEvent]:
        started = time.perf_counter()
        prepared = await self.prepare(db, workspace_id, query, mode, filters, memory, prior_messages)
        if prepared.faq_response is not None:
            partial = ""
            for piece in self._split_for_streaming(prepared.faq_response.answer):
                if stop_event.is_set():
                    break
                partial += piece
                yield RagStreamEvent(event_type="token", token=piece)
                await asyncio.sleep(0)
            yield RagStreamEvent(
                event_type="final",
                result=prepared.faq_response.model_copy(
                    update={
                        "answer": partial or prepared.faq_response.answer,
                        "metadata": prepared.faq_response.metadata.model_copy(
                            update={
                                "processing_time": int((time.perf_counter() - started) * 1000),
                                "stopped": stop_event.is_set(),
                            }
                        ),
                    }
                ),
            )
            return
        if prepared.fallback_only:
            partial = ""
            for piece in self._split_for_streaming(FALLBACK_ANSWER):
                if stop_event.is_set():
                    break
                partial += piece
                yield RagStreamEvent(event_type="token", token=piece)
                await asyncio.sleep(0)
            yield RagStreamEvent(
                event_type="final",
                result=self.response_formatter.build_response(
                    partial or FALLBACK_ANSWER,
                    [],
                    processing_time_ms=int((time.perf_counter() - started) * 1000),
                    stopped=stop_event.is_set(),
                ),
            )
            return

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()

        def worker() -> None:
            try:
                for token in self.chat_client.stream(prepared.prompt.messages, stop_event=stop_event):
                    loop.call_soon_threadsafe(queue.put_nowait, ("token", token))
                    if stop_event.is_set():
                        break
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
            except Exception as exc:  # noqa: BLE001
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

        tokens: list[str] = []
        while True:
            event_type, payload = await queue.get()
            if event_type == "token" and payload is not None:
                tokens.append(payload)
                yield RagStreamEvent(event_type="token", token=payload)
                continue
            if event_type == "error":
                logger.error(
                    "Streaming LLM generation failed",
                    extra={"workspace_id": str(workspace_id), "query": query, "error": payload},
                )
                break
            if event_type == "done":
                break

        answer = "".join(tokens).strip() or FALLBACK_ANSWER
        yield RagStreamEvent(
            event_type="final",
            result=self.response_formatter.build_response(
                answer,
                prepared.results,
                processing_time_ms=int((time.perf_counter() - started) * 1000),
                stopped=stop_event.is_set(),
            ),
        )

    def summarize_messages(self, existing_summary: str | None, messages: list[ChatMessage]) -> str:
        if not messages:
            return existing_summary or ""
        condensed = []
        if existing_summary:
            condensed.append(existing_summary.strip())
        for message in messages[-8:]:
            prefix = "User" if message.role == "user" else "Assistant"
            condensed.append(f"{prefix}: {' '.join(message.content.strip().split())[:220]}")
        return "\n".join(condensed[-8:])

    def _split_for_streaming(self, answer: str) -> list[str]:
        words = answer.split(" ")
        pieces: list[str] = []
        for index, word in enumerate(words):
            suffix = " " if index < len(words) - 1 else ""
            pieces.append(f"{word}{suffix}")
        return pieces or [answer]
