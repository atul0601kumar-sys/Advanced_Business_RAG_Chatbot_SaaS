from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from app.core.config import get_settings
from app.services.retrieval_types import SearchHit

settings = get_settings()
logger = logging.getLogger(__name__)


class OpenAIReranker:
    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        max_retries: int | None = None,
        endpoint: str = "https://api.openai.com/v1/chat/completions",
    ) -> None:
        self.api_key = api_key
        self.model = model or settings.openai_reranker_model
        self.max_retries = max_retries or settings.openai_max_retries
        self.endpoint = endpoint

    def rerank(self, query: str, hits: list[SearchHit]) -> list[float]:
        if not hits:
            return []
        if not self.api_key or self.api_key == "your_openai_api_key":
            logger.warning("OpenAI API key missing for reranker, falling back to hybrid scores")
            return [hit.hybrid_score for hit in hits]

        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a retrieval reranker. Score each chunk for relevance to the user query from 0 to 1. "
                        "Return JSON like {\"scores\": [{\"chunk_id\": \"...\", \"score\": 0.87}, ...]}."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "chunks": [
                                {"chunk_id": hit.chunk_id, "text": hit.text[:2000], "metadata": hit.metadata}
                                for hit in hits
                            ],
                        }
                    ),
                },
            ],
        }
        request_body = json.dumps(payload).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        for attempt in range(self.max_retries):
            request = urllib.request.Request(self.endpoint, data=request_body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    response_json = json.loads(response.read().decode("utf-8"))
                    content = response_json["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    score_map = {
                        item["chunk_id"]: float(item["score"])
                        for item in parsed.get("scores", [])
                    }
                    return [score_map.get(hit.chunk_id, hit.hybrid_score) for hit in hits]
            except (urllib.error.HTTPError, urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
                if attempt == self.max_retries - 1:
                    logger.warning("Reranker failed; falling back to hybrid scores", exc_info=exc)
                    return [hit.hybrid_score for hit in hits]
                time.sleep(2 ** attempt)
        return [hit.hybrid_score for hit in hits]

