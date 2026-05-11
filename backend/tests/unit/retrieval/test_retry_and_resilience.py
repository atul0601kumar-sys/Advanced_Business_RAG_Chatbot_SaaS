from __future__ import annotations

import json
import urllib.error

import pytest

from app.services.embedder import OpenAIEmbedder
from app.services.vector_store import QdrantVectorStore


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload
        self.status = 200

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_embedder_retries_after_transient_timeout(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout=60):  # noqa: ARG001
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise urllib.error.URLError("timed out")
        return FakeResponse({"data": [{"index": 0, "embedding": [1.0, 2.0]}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.embedder.time.sleep", lambda seconds: None)

    embedder = OpenAIEmbedder(api_key="test-key", max_retries=2)
    assert embedder.embed_texts(["revenue"]) == [[1.0, 2.0]]
    assert attempts["count"] == 2


def test_qdrant_store_retries_after_transient_network_failure(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(request, timeout=30):  # noqa: ARG001
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise urllib.error.URLError("connection reset")
        return FakeResponse({"status": "ok", "result": []})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.vector_store.time.sleep", lambda seconds: None)

    store = QdrantVectorStore(base_url="http://qdrant.test", max_retries=2)
    assert store.search_points([1.0, 2.0], {"must": []}, 5) == []
    assert attempts["count"] == 2


def test_qdrant_store_sends_api_key_header_when_configured(monkeypatch):
    captured_headers = {}

    def fake_urlopen(request, timeout=30):  # noqa: ARG001
        captured_headers.update(dict(request.header_items()))
        return FakeResponse({"status": "ok", "result": []})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    store = QdrantVectorStore(base_url="http://qdrant.test", max_retries=1)
    store.api_key = "test-qdrant-key"

    assert store.search_points([1.0, 2.0], {"must": []}, 5) == []
    assert captured_headers["Api-key"] == "test-qdrant-key"


def test_qdrant_store_surfaces_clear_error_after_retries(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30: (_ for _ in ()).throw(urllib.error.URLError("offline")),  # noqa: ARG005
    )
    monkeypatch.setattr("app.services.vector_store.time.sleep", lambda seconds: None)
    store = QdrantVectorStore(base_url="http://qdrant.test", max_retries=2)
    with pytest.raises(RuntimeError, match="Qdrant request failed"):
        store.ensure_collection(2)
