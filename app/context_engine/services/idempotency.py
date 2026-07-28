"""Shared durable HTTP Idempotency-Key claim/complete helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from context_engine.db import utc_now
from context_engine.models import (
    HTTP_IDEMPOTENCY_ROUTE_CLASSES,
    HTTP_IDEMPOTENCY_STATE_COMPLETED,
    HTTP_IDEMPOTENCY_STATE_PENDING,
    HttpIdempotencyRecord,
)


class IdempotencyError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class IdempotencyOutcome:
    record: HttpIdempotencyRecord
    replay: bool
    http_status: int | None = None
    response_kind: str | None = None
    response_refs: dict[str, Any] | None = None


def hash_idempotency_key(raw_key: str) -> str:
    if not raw_key or not raw_key.strip():
        raise IdempotencyError(422, "validation_error", "Request validation failed.")
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def fingerprint_payload(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _lookup(
    db: Session,
    *,
    principal_user_id: str,
    route_class: str,
    key_hash: str,
    for_update: bool,
) -> HttpIdempotencyRecord | None:
    statement = select(HttpIdempotencyRecord).where(
        HttpIdempotencyRecord.principal_user_id == principal_user_id,
        HttpIdempotencyRecord.route_class == route_class,
        HttpIdempotencyRecord.key_hash == key_hash,
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def _resolve_existing(record: HttpIdempotencyRecord, fingerprint: str) -> IdempotencyOutcome:
    if record.fingerprint != fingerprint:
        raise IdempotencyError(
            409,
            "idempotency_conflict",
            "Idempotency-Key was reused with a different request.",
        )
    if record.state == HTTP_IDEMPOTENCY_STATE_PENDING:
        raise IdempotencyError(
            503,
            "capacity_unavailable",
            "A request with this Idempotency-Key is already in progress.",
        )
    refs = json.loads(record.response_refs_json or "{}")
    if not isinstance(refs, dict):
        raise IdempotencyError(500, "internal_error", "An unexpected error occurred.")
    return IdempotencyOutcome(
        record=record,
        replay=True,
        http_status=record.http_status,
        response_kind=record.response_kind,
        response_refs=refs,
    )


def begin_idempotent(
    db: Session,
    *,
    principal_user_id: str,
    route_class: str,
    raw_key: str,
    fingerprint: str,
) -> IdempotencyOutcome:
    if route_class not in HTTP_IDEMPOTENCY_ROUTE_CLASSES:
        raise IdempotencyError(500, "internal_error", "An unexpected error occurred.")
    if len(fingerprint) != 64:
        raise IdempotencyError(500, "internal_error", "An unexpected error occurred.")

    key_hash = hash_idempotency_key(raw_key)
    existing = _lookup(
        db,
        principal_user_id=principal_user_id,
        route_class=route_class,
        key_hash=key_hash,
        for_update=True,
    )
    if existing is not None:
        return _resolve_existing(existing, fingerprint)

    record = HttpIdempotencyRecord(
        principal_user_id=principal_user_id,
        route_class=route_class,
        key_hash=key_hash,
        fingerprint=fingerprint,
        state=HTTP_IDEMPOTENCY_STATE_PENDING,
    )
    try:
        with db.begin_nested():
            db.add(record)
            db.flush()
    except IntegrityError:
        raced = _lookup(
            db,
            principal_user_id=principal_user_id,
            route_class=route_class,
            key_hash=key_hash,
            for_update=True,
        )
        if raced is None:
            raise IdempotencyError(500, "internal_error", "An unexpected error occurred.") from None
        return _resolve_existing(raced, fingerprint)

    return IdempotencyOutcome(record=record, replay=False)


def complete_idempotent(
    db: Session,
    record: HttpIdempotencyRecord,
    *,
    http_status: int,
    response_kind: str,
    response_refs: Mapping[str, Any],
) -> None:
    if record.state != HTTP_IDEMPOTENCY_STATE_PENDING:
        raise IdempotencyError(500, "internal_error", "An unexpected error occurred.")
    if not response_kind or not isinstance(response_refs, Mapping):
        raise IdempotencyError(500, "internal_error", "An unexpected error occurred.")
    payload = json.dumps(dict(response_refs), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    record.state = HTTP_IDEMPOTENCY_STATE_COMPLETED
    record.http_status = int(http_status)
    record.response_kind = response_kind
    record.response_refs_json = payload
    record.completed_at = utc_now()
    db.flush()


def abandon_idempotent(db: Session, record: HttpIdempotencyRecord) -> None:
    if record.state != HTTP_IDEMPOTENCY_STATE_PENDING:
        return
    db.delete(record)
    db.flush()
