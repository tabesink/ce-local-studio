"""P8-01 adversarial privacy scans over persisted audit_events rows only."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    DOMAIN_STATE_STOPPED,
    ROLE_ADMINISTRATOR,
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_COMPLETED,
    TURN_STOP_REASON_DIRECT_LLM,
    AuditEvent,
    AuthSession,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    Domain,
    User,
)
from context_engine.services.audit import ALLOWED_AUDIT_METADATA_KEYS, AuditContext
from context_engine.services.auth import create_user
from context_engine.services.chat_turns import redact_turns_for_domain
from context_engine.services.conversations import create_conversation, update_conversation_title
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config
from context_engine.services.sources import upload_source_bytes

FORBIDDEN_SUBSTRINGS = (
    "SECRET_PROMPT_SENTINEL",
    "SECRET_ANSWER_SENTINEL",
    "SECRET_EXCERPT_SENTINEL",
    "SECRET_CREDENTIAL_SENTINEL",
    "SECRET_TITLE_SENTINEL",
    "SECRET_FILENAME_SENTINEL",
    "SECRET_BODY_SENTINEL",
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
    settings = Settings(testing=True)
    owner = _user(db, "member-privacy@example.test")
    auth_session = _auth_session(db, owner)
    context = AuditContext(actor_user=owner, request_id="req-privacy-1")

    conversation = create_conversation(
        db,
        settings=settings,
        owner=owner,
        title="SECRET_TITLE_SENTINEL",
        auth_session=auth_session,
        audit_context=context,
    )
    update_conversation_title(
        db,
        settings=settings,
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


def test_ae6_credential_upload_redaction_sentinels_absent_from_audit_rows(
    db: Session,
    tmp_path: Path,
) -> None:
    settings = Settings(
        testing=True,
        source_storage_root=str(tmp_path / "source-storage"),
        domain_runtime_root=str(tmp_path / "domain-runtimes"),
        domain_runtime_controller_kind="local",
    )
    seed_runtime_config(db)
    admin = create_user(
        db,
        "admin-privacy@example.test",
        "Password123!",
        role=ROLE_ADMINISTRATOR,
    )
    member = create_user(db, "member-privacy-ae6@example.test", "Password123!")
    auth_session = _auth_session(db, member)
    admin_audit = AuditContext(actor_user=admin, request_id="req-privacy-ae6-admin")
    member_audit = AuditContext(actor_user=member, request_id="req-privacy-ae6-member")

    rotate_provider_credential(
        db,
        "openai",
        "SECRET_CREDENTIAL_SENTINEL",
        SecretCrypto.from_settings(settings),
        expected_version=1,
        audit_context=admin_audit,
    )

    conversation = create_conversation(
        db,
        settings=settings,
        owner=member,
        title="SECRET_TITLE_SENTINEL",
        auth_session=auth_session,
        audit_context=member_audit,
    )
    update_conversation_title(
        db,
        settings=settings,
        owner=member,
        conversation_id=conversation.public_ref,
        title="SECRET_TITLE_SENTINEL renamed",
        expected_version=conversation.version,
        auth_session=auth_session,
        audit_context=member_audit,
    )

    domain = Domain(
        id="domain-privacy-ae6",
        display_name="Privacy AE6",
        state=DOMAIN_STATE_STOPPED,
        embedding_profile_id="openai-embedding-default",
    )
    db.add(domain)
    db.commit()

    source, _operation = upload_source_bytes(
        db,
        settings=settings,
        domain_id=domain.id,
        filename="SECRET_FILENAME_SENTINEL.pdf",
        content_type="application/pdf",
        data=b"%PDF-1.4 SECRET_BODY_SENTINEL privacy-scan",
        requested_by_user=admin,
        audit_context=admin_audit,
    )
    assert "SECRET_FILENAME_SENTINEL" in source.original_filename

    now = utc_now()
    turn = ConversationTurn(
        conversation_id=conversation.id,
        client_request_id="privacy-ae6-turn",
        route=TURN_ROUTE_DIRECT_LLM,
        status=TURN_STATUS_COMPLETED,
        stop_reason=TURN_STOP_REASON_DIRECT_LLM,
        user_message="SECRET_PROMPT_SENTINEL",
        assistant_answer="SECRET_ANSWER_SENTINEL",
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(turn)
    db.flush()
    db.add(
        ConversationTurnEvidenceRef(
            turn_id=turn.id,
            evidence_order=1,
            citation_label="E1",
            source_label="SECRET_FILENAME_SENTINEL.pdf",
            excerpt="SECRET_EXCERPT_SENTINEL",
            source_document_id=source.id,
            source_block_id="block-privacy-ae6",
        )
    )
    db.commit()

    changed = redact_turns_for_domain(db, domain.id, audit_context=admin_audit)
    assert changed == 1

    events = list(db.scalars(select(AuditEvent)))
    assert any(event.event_name == "runtime_settings.provider_config_rotated" for event in events)
    assert any(event.event_name == "source.uploaded" for event in events)
    assert any(event.event_name == "chat.turn_redacted" for event in events)
    _assert_audit_rows_private(events)


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


def test_direct_audit_record_rejects_smuggled_forbidden_metadata_keys(db: Session) -> None:
    from context_engine.services.audit import AuditError, AuditService

    for key, value in (
        ("credential", "SECRET_CREDENTIAL_SENTINEL"),
        ("path", "https://runtime.example.invalid/path"),
        ("objectKey", "s3://bucket/object-key"),
        ("prompt", "SECRET_PROMPT_SENTINEL"),
        ("excerpt", "SECRET_EXCERPT_SENTINEL"),
    ):
        with pytest.raises(AuditError):
            AuditService(db).record(
                "source.uploaded",
                context=AuditContext(actor_kind="administrator", request_id="req-meta-2"),
                metadata={key: value},
            )
    assert list(db.scalars(select(AuditEvent))) == []
