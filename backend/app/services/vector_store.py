from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings

settings = get_settings()


@dataclass
class VectorPoint:
    id: str
    vector: list[float]
    payload: dict[str, Any]


class QdrantVectorStore:
    def __init__(
        self,
        base_url: str | None = None,
        collection_name: str | None = None,
        distance_metric: str | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.qdrant_url).strip().rstrip("/")
        self.api_key = settings.qdrant_api_key.strip()
        self.collection_name = collection_name or settings.qdrant_collection_name
        self.distance_metric = distance_metric or settings.qdrant_distance_metric
        self.max_retries = max_retries or settings.openai_max_retries

    def ensure_collection(self, vector_size: int) -> None:
        response = self._request("GET", f"/collections/{self.collection_name}", expected_status=(200, 404))
        if response.get("status") == "ok":
            return
        self._request(
            "PUT",
            f"/collections/{self.collection_name}",
            {
                "vectors": {
                    "size": vector_size,
                    "distance": self.distance_metric,
                }
            },
            expected_status=(200,),
        )
        for field_name in ("workspace_id", "document_id", "source"):
            self._request(
                "PUT",
                f"/collections/{self.collection_name}/index",
                {"field_name": field_name, "field_schema": "keyword"},
                expected_status=(200, 409),
            )

    def upsert_points(self, points: list[VectorPoint]) -> None:
        if not points:
            return
        payload = {
            "points": [
                {"id": point.id, "vector": point.vector, "payload": point.payload}
                for point in points
            ]
        }
        self._request(
            "PUT",
            f"/collections/{self.collection_name}/points?wait=true",
            payload,
            expected_status=(200,),
        )

    def delete_points(self, point_ids: list[str]) -> None:
        if not point_ids:
            return
        self._request(
            "POST",
            f"/collections/{self.collection_name}/points/delete?wait=true",
            {"points": point_ids},
            expected_status=(200,),
        )

    def delete_document_points(self, workspace_id: str, document_id: str) -> None:
        self._request(
            "POST",
            f"/collections/{self.collection_name}/points/delete?wait=true",
            {
                "filter": {
                    "must": [
                        {"key": "workspace_id", "match": {"value": workspace_id}},
                        {"key": "document_id", "match": {"value": document_id}},
                    ]
                }
            },
            expected_status=(200,),
        )

    def search_points(self, query_vector: list[float], qdrant_filter: dict, limit: int) -> list[dict[str, Any]]:
        response = self._request(
            "POST",
            f"/collections/{self.collection_name}/points/search",
            {
                "vector": query_vector,
                "filter": qdrant_filter,
                "limit": limit,
                "with_payload": True,
                "with_vector": False,
            },
            expected_status=(200,),
        )
        return response.get("result", [])

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        expected_status: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        url = urllib.parse.urljoin(f"{self.base_url}/", path.lstrip("/"))
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        if self.api_key:
            headers["api-key"] = self.api_key

        for attempt in range(self.max_retries):
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.status not in expected_status:
                        raise RuntimeError(f"Unexpected Qdrant response: {response.status}")
                    raw_body = response.read().decode("utf-8")
                    return json.loads(raw_body) if raw_body else {"status": "ok"}
            except urllib.error.HTTPError as exc:
                if exc.code in expected_status:
                    raw_body = exc.read().decode("utf-8", errors="ignore")
                    return json.loads(raw_body) if raw_body else {"status": "ok"}
                should_retry = exc.code in {408, 409, 429, 500, 502, 503, 504}
                if not should_retry or attempt == self.max_retries - 1:
                    detail = exc.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Qdrant request failed with HTTP {exc.code}: {detail}") from exc
                time.sleep(2 ** attempt)
            except urllib.error.URLError as exc:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Qdrant request failed: {exc.reason}") from exc
                time.sleep(2 ** attempt)
        raise RuntimeError("Qdrant request exhausted all retries.")
