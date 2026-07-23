from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from context_engine.config import Settings
from context_engine.services.structured_logging import safe_log

logger = logging.getLogger(__name__)

ALLOWED_TRACE_METADATA_KEYS = {
    "trace_id",
    "request_id",
    "conversation_turn_id",
    "domain_id",
    "route",
    "stop_reason",
    "plan_step_count",
    "retrieval_operation_count",
    "repair_attempt_count",
    "mapped_evidence_count",
    "discarded_hit_count",
    "citation_count",
    "elapsed_ms",
    "provider_kind",
    "synthesis_profile_id",
}


@dataclass(frozen=True)
class TraceMetadata:
    values: dict[str, Any]

    def safe_values(self) -> dict[str, Any]:
        return {key: value for key, value in self.values.items() if key in ALLOWED_TRACE_METADATA_KEYS and value is not None}


class TracingPort:
    def record_turn(self, metadata: TraceMetadata) -> None:
        return None


class DisabledTracingPort(TracingPort):
    pass


class SafeTracingWrapper(TracingPort):
    def __init__(self, inner: TracingPort) -> None:
        self._inner = inner

    def record_turn(self, metadata: TraceMetadata) -> None:
        try:
            self._inner.record_turn(metadata)
        except Exception:
            safe_log(logger, "tracing.outage", trace_id=metadata.safe_values().get("trace_id"), safe_error_code="tracing_unavailable")


def tracer_from_settings(_settings: Settings) -> TracingPort:
    return SafeTracingWrapper(DisabledTracingPort())
