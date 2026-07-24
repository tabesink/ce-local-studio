from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import SQLAlchemyError

from context_engine.models import (
    AUDIT_EVENT_USER_DISABLED,
    AUDIT_OUTCOME_SUCCEEDED,
    AuditEvent,
)
from context_engine.services.audit import (
    AuditContext,
    AuditError,
    AuditService,
    commit_protected_mutation,
)


class FlushError(SQLAlchemyError):
    pass


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.fail_flush = False

    def add(self, value: Any) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flush_count += 1
        if self.fail_flush:
            raise FlushError("flush failed")

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


def test_record_rejects_unknown_event_and_rolls_back() -> None:
    session = RecordingSession()

    with pytest.raises(AuditError) as exc_info:
        AuditService(session).record("not.an.allowed.event", context=AuditContext(actor_kind="system"))

    assert exc_info.value.code == "audit_unavailable"
    assert exc_info.value.status_code == 503
    assert session.added == []
    assert session.rollback_count == 1
    assert session.commit_count == 0


def test_record_rejects_unknown_metadata_key_and_rolls_back() -> None:
    session = RecordingSession()

    with pytest.raises(AuditError):
        AuditService(session).record(
            AUDIT_EVENT_USER_DISABLED,
            context=AuditContext(actor_kind="administrator"),
            metadata={"prompt": "secret question"},
        )

    assert session.added == []
    assert session.rollback_count == 1


def test_commit_protected_mutation_commits_mutation_and_audit_together() -> None:
    session = RecordingSession()
    state = {"disabled": False}

    result = commit_protected_mutation(
        session,
        lambda: state.__setitem__("disabled", True) or state,
        event_name=AUDIT_EVENT_USER_DISABLED,
        context=AuditContext(actor_kind="administrator", request_id="req-audit-1"),
        target_kind="user",
        target_id="user-1",
    )

    assert result["disabled"] is True
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert session.flush_count == 1
    assert len(session.added) == 1
    event = session.added[0]
    assert isinstance(event, AuditEvent)
    assert event.event_name == AUDIT_EVENT_USER_DISABLED
    assert event.outcome == AUDIT_OUTCOME_SUCCEEDED
    assert event.request_id == "req-audit-1"
    assert event.target_id == "user-1"


def test_commit_protected_mutation_rolls_back_product_change_when_audit_fails() -> None:
    session = RecordingSession()
    session.fail_flush = True
    state = {"disabled": False}

    def mutate() -> dict[str, bool]:
        state["disabled"] = True
        return state

    with pytest.raises(AuditError):
        commit_protected_mutation(
            session,
            mutate,
            event_name=AUDIT_EVENT_USER_DISABLED,
            context=AuditContext(actor_kind="administrator"),
            target_kind="user",
            target_id="user-1",
        )

    assert state["disabled"] is True  # in-memory mutate ran
    assert session.commit_count == 0
    assert session.rollback_count >= 1
