from __future__ import annotations

import json
import logging
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class RedisTaskQueue:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Redis | None = None

    def is_enabled(self) -> bool:
        return self.settings.task_queue_enabled

    def enqueue(self, task_type: str, payload: dict[str, Any]) -> bool:
        if not self.is_enabled():
            return False
        message = json.dumps({"type": task_type, "payload": payload})
        try:
            self._get_client().rpush(self.settings.task_queue_name, message)
            return True
        except RedisError:
            logger.exception("Failed to enqueue task", extra={"task_type": task_type})
            return False

    def dequeue(self, timeout: int | None = None) -> dict[str, Any] | None:
        if not self.is_enabled():
            return None
        wait_seconds = timeout if timeout is not None else self.settings.task_queue_timeout_seconds
        try:
            item = self._get_client().blpop(self.settings.task_queue_name, timeout=wait_seconds)
        except RedisError:
            logger.exception("Failed to dequeue task")
            return None
        if item is None:
            return None
        _, raw = item
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Discarded malformed task payload", extra={"payload": raw.decode("utf-8", errors="ignore")})
            return None

    def ping(self) -> bool:
        if not self.is_enabled():
            return True
        try:
            return bool(self._get_client().ping())
        except RedisError:
            logger.exception("Redis health check failed")
            return False

    def _get_client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(self.settings.redis_url, decode_responses=True)
        return self._client


shared_task_queue = RedisTaskQueue()
