from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

settings = get_settings()


class EmbeddingClient(Protocol):
    model: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class OpenAIEmbedder:
    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        batch_size: int | None = None,
        max_retries: int | None = None,
        endpoint: str = "https://api.openai.com/v1/embeddings",
    ) -> None:
        self.api_key = api_key
        self.model = model or settings.openai_embedding_model
        self.batch_size = batch_size or settings.openai_embedding_batch_size
        self.max_retries = max_retries or settings.openai_max_retries
        self.endpoint = endpoint

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            embeddings.extend(self._request_batch(batch))
        return embeddings

    def _request_batch(self, batch: list[str]) -> list[list[float]]:
        if not self.api_key or self.api_key == "your_openai_api_key":
            raise RuntimeError("OpenAI API key is not configured for embeddings.")

        payload = json.dumps({"model": self.model, "input": batch}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.max_retries):
            request = urllib.request.Request(self.endpoint, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    ordered = sorted(body["data"], key=lambda item: item["index"])
                    return [item["embedding"] for item in ordered]
            except urllib.error.HTTPError as exc:
                should_retry = exc.code in {408, 409, 429, 500, 502, 503, 504}
                if not should_retry or attempt == self.max_retries - 1:
                    detail = exc.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Embedding request failed with HTTP {exc.code}: {detail}") from exc
                time.sleep(2 ** attempt)
            except urllib.error.URLError as exc:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Embedding request failed: {exc.reason}") from exc
                time.sleep(2 ** attempt)
        raise RuntimeError("Embedding request exhausted all retries.")


class LocalFastEmbedder:
    def __init__(self, model: str | None = None, cache_dir: str | None = None) -> None:
        self.model = model or settings.local_embedding_model
        self.cache_dir = cache_dir or settings.local_embedding_cache_dir
        self._embedding_model = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = list(model.embed(texts))
        return [vector.tolist() for vector in vectors]

    def _get_model(self):
        if self._embedding_model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:  # pragma: no cover - exercised in runtime environments without dependency
                raise RuntimeError("Local embedding provider is not installed. Add fastembed to the backend runtime.") from exc
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
            self._embedding_model = TextEmbedding(model_name=self.model, cache_dir=self.cache_dir)
        return self._embedding_model


class HashingEmbedder:
    def __init__(self, dimensions: int | None = None) -> None:
        self.dimensions = dimensions or settings.hash_embedding_dimensions
        self.model = f"hash-embedding-{self.dimensions}"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [self._embed_single(text) for text in texts]

    def _embed_single(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = [token for token in text.lower().split() if token]
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] % 2 == 0 else -1.0
            weight = 1.0 + (digest[9] / 255.0)
            vector[bucket] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


def get_default_embedder() -> EmbeddingClient:
    if settings.embedding_provider == "hash":
        return HashingEmbedder()
    if settings.embedding_provider == "local":
        return LocalFastEmbedder()
    return OpenAIEmbedder(api_key=settings.openai_api_key)
