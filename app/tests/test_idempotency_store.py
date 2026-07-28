from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.db import Base
from context_engine.models import (
    HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
    HTTP_IDEMPOTENCY_STATE_COMPLETED,
    HTTP_IDEMPOTENCY_STATE_PENDING,
    HttpIdempotencyRecord,
    User,
)
from context_engine.services.idempotency import (
    IdempotencyError,
    abandon_idempotent,
    begin_idempotent,
    complete_idempotent,
    fingerprint_payload,
    hash_idempotency_key,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(db: Session) -> User:
    user = User(username="member@example.test", password_hash="synthetic-password-hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_hash_and_fingerprint_are_stable_sha256() -> None:
    assert hash_idempotency_key("retry-1") == hashlib.sha256(b"retry-1").hexdigest()
    assert fingerprint_payload({"title": "A"}) == fingerprint_payload({"title": "A"})
    assert fingerprint_payload({"title": "A"}) != fingerprint_payload({"title": "B"})


def test_replay_returns_prior_result_without_second_side_effect(db: Session) -> None:
    owner = _user(db)
    fingerprint = fingerprint_payload({"title": "Hello"})
    first = begin_idempotent(
        db,
        principal_user_id=owner.id,
        route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
        raw_key="create-key-1",
        fingerprint=fingerprint,
    )
    assert first.replay is False
    side_effects = 0

    def mutate() -> None:
        nonlocal side_effects
        side_effects += 1

    mutate()
    complete_idempotent(
        db,
        first.record,
        http_status=201,
        response_kind="conversation",
        response_refs={"conversationId": "conv_abc"},
    )
    db.commit()

    second = begin_idempotent(
        db,
        principal_user_id=owner.id,
        route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
        raw_key="create-key-1",
        fingerprint=fingerprint,
    )
    assert second.replay is True
    assert second.http_status == 201
    assert second.response_refs == {"conversationId": "conv_abc"}
    assert side_effects == 1
    rows = list(db.scalars(select(HttpIdempotencyRecord)))
    assert len(rows) == 1
    assert rows[0].state == HTTP_IDEMPOTENCY_STATE_COMPLETED
    assert rows[0].key_hash == hash_idempotency_key("create-key-1")
    assert "create-key-1" not in (rows[0].response_refs_json or "")


def test_fingerprint_mismatch_conflicts(db: Session) -> None:
    owner = _user(db)
    first = begin_idempotent(
        db,
        principal_user_id=owner.id,
        route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
        raw_key="create-key-2",
        fingerprint=fingerprint_payload({"title": "One"}),
    )
    complete_idempotent(
        db,
        first.record,
        http_status=201,
        response_kind="conversation",
        response_refs={"conversationId": "conv_one"},
    )
    db.commit()

    with pytest.raises(IdempotencyError) as exc_info:
        begin_idempotent(
            db,
            principal_user_id=owner.id,
            route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
            raw_key="create-key-2",
            fingerprint=fingerprint_payload({"title": "Two"}),
        )
    assert (exc_info.value.status_code, exc_info.value.code) == (409, "idempotency_conflict")


def test_pending_same_fingerprint_is_capacity_unavailable(db: Session) -> None:
    owner = _user(db)
    fingerprint = fingerprint_payload({"title": "Pending"})
    begin_idempotent(
        db,
        principal_user_id=owner.id,
        route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
        raw_key="create-key-3",
        fingerprint=fingerprint,
    )
    db.commit()

    with pytest.raises(IdempotencyError) as exc_info:
        begin_idempotent(
            db,
            principal_user_id=owner.id,
            route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
            raw_key="create-key-3",
            fingerprint=fingerprint,
        )
    assert (exc_info.value.status_code, exc_info.value.code) == (503, "capacity_unavailable")


def test_abandon_clears_pending_claim(db: Session) -> None:
    owner = _user(db)
    fingerprint = fingerprint_payload({"title": "Abandon"})
    claim = begin_idempotent(
        db,
        principal_user_id=owner.id,
        route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
        raw_key="create-key-4",
        fingerprint=fingerprint,
    )
    assert claim.record.state == HTTP_IDEMPOTENCY_STATE_PENDING
    abandon_idempotent(db, claim.record)
    db.commit()
    assert db.scalar(select(HttpIdempotencyRecord)) is None

    retry = begin_idempotent(
        db,
        principal_user_id=owner.id,
        route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
        raw_key="create-key-4",
        fingerprint=fingerprint,
    )
    assert retry.replay is False


def test_privacy_row_has_no_raw_key_or_password_material(db: Session) -> None:
    owner = _user(db)
    secretish = "password=hunter2&token=raw-secret"
    claim = begin_idempotent(
        db,
        principal_user_id=owner.id,
        route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
        raw_key=secretish,
        fingerprint=fingerprint_payload({"title": None}),
    )
    complete_idempotent(
        db,
        claim.record,
        http_status=201,
        response_kind="conversation",
        response_refs={"conversationId": "conv_safe"},
    )
    db.commit()
    row = db.scalar(select(HttpIdempotencyRecord))
    assert row is not None
    blob = " ".join(
        [
            row.key_hash,
            row.fingerprint,
            row.response_kind or "",
            row.response_refs_json or "",
        ]
    )
    assert "hunter2" not in blob
    assert "raw-secret" not in blob
    assert secretish not in blob
