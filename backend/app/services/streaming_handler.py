from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass


@dataclass
class GenerationHandle:
    session_id: uuid.UUID
    generation_id: str
    stop_event: threading.Event


class StopGenerationRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handles: dict[uuid.UUID, dict[str, GenerationHandle]] = {}

    def register(self, session_id: uuid.UUID) -> GenerationHandle:
        handle = GenerationHandle(
            session_id=session_id,
            generation_id=uuid.uuid4().hex,
            stop_event=threading.Event(),
        )
        with self._lock:
            self._handles.setdefault(session_id, {})[handle.generation_id] = handle
        return handle

    def stop(self, session_id: uuid.UUID, generation_id: str | None = None) -> bool:
        with self._lock:
            session_handles = self._handles.get(session_id, {})
            if generation_id:
                handle = session_handles.get(generation_id)
                if not handle:
                    return False
                handle.stop_event.set()
                return True
            if not session_handles:
                return False
            for handle in session_handles.values():
                handle.stop_event.set()
            return True

    def release(self, handle: GenerationHandle) -> None:
        with self._lock:
            session_handles = self._handles.get(handle.session_id, {})
            session_handles.pop(handle.generation_id, None)
            if not session_handles:
                self._handles.pop(handle.session_id, None)


class StreamingHandler:
    def encode(self, event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
