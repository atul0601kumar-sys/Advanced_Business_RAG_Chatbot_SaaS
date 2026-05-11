from __future__ import annotations

import json
import uuid

from app.services.streaming_handler import StopGenerationRegistry, StreamingHandler


def test_streaming_handler_preserves_event_payload_order():
    payload = {"message_id": "msg-1", "token": "Revenue"}
    encoded = StreamingHandler().encode("token", payload)
    assert encoded.startswith("event: token")
    assert json.loads(encoded.split("data: ", 1)[1].strip()) == payload


def test_stop_generation_registry_registers_stops_and_releases_handles():
    registry = StopGenerationRegistry()
    session_id = uuid.uuid4()
    handle = registry.register(session_id)

    assert registry.stop(session_id, handle.generation_id) is True
    assert handle.stop_event.is_set() is True

    registry.release(handle)
    assert registry.stop(session_id, handle.generation_id) is False
