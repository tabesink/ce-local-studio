"""P8-01 adversarial privacy scans over persisted audit_events rows only."""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import AuditEvent, AuthSession, User
from context_engine.services.audit import ALLOWED_AUDIT_METADATA_KEYS, AuditContext
from context_engine.services.conversations import create_conversation, update_conversation_title

SERVICE_SETTINGS = Settings(testing=True)

FORBIDDEN_SUBSTRINGS = (
    "SECRET_PROMPT_SENTINEL",
    "SECRET_ANSWER_SENTINEL",
    "SECRET_EXCERPT_SENTINEL",
    "SECRET_CREDENTIAL_SENTINEL",
    "SECRET_TITLE_SENTINEL",
    "https://runtime.example.invalid/path",
    "s3://bucket/object-key",
    "Traceback (most recent call last)",
    "composer_token_raw_",
)


def _serialize_audit_row(event: AuditEvent) -> str:
    payload = {
        "event_name": event.event_name,
        "actor_kind": event.actor_kind,
        "actor_user_id": event.actor_user_id,
        "target_kind": event.target_kind,
        "target_id": event.target_id,
        "request_id": event.request_id,
        "trace_id": event.trace_id,
        "outcome": event.outcome,
        "safe_error_code": event.safe_error_code,
        "metadata_json": event.metadata_json,
    }
    return json.dumps(payload, sort_keys=True)


def _assert_audit_rows_private(events: list[AuditEvent]) -> None:
    for event in events:
        blob = _serialize_audit_row(event)
        for sentinel in FORBIDDEN_SUBSTRINGS:
            assert sentinel not in blob, f"{sentinel!r} leaked into audit event {event.event_name}"
        if event.metadata_json:
            metadata = json.loads(event.metadata_json)
            assert isinstance(metadata, dict)
            assert set(metadata).issubset(ALLOWED_AUDIT_METADATA_KEYS)


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


def _user(db: Session, username: str) -> User:
    user = User(username=username, password_hash="synthetic-password-hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_session(db: Session, owner: User) -> AuthSession:
    now = utc_now()
    auth_session = AuthSession(
        user_id=owner.id,
        token_hash=uuid4().hex * 2,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        last_used_at=now,
    )
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    return auth_session


def test_conversation_title_sentinels_absent_from_audit_rows(db: Session) -> None:
    owner = _user(db, "member-privacy@example.test")
    auth_session = _auth_session(db, owner)
    context = AuditContext(actor_user=owner, request_id="req-privacy-1")

    conversation = create_conversation(
        db,
        settings=SERVICE_SETTINGS,
        owner=owner,
        title="SECRET_TITLE_SENTINEL",
        auth_session=auth_session,
        audit_context=context,
    )
    update_conversation_title(
        db,
        settings=SERVICE_SETTINGS,
        owner=owner,
        conversation_id=conversation.public_ref,
        title="SECRET_TITLE_SENTINEL renamed",
        expected_version=conversation.version,
        auth_session=auth_session,
        audit_context=context,
    )

    events = list(db.scalars(select(AuditEvent)))
    assert len(events) >= 2
    _assert_audit_rows_private(events)
    for event in events:
        assert event.target_id == conversation.public_ref
        assert "SECRET_TITLE" not in (event.metadata_json or "")


def test_audit_metadata_keys_closed_for_planted_content(db: Session) -> None:
    from context_engine.services.audit import AuditError, AuditService

    with pytest.raises(AuditError):
        AuditService(db).record(
            "conversation.created",
            context=AuditContext(actor_kind="member", request_id="req-meta"),
            metadata={
                "prompt": "SECRET_PROMPT_SENTINEL",
                "operationType": "create",
            },
        )
    assert db.scalars(select(AuditEvent)).first() is None
