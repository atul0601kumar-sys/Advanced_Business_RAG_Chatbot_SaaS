from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models import ChatMessage
from app.services.chunker import SmartChunker


@dataclass
class MemorySnapshot:
    summary: str | None
    recent_messages: list[ChatMessage]
    updated_summary: str | None


class MemoryManager:
    def __init__(
        self,
        recent_message_limit: int = 8,
        token_limit: int = 1800,
        summary_trigger_message_count: int = 12,
    ) -> None:
        self.recent_message_limit = recent_message_limit
        self.token_limit = token_limit
        self.summary_trigger_message_count = summary_trigger_message_count
        self.token_estimator = SmartChunker().estimate_tokens

    def build_memory(
        self,
        messages: list[ChatMessage],
        existing_summary: str | None,
        summarizer: Callable[[str | None, list[ChatMessage]], str] | None = None,
    ) -> MemorySnapshot:
        if not messages:
            return MemorySnapshot(summary=existing_summary, recent_messages=[], updated_summary=existing_summary)

        recent_messages = self._trim_recent_messages(messages)
        updated_summary = existing_summary

        older_messages = messages[: max(0, len(messages) - len(recent_messages))]
        if older_messages and (
            len(messages) > self.summary_trigger_message_count
            or self._estimate_messages_tokens(messages) > self.token_limit
        ):
            updated_summary = (
                summarizer(existing_summary, older_messages) if summarizer else self._fallback_summary(existing_summary, older_messages)
            )

        return MemorySnapshot(summary=updated_summary, recent_messages=recent_messages, updated_summary=updated_summary)

    def _trim_recent_messages(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        recent = list(messages[-self.recent_message_limit :])
        total_tokens = 0
        selected: list[ChatMessage] = []
        for message in reversed(recent):
            message_tokens = self.token_estimator(message.content)
            if selected and total_tokens + message_tokens > self.token_limit:
                break
            selected.append(message)
            total_tokens += message_tokens
        selected.reverse()
        return selected

    def _estimate_messages_tokens(self, messages: list[ChatMessage]) -> int:
        return sum(self.token_estimator(message.content) for message in messages)

    def _fallback_summary(self, existing_summary: str | None, messages: list[ChatMessage]) -> str:
        snippets: list[str] = []
        if existing_summary:
            snippets.append(existing_summary.strip())
        for message in messages[-6:]:
            prefix = "User" if message.role == "user" else "Assistant"
            condensed = " ".join(message.content.strip().split())[:180]
            if condensed:
                snippets.append(f"{prefix}: {condensed}")
        return "\n".join(snippets[-6:])
