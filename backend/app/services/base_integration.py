from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IntegrationContext:
    workspace_id: str
    integration_id: str
    display_name: str
    config: dict[str, Any]
    credentials: dict[str, Any]


@dataclass(frozen=True)
class IntegrationResult:
    status_code: int
    response_body: str


class IntegrationService(ABC):
    integration_type: str = "base"

    @abstractmethod
    def connect(self, context: IntegrationContext) -> IntegrationResult:
        raise NotImplementedError

    @abstractmethod
    def send_event(self, context: IntegrationContext, *, event_type: str, payload: dict[str, Any]) -> IntegrationResult:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self, context: IntegrationContext) -> IntegrationResult:
        raise NotImplementedError

    @abstractmethod
    def validate_config(self, *, config: dict[str, Any], credentials: dict[str, Any]) -> None:
        raise NotImplementedError
