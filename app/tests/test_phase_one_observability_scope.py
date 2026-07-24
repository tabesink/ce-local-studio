from __future__ import annotations

from typing import Any

import context_engine.services.audit as audit_module
from context_engine.db import Base
from context_engine.models import (
    AUDIT_EVENT_NAMES,
    AUDIT_EVENT_SOURCE_UPLOADED,
    AUDIT_OUTCOME_SUCCEEDED,
    AuditEvent,
)
from context_engine.services.audit import (
    ALLOWED_AUDIT_METADATA_KEYS,
    AuditContext,
    AuditService,
    commit_protected_mutation,
)


DEFERRED_OBSERVABILITY_EVENTS = {
    "audit_events.read",
    "diagnostics.read",
}
DEFERRED_OBSERVABILITY_METADATA_KEYS = {
    "diagnosticKind",
    "lineCount",
    "truncated",
    "limit",
    "elapsedMs",
}
DEFERRED_AUDIT_READ_SYMBOLS = {
    "AuditEventPage",
    "AuditValidationError",
    "safe_audit_event",
    "_encode_cursor",
    "_decode_cursor",
}


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flush_count = 0
        self.rollback_count = 0

    def add(self, value: Any) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flush_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


def test_phase_one_excludes_deferred_observability_read_service() -> None:
    audit_table = Base.metadata.tables["audit_events"]
    constraint_sql = " ".join(
        str(constraint.sqltext)
        for constraint in audit_table.constraints
        if hasattr(constraint, "sqltext")
    )

    assert DEFERRED_OBSERVABILITY_EVENTS.isdisjoint(AUDIT_EVENT_NAMES)
    assert not any(event in constraint_sql for event in DEFERRED_OBSERVABILITY_EVENTS)
    assert DEFERRED_OBSERVABILITY_METADATA_KEYS.isdisjoint(ALLOWED_AUDIT_METADATA_KEYS)
    assert not hasattr(AuditService, "list_events")
    assert callable(commit_protected_mutation)
    assert not any(hasattr(audit_module, symbol) for symbol in DEFERRED_AUDIT_READ_SYMBOLS)


def test_phase_one_preserves_private_transactional_audit_writes() -> None:
    session = RecordingSession()

    event = AuditService(session).record(
        AUDIT_EVENT_SOURCE_UPLOADED,
        context=AuditContext(actor_kind="worker", request_id="req-1"),
        target_kind="source_document",
        target_id="source-1",
        metadata={"operationType": "prepare"},
    )

    assert isinstance(event, AuditEvent)
    assert event.event_name == AUDIT_EVENT_SOURCE_UPLOADED
    assert event.outcome == AUDIT_OUTCOME_SUCCEEDED
    assert event.request_id == "req-1"
    assert event.metadata_json == '{"operationType":"prepare"}'
    assert session.added == [event]
    assert session.flush_count == 1
    assert session.rollback_count == 0
