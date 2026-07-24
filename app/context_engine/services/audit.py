from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from context_engine.db import utc_now
from context_engine.models import (
    AUDIT_ACTOR_ADMINISTRATOR,
    AUDIT_ACTOR_KINDS,
    AUDIT_ACTOR_MEMBER,
    AUDIT_ACTOR_SYSTEM,
    AUDIT_EVENT_NAMES,
    AUDIT_OUTCOME_SUCCEEDED,
    AUDIT_OUTCOMES,
    ROLE_ADMINISTRATOR,
    AuditEvent,
    User,
)

MAX_AUDIT_METADATA_BYTES = 4096
MAX_AUDIT_METADATA_STRING_CHARS = 200
ALLOWED_AUDIT_METADATA_KEYS = {
    "operationType",
    "operationStatus",
    "sourceState",
    "indexState",
    "turnStatus",
    "stopReason",
    "redactedTurnCount",
}

T = TypeVar("T")


class AuditError(Exception):
    def __init__(self, message: str = "Audit unavailable.") -> None:
        self.status_code = 503
        self.code = "audit_unavailable"
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class AuditContext:
    request_id: str | None = None
    trace_id: str | None = None
    actor_user: User | None = None
    actor_kind: str | None = None


def actor_kind_for_user(user: User | None) -> str:
    if user is None:
        return AUDIT_ACTOR_SYSTEM
    if user.role == ROLE_ADMINISTRATOR:
        return AUDIT_ACTOR_ADMINISTRATOR
    return AUDIT_ACTOR_MEMBER


def _validate_string(value: str, *, max_length: int) -> str:
    if len(value) > max_length:
        raise AuditError()
    return value


def _validated_metadata(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    safe: dict[str, Any] = {}
    for key, value in metadata.items():
        if key not in ALLOWED_AUDIT_METADATA_KEYS:
            raise AuditError()
        if value is None or isinstance(value, bool):
            safe[key] = value
            continue
        if isinstance(value, int):
            safe[key] = value
            continue
        if isinstance(value, str):
            safe[key] = _validate_string(value, max_length=MAX_AUDIT_METADATA_STRING_CHARS)
            continue
        raise AuditError()
    encoded = json.dumps(safe, separators=(",", ":"), sort_keys=True)
    if len(encoded.encode("utf-8")) > MAX_AUDIT_METADATA_BYTES:
        raise AuditError()
    return encoded


class AuditService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def record(
        self,
        event_name: str,
        *,
        context: AuditContext | None = None,
        actor_user: User | None = None,
        actor_kind: str | None = None,
        target_kind: str | None = None,
        target_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        outcome: str = AUDIT_OUTCOME_SUCCEEDED,
        safe_error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        try:
            context = context or AuditContext()
            resolved_actor_user = actor_user if actor_user is not None else context.actor_user
            resolved_actor_kind = actor_kind or context.actor_kind or actor_kind_for_user(resolved_actor_user)
            resolved_request_id = request_id if request_id is not None else context.request_id
            resolved_trace_id = trace_id if trace_id is not None else context.trace_id
            if (
                event_name not in AUDIT_EVENT_NAMES
                or resolved_actor_kind not in AUDIT_ACTOR_KINDS
                or outcome not in AUDIT_OUTCOMES
            ):
                raise AuditError()
            event = AuditEvent(
                id=str(uuid.uuid4()),
                event_name=event_name,
                actor_kind=resolved_actor_kind,
                actor_user_id=resolved_actor_user.id if resolved_actor_user is not None else None,
                target_kind=_validate_string(target_kind, max_length=40) if target_kind else None,
                target_id=_validate_string(target_id, max_length=128) if target_id else None,
                request_id=_validate_string(resolved_request_id, max_length=80) if resolved_request_id else None,
                trace_id=_validate_string(resolved_trace_id, max_length=80) if resolved_trace_id else None,
                outcome=outcome,
                safe_error_code=_validate_string(safe_error_code, max_length=64) if safe_error_code else None,
                metadata_json=_validated_metadata(metadata),
                created_at=utc_now(),
            )
            self._db.add(event)
            self._db.flush()
            return event
        except AuditError:
            self._db.rollback()
            raise
        except SQLAlchemyError:
            self._db.rollback()
            raise AuditError() from None


def commit_protected_mutation(
    db: Session,
    mutate: Callable[[], T],
    *,
    event_name: str,
    context: AuditContext | None = None,
    actor_user: User | None = None,
    actor_kind: str | None = None,
    target_kind: str | None = None,
    target_id: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    outcome: str = AUDIT_OUTCOME_SUCCEEDED,
    safe_error_code: str | None = None,
    metadata: dict[str, Any] | Callable[[T], dict[str, Any] | None] | None = None,
) -> T:
    """Persist a protected product change and its required audit row together.

    Commits only when both the mutation and audit insert succeed. Any audit
    validation/persistence failure raises ``AuditError`` after rolling back so
    the product change is not durable.
    """
    try:
        result = mutate()
        resolved_metadata = metadata(result) if callable(metadata) else metadata
        AuditService(db).record(
            event_name,
            context=context,
            actor_user=actor_user,
            actor_kind=actor_kind,
            target_kind=target_kind,
            target_id=target_id,
            request_id=request_id,
            trace_id=trace_id,
            outcome=outcome,
            safe_error_code=safe_error_code,
            metadata=resolved_metadata,
        )
        db.commit()
        return result
    except AuditError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@event.listens_for(AuditEvent, "before_update")
def _forbid_audit_event_update(_mapper, _connection, _target) -> None:
    raise AuditError("audit_events is append-only")


@event.listens_for(AuditEvent, "before_delete")
def _forbid_audit_event_delete(_mapper, _connection, _target) -> None:
    raise AuditError("audit_events is append-only")
