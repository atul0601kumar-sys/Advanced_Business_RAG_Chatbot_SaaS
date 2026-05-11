from __future__ import annotations

import io
import json
import urllib.error

import pytest

from app.services.embedder import OpenAIEmbedder
from app.services.reranker import OpenAIReranker
from app.services.retrieval_types import SearchHit


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_embedder_batches_and_orders_embeddings(monkeypatch):
    calls: list[list[str]] = []

    def fake_urlopen(request, timeout=60):  # noqa: ARG001
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload["input"])
        return FakeResponse(
            {
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    embedder = OpenAIEmbedder(api_key="test-key", batch_size=2, max_retries=1)
    vectors = embedder.embed_texts(["alpha", "beta"])
    assert calls == [["alpha", "beta"]]
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]


def test_embedder_raises_clear_error_after_http_failure(monkeypatch):
    def fake_urlopen(request, timeout=60):  # noqa: ARG001
        raise urllib.error.HTTPError(
            url="https://api.openai.com/v1/embeddings",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"rate limited"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    embedder = OpenAIEmbedder(api_key="test-key", max_retries=1)
    with pytest.raises(RuntimeError, match="HTTP 429"):
        embedder.embed_texts(["alpha"])


def test_reranker_improves_result_order(monkeypatch):
    hits = [
        SearchHit(chunk_id="low", text="general note", hybrid_score=0.6, metadata={}),
        SearchHit(chunk_id="high", text="revenue grew 18 percent", hybrid_score=0.4, metadata={}),
    ]

    def fake_urlopen(request, timeout=60):  # noqa: ARG001
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"scores": [{"chunk_id": "high", "score": 0.95}, {"chunk_id": "low", "score": 0.2}]}
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    reranker = OpenAIReranker(api_key="test-key", max_retries=1)
    assert reranker.rerank("revenue", hits) == [0.2, 0.95]


def test_reranker_falls_back_to_hybrid_scores_when_network_fails(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")))
    hits = [SearchHit(chunk_id="one", text="doc", hybrid_score=0.72, metadata={})]
    reranker = OpenAIReranker(api_key="test-key", max_retries=1)
    assert reranker.rerank("query", hits) == [0.72]
