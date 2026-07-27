from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from context_engine.services.structured_logging import safe_log

import logging

logger = logging.getLogger(__name__)

METRIC_NAMES = frozenset(
    {
        "http_request",
        "chat_turn_terminal",
        "worker_operation",
    }
)

METRIC_LABEL_KEYS = frozenset(
    {
        "http_method",
        "http_route",
        "outcome",
        "actor_kind",
        "status_class",
        "safe_error_code",
        "chat_route_kind",
        "operation_type",
    }
)

_FORBIDDEN_LABEL_KEYS = frozenset(
    {
        "domain_id",
        "source_id",
        "conversation_turn_id",
        "operation_id",
        "request_id",
        "trace_id",
        "client_request_id",
        "index_request_id",
        "user_id",
        "actor_user_id",
    }
)

_HTTP_METHODS = frozenset({"GET", "POST", "PATCH", "PUT", "DELETE", "HEAD", "OPTIONS"})
_OUTCOMES = frozenset({"succeeded", "failed", "denied", "running"})
_ACTOR_KINDS = frozenset({"public", "member", "administrator", "worker"})
_STATUS_CLASSES = frozenset({"2xx", "3xx", "4xx", "5xx"})
_CHAT_ROUTE_KINDS = frozenset({"direct_llm", "domain_rag", "unknown"})
_OPERATION_TYPES = frozenset(
    {
        "source_preparation",
        "source_index",
        "source_delete",
        "domain_delete",
        "stack_worker",
    }
)

_ROUTE_TEMPLATE_RE = re.compile(r"^/(?:[A-Za-z0-9_./{}|-]+)$")
_SAFE_ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_OPAQUE_REF_RE = re.compile(
    r"\b(?:conv_|turn_|dom_|src_|op_|doc_|ev_|tpl_)[A-Za-z0-9_-]{8,}\b"
)


@dataclass(frozen=True)
class MetricSample:
    name: str
    labels: dict[str, str]
    value: int


class _Registry:
    def __init__(self) -> None:
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)

    def increment(self, name: str, labels: dict[str, str], amount: int = 1) -> None:
        key = (name, tuple(sorted(labels.items())))
        self._counters[key] += amount

    def snapshot(self) -> list[MetricSample]:
        samples = [
            MetricSample(name=name, labels=dict(label_items), value=value)
            for (name, label_items), value in self._counters.items()
        ]
        samples.sort(key=lambda sample: (sample.name, tuple(sorted(sample.labels.items()))))
        return samples

    def reset(self) -> None:
        self._counters.clear()


_REGISTRY = _Registry()


def reset_metrics() -> None:
    _REGISTRY.reset()


def snapshot_metrics() -> list[MetricSample]:
    return _REGISTRY.snapshot()


def status_class_for(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return "4xx"
    if 500 <= status_code < 600:
        return "5xx"
    return "5xx"


def _normalize_http_method(value: str) -> str | None:
    method = value.upper()
    if method in _HTTP_METHODS:
        return method
    return "OTHER"


def _label_value_allowed(key: str, value: str) -> bool:
    if not value or len(value) > 128:
        return False
    if _UUID_RE.search(value) or _OPAQUE_REF_RE.search(value):
        return False
    if key == "http_method":
        return value in _HTTP_METHODS or value == "OTHER"
    if key == "http_route":
        return value == "unmatched" or bool(_ROUTE_TEMPLATE_RE.fullmatch(value))
    if key == "outcome":
        return value in _OUTCOMES
    if key == "actor_kind":
        return value in _ACTOR_KINDS
    if key == "status_class":
        return value in _STATUS_CLASSES
    if key == "safe_error_code":
        return bool(_SAFE_ERROR_CODE_RE.fullmatch(value))
    if key == "chat_route_kind":
        return value in _CHAT_ROUTE_KINDS
    if key == "operation_type":
        return value in _OPERATION_TYPES
    return False


def _sanitize_labels(raw: dict[str, Any]) -> dict[str, str] | None:
    labels: dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if key in _FORBIDDEN_LABEL_KEYS or key not in METRIC_LABEL_KEYS:
            return None
        text = str(value)
        if key == "http_method":
            normalized = _normalize_http_method(text)
            if normalized is None:
                return None
            text = normalized
        if not _label_value_allowed(key, text):
            return None
        labels[key] = text
    return labels


def safe_increment(name: str, *, amount: int = 1, **labels: Any) -> None:
    try:
        if name not in METRIC_NAMES or amount < 1:
            return
        sanitized = _sanitize_labels(labels)
        if sanitized is None:
            return
        _REGISTRY.increment(name, sanitized, amount=amount)
    except Exception:
        try:
            safe_log(logger, "metrics.outage", safe_error_code="metrics_unavailable")
        except Exception:
            pass
