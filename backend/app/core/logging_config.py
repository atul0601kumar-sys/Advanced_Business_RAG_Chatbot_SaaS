from __future__ import annotations

import json
import logging
from logging.config import dictConfig

from app.core.config import Settings
from app.core.request_context import get_request_id


class RequestContextFilter(logging.Filter):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.service = "backend"
        record.app_version = self.settings.app_version
        record.environment = self.settings.app_env
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "service": getattr(record, "service", "backend"),
            "app_version": getattr(record, "app_version", "-"),
            "environment": getattr(record, "environment", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(settings: Settings) -> None:
    level = settings.log_level.upper()
    formatter_class = "app.core.logging_config.JsonFormatter" if settings.log_format == "json" else "logging.Formatter"
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "()": formatter_class,
                    "format": "%(asctime)s %(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s",
                }
            },
            "filters": {
                "request_context": {
                    "()": "app.core.logging_config.RequestContextFilter",
                    "settings": settings,
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "filters": ["request_context"],
                }
            },
            "root": {"level": level, "handlers": ["default"]},
            "loggers": {
                "uvicorn": {"level": level, "handlers": ["default"], "propagate": False},
                "uvicorn.error": {"level": level, "handlers": ["default"], "propagate": False},
                "uvicorn.access": {"level": level, "handlers": ["default"], "propagate": False},
            },
        }
    )
    logging.getLogger(__name__).debug("Logging configured", extra={"level": level})
