from __future__ import annotations

import json
from urllib.error import URLError

from app.api.v1.routes import health


class FakeResponse:
    def __init__(self, status: int, payload: str = '"healthz check passed"') -> None:
        self.status = status
        self._payload = payload

    def read(self) -> bytes:
        return self._payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_qdrant_ready_uses_readyz_when_available(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout=3):  # noqa: ARG001
        requests.append(request.full_url)
        return FakeResponse(200)

    monkeypatch.setattr("app.api.v1.routes.health.urlopen", fake_urlopen)
    monkeypatch.setattr(health.settings, "qdrant_api_key", "")

    assert health._qdrant_ready() is True
    assert requests == [f"{health.settings.qdrant_url.rstrip('/')}/readyz"]


def test_qdrant_ready_falls_back_to_collections_for_cloud(monkeypatch):
    requests = []
    headers = []

    def fake_urlopen(request, timeout=3):  # noqa: ARG001
        requests.append(request.full_url)
        headers.append(dict(request.header_items()))
        if request.full_url.endswith("/readyz"):
            raise URLError("not exposed")
        return FakeResponse(200, json.dumps({"status": "ok", "result": {"collections": []}}))

    monkeypatch.setattr("app.api.v1.routes.health.urlopen", fake_urlopen)
    monkeypatch.setattr(health.settings, "qdrant_api_key", "cloud-key")

    assert health._qdrant_ready() is True
    assert requests == [
        f"{health.settings.qdrant_url.rstrip('/')}/readyz",
        f"{health.settings.qdrant_url.rstrip('/')}/collections",
    ]
    assert headers[0]["Api-key"] == "cloud-key"
    assert headers[1]["Api-key"] == "cloud-key"
