from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import Base, utc_now
import context_engine.services.chat_turns as chat_turns_module
import context_engine.services.public_refs as public_refs_module
from context_engine.models import (
    DOMAIN_STATE_RUNNING,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_COMPLETED,
    AuditEvent,
    AuthSession,
    Conversation,
    ConversationTurn,
    Domain,
    ModelProfile,
    ProviderConfig,
    User,
)
from context_engine.services.audit import AuditContext, AuditError, AuditService
from context_engine.services.conversations import (
    ConversationError,
    create_conversation,
    delete_conversation,
    get_owned_conversation,
    list_conversations,
    safe_conversation_summary,
    update_conversation_title,
)
from context_engine.services.chat_turns import claim_turn, conversation_turn_summaries
from context_engine.services.public_refs import PublicRefCollisionError


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


SERVICE_SETTINGS = Settings(testing=True)


def test_p7_01_owner_crud_uses_public_refs_versions_and_atomic_audit(db: Session) -> None:
    owner = _user(db, "owner@example.test")
    other = _user(db, "other@example.test")
    auth_session = _auth_session(db, owner)
    audit = AuditContext(actor_user=owner, request_id="req-p7-owner-crud")

    conversation = create_conversation(
        db,
        settings=SERVICE_SETTINGS,
        owner=owner,
        auth_session=auth_session,
        title="  Equipment notes  ",
        audit_context=audit,
    )
    projected = safe_conversation_summary(conversation)
    assert projected == {
        "id": conversation.public_ref,
        "title": "Equipment notes",
        "createdAt": projected["createdAt"],
        "updatedAt": projected["updatedAt"],
        "version": 1,
    }
    assert conversation.public_ref.startswith("conv_")
    assert conversation.id not in str(projected)

    with pytest.raises(ConversationError) as hidden:
        get_owned_conversation(db, owner=other, conversation_id=conversation.public_ref)
    assert (hidden.value.status_code, hidden.value.code) == (404, "not_found")

    renamed = update_conversation_title(
        db,
        settings=SERVICE_SETTINGS,
        owner=owner,
        auth_session=auth_session,
        conversation_id=conversation.public_ref,
        title="Renamed",
        expected_version=1,
        audit_context=audit,
    )
    assert renamed.version == 2

    with pytest.raises(ConversationError) as stale:
        update_conversation_title(
            db,
            settings=SERVICE_SETTINGS,
            owner=owner,
            auth_session=auth_session,
            conversation_id=conversation.public_ref,
            title="Stale write",
            expected_version=1,
            audit_context=audit,
        )
    assert stale.value.code == "stale_revision"
    db.rollback()

    delete_conversation(
        db,
        settings=SERVICE_SETTINGS,
        owner=owner,
        auth_session=auth_session,
        conversation_id=conversation.public_ref,
        expected_version=2,
        audit_context=audit,
    )
    assert db.scalar(select(Conversation).where(Conversation.public_ref == conversation.public_ref)) is None
    events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)))
    assert [event.event_name for event in events] == [
        "conversation.created",
        "conversation.renamed",
        "conversation.deleted",
    ]
    assert all(event.target_id == conversation.public_ref for event in events)
    assert all(event.request_id == "req-p7-owner-crud" for event in events)


def test_p7_01_conversation_cursor_is_owner_scoped_and_stable(db: Session) -> None:
    owner = _user(db, "cursor-owner@example.test")
    other = _user(db, "cursor-other@example.test")
    base = utc_now() - timedelta(minutes=3)
    rows: list[Conversation] = []
    for offset in range(3):
        row = Conversation(
            owner_user_id=owner.id,
            title=f"Conversation {offset}",
            created_at=base + timedelta(minutes=offset),
            updated_at=base + timedelta(minutes=offset),
        )
        db.add(row)
        rows.append(row)
    db.commit()

    first = list_conversations(db, owner=owner, limit=2)
    assert [item["title"] for item in first.conversations] == ["Conversation 2", "Conversation 1"]
    assert first.next_cursor is not None
    assert rows[1].id not in first.next_cursor

    second = list_conversations(db, owner=owner, cursor=first.next_cursor, limit=2)
    assert [item["title"] for item in second.conversations] == ["Conversation 0"]
    assert second.next_cursor is None

    with pytest.raises(ConversationError) as cross_owner:
        list_conversations(db, owner=other, cursor=first.next_cursor, limit=2)
    assert (cross_owner.value.status_code, cross_owner.value.code) == (410, "cursor_expired")


def test_p7_01_legacy_accepted_event_projection_does_not_rewrite_stored_payload(db: Session) -> None:
    from context_engine.models import (
        TURN_EVENT_ACCEPTED,
        TURN_ROUTE_DIRECT_LLM,
        TURN_STATUS_RUNNING,
        ConversationTurn,
    )
    from context_engine.services.chat_turns import _persist_event, _stored_events

    owner = _user(db, "legacy-event-owner@example.test")
    conversation = Conversation(owner_user_id=owner.id, title="Legacy replay")
    db.add(conversation)
    db.flush()
    turn = ConversationTurn(
        conversation_id=conversation.id,
        client_request_id="legacy-event-request",
        route=TURN_ROUTE_DIRECT_LLM,
        status=TURN_STATUS_RUNNING,
        user_message="Replay safely.",
    )
    db.add(turn)
    db.flush()
    _persist_event(
        db,
        turn=turn,
        event_type=TURN_EVENT_ACCEPTED,
        payload={
            "conversationId": conversation.id,
            "clientRequestId": turn.client_request_id,
            "replay": False,
        },
    )

    event = next(_stored_events(db, turn))
    assert event.turn_id == turn.public_ref
    assert event.payload["conversationId"] == conversation.public_ref
    stored = turn.events[0]
    assert conversation.id in stored.payload_json
    assert conversation.public_ref not in stored.payload_json


def test_p7_01_audit_failure_rolls_back_conversation_creation(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _user(db, "audit-failure-owner@example.test")
    auth_session = _auth_session(db, owner)

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise AuditError()

    monkeypatch.setattr(AuditService, "record", fail_audit)
    with pytest.raises(AuditError):
        create_conversation(
            db,
            settings=SERVICE_SETTINGS,
            owner=owner,
            auth_session=auth_session,
            title="Must roll back",
        )
    assert db.scalar(select(Conversation).where(Conversation.owner_user_id == owner.id)) is None


def test_p7_01_mutation_revalidates_enabled_user_and_live_session(db: Session) -> None:
    owner = _user(db, "session-owner@example.test")
    auth_session = _auth_session(db, owner)
    conversation = create_conversation(
        db,
        settings=SERVICE_SETTINGS,
        owner=owner,
        auth_session=auth_session,
    )

    auth_session.revoked_at = utc_now()
    db.commit()
    with pytest.raises(ConversationError) as revoked:
        update_conversation_title(
            db,
            settings=SERVICE_SETTINGS,
            owner=owner,
            auth_session=auth_session,
            conversation_id=conversation.public_ref,
            title="Rejected",
            expected_version=1,
        )
    assert (revoked.value.status_code, revoked.value.code) == (401, "unauthenticated")
    db.rollback()

    auth_session.revoked_at = None
    owner.is_disabled = True
    db.commit()
    with pytest.raises(ConversationError) as disabled:
        delete_conversation(
            db,
            settings=SERVICE_SETTINGS,
            owner=owner,
            auth_session=auth_session,
            conversation_id=conversation.public_ref,
            expected_version=1,
        )
    assert (disabled.value.status_code, disabled.value.code) == (401, "unauthenticated")
    db.rollback()
    assert db.scalar(select(Conversation).where(Conversation.public_ref == conversation.public_ref)) is not None


def test_p7_01_turn_detail_uses_authoritative_domain_query_eligibility(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _user(db, "detail-domain-owner@example.test")
    provider = ProviderConfig(
        provider_kind="openai",
        display_name="OpenAI",
        requires_credentials=False,
    )
    profile = ModelProfile(
        name="Detail embedding",
        profile_kind="embedding",
        provider_kind="openai",
        model_name="synthetic-embedding",
        vector_dimensions=1536,
    )
    domain = Domain(
        id="detail-running-domain",
        display_name="Running but unavailable",
        state=DOMAIN_STATE_RUNNING,
        embedding_profile=profile,
    )
    conversation = Conversation(owner_user_id=owner.id, title="Domain detail")
    turn = ConversationTurn(
        conversation=conversation,
        client_request_id="detail-domain-request",
        domain_id=domain.id,
        route=TURN_ROUTE_DOMAIN_RAG,
        status=TURN_STATUS_COMPLETED,
        stop_reason="no_grounded_context",
        user_message="Use the domain.",
        completed_at=utc_now(),
    )
    db.add_all([provider, domain, conversation, turn])
    db.commit()
    monkeypatch.setattr(chat_turns_module, "controller_from_settings", lambda _settings: object())
    monkeypatch.setattr(
        chat_turns_module,
        "domain_available",
        lambda _db, _domain, _controller: False,
    )

    projected = conversation_turn_summaries(db, SERVICE_SETTINGS, conversation)

    assert projected[0]["domain"] == {
        "id": domain.id,
        "displayName": domain.display_name,
        "state": DOMAIN_STATE_RUNNING,
        "queryEligible": False,
    }


def test_p7_01_public_ref_creation_retries_bounded_collisions_and_fails_closed(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _user(db, "public-ref-collision-owner@example.test")
    auth_session = _auth_session(db, owner)
    colliding_conversation_ref = f"conv_{'a' * 32}"
    colliding_turn_ref = f"turn_{'b' * 32}"
    chat_conversation = Conversation(owner_user_id=owner.id, title="Turn collision")
    existing_conversation = Conversation(
        public_ref=colliding_conversation_ref,
        owner_user_id=owner.id,
        title="Existing ref",
    )
    existing_turn = ConversationTurn(
        public_ref=colliding_turn_ref,
        conversation=chat_conversation,
        client_request_id="existing-collision-request",
        route=TURN_ROUTE_DIRECT_LLM,
        status=TURN_STATUS_COMPLETED,
        stop_reason="direct_llm",
        user_message="Existing.",
        assistant_answer="Existing.",
        completed_at=utc_now(),
    )
    db.add_all([existing_conversation, chat_conversation, existing_turn])
    db.commit()

    fresh_conversation_ref = f"conv_{'c' * 32}"
    conversation_candidates = iter([colliding_conversation_ref, fresh_conversation_ref])
    monkeypatch.setattr(
        public_refs_module,
        "new_public_ref_candidate",
        lambda _prefix: next(conversation_candidates),
    )
    created = create_conversation(
        db,
        settings=SERVICE_SETTINGS,
        owner=owner,
        auth_session=auth_session,
        title="Retried ref",
    )
    assert created.public_ref == fresh_conversation_ref

    fresh_turn_ref = f"turn_{'d' * 32}"
    turn_candidates = iter([colliding_turn_ref, fresh_turn_ref])
    monkeypatch.setattr(
        public_refs_module,
        "new_public_ref_candidate",
        lambda _prefix: next(turn_candidates),
    )
    claimed = claim_turn(
        db,
        owner=owner,
        conversation_id=chat_conversation.public_ref,
        client_request_id="new-collision-request",
        message="Create once.",
        route=TURN_ROUTE_DIRECT_LLM,
        domain_id=None,
    )
    assert claimed.turn.public_ref == fresh_turn_ref

    monkeypatch.setattr(
        public_refs_module,
        "new_public_ref_candidate",
        lambda _prefix: colliding_conversation_ref,
    )
    before = db.scalar(select(Conversation).where(Conversation.owner_user_id == owner.id))
    with pytest.raises(PublicRefCollisionError):
        create_conversation(
            db,
            settings=SERVICE_SETTINGS,
            owner=owner,
            auth_session=auth_session,
            title="Must fail closed",
        )
    db.rollback()
    after_rows = list(db.scalars(select(Conversation).where(Conversation.owner_user_id == owner.id)))
    assert before is not None
    assert all(row.title != "Must fail closed" for row in after_rows)
