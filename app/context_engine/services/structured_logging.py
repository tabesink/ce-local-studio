from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

SAFE_LOG_FIELDS = {
    "event",
    "request_id",
    "trace_id",
    "actor_kind",
    "domain_id",
    "source_id",
    "conversation_turn_id",
    "operation_id",
    "client_request_id",
    "index_request_id",
    "safe_error_code",
    "elapsed_ms",
    "http_method",
    "http_route",
    "http_status",
    "outcome",
    "replay",
}


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        for field in sorted(SAFE_LOG_FIELDS - {"event"}):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)


def configure_json_logging() -> None:
    root = logging.getLogger()
    if any(getattr(handler, "_context_engine_json", False) for handler in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    handler._context_engine_json = True  # type: ignore[attr-defined]
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def safe_log(logger: logging.Logger, event: str, **fields: Any) -> None:
    extra = {"event": event}
    for key, value in fields.items():
        if key in SAFE_LOG_FIELDS and value is not None:
            extra[key] = value
    logger.info(event, extra=extra)
