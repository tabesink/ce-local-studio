from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from datetime import timedelta

from context_engine.db import Base, utc_now
from context_engine.models import (
    COMPOSER_REF_KIND_EVIDENCE,
    COMPOSER_REF_KIND_SOURCE,
    DOMAIN_STATE_DELETING,
    DOMAIN_STATE_STOPPED,
    ROLE_ADMINISTRATOR,
    ComposerRefToken,
    Conversation,
    ConversationTurn,
    ConversationTurnComposerRef,
    ConversationTurnEvidenceRef,
    ConversationTurnEvent,
    Domain,
    ModelProfile,
    ProviderConfig,
    SourceDocument,
    TURN_EVENT_ANSWER_DELTA,
    TURN_EVENT_REDACTED,
    TURN_ROUTE_DIRECT_LLM,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_STATUS_COMPLETED,
    TURN_STATUS_REDACTED,
    TURN_STATUS_RUNNING,
    TURN_STOP_REASON_DIRECT_LLM,
    User,
)
from context_engine.config import Settings
from context_engine.services.chat_turns import (
    _complete_turn,
    _execution_fence_open,
    _persist_event,
    _stored_events,
    _terminal_snapshot,
    redact_turns_for_domain,
    safe_turn_dto,
)
from context_engine.services.composer_refs import ComposerRefError, _token_hash, validate_composer_ref_tokens
from context_engine.services.domains import enqueue_delete_domain
from context_engine.services.sources import enqueue_delete_source


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'delete-redaction.db'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def _owner_conversation(db: Session) -> tuple[User, Conversation]:
    owner = User(username="redact-owner@example.test", password_hash="synthetic-password-hash")
    conversation = Conversation(owner=owner, title="Delete redaction")
    db.add_all([owner, conversation])
    db.flush()
    return owner, conversation


def _source(db: Session, *, source_id: str, domain_id: str) -> SourceDocument:
    source = SourceDocument(
        id=source_id,
        public_ref=f"document-{source_id}",
        domain_id=domain_id,
        original_filename="manual.pdf",
        content_type="application/pdf",
        original_sha256="a" * 64,
        original_size_bytes=128,
        original_object_key=f"source/{source_id}",
        state="prepared",
        parser_kind="docling",
    )
    db.add(source)
    db.flush()
    return source


def _turn(
    db: Session,
    conversation: Conversation,
    *,
    client_request_id: str,
    route: str,
    domain_id: str | None = None,
    status: str = TURN_STATUS_COMPLETED,
    assistant_answer: str = "Sensitive answer.",
) -> ConversationTurn:
    now = utc_now()
    turn = ConversationTurn(
        conversation=conversation,
        client_request_id=client_request_id,
        route=route,
        domain_id=domain_id,
        status=status,
        user_message="Retained question.",
        assistant_answer=assistant_answer,
        started_at=now,
        completed_at=now if status != TURN_STATUS_RUNNING else None,
        created_at=now,
        updated_at=now,
    )
    db.add(turn)
    db.flush()
    return turn


def test_redact_turns_for_domain_commit_false_defers_publish(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        _, conversation = _owner_conversation(db)
        turn = _turn(
            db,
            conversation,
            client_request_id="domain-rag-1",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id="domain-a",
        )
        db.commit()

        changed = redact_turns_for_domain(db, "domain-a", commit=False)
        assert changed == 1
        db.refresh(turn)
        assert turn.status == TURN_STATUS_REDACTED

        other = Session(db.get_bind())
        try:
            isolated = other.get(ConversationTurn, turn.id)
            assert isolated is not None
            assert isolated.status == TURN_STATUS_COMPLETED
            assert isolated.assistant_answer == "Sensitive answer."
        finally:
            other.close()

        db.commit()
        other = Session(db.get_bind())
        try:
            published = other.get(ConversationTurn, turn.id)
            assert published is not None
            assert published.status == TURN_STATUS_REDACTED
            assert published.assistant_answer is None
            events = list(
                other.scalars(
                    select(ConversationTurnEvent)
                    .where(ConversationTurnEvent.turn_id == turn.id)
                    .order_by(ConversationTurnEvent.sequence)
                )
            )
            assert events[-1].event_type == TURN_EVENT_REDACTED
        finally:
            other.close()
    finally:
        db.close()


def test_redact_turns_for_domain_is_idempotent(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        _, conversation = _owner_conversation(db)
        turn = _turn(
            db,
            conversation,
            client_request_id="domain-rag-2",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id="domain-a",
        )
        db.commit()

        assert redact_turns_for_domain(db, "domain-a") == 1
        assert redact_turns_for_domain(db, "domain-a") == 0
        events = list(
            db.scalars(
                select(ConversationTurnEvent)
                .where(
                    ConversationTurnEvent.turn_id == turn.id,
                    ConversationTurnEvent.event_type == TURN_EVENT_REDACTED,
                )
            )
        )
        assert len(events) == 1
    finally:
        db.close()


def test_redact_turns_for_domain_selects_evidence_and_composer_linked_turns(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        _, conversation = _owner_conversation(db)
        source = _source(db, source_id="source-a", domain_id="domain-a")
        domain_rag = _turn(
            db,
            conversation,
            client_request_id="domain-rag-3",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id="domain-a",
            assistant_answer="Domain RAG answer.",
        )
        evidence_only = _turn(
            db,
            conversation,
            client_request_id="direct-evidence",
            route=TURN_ROUTE_DIRECT_LLM,
            assistant_answer="Evidence-linked answer.",
        )
        db.add(
            ConversationTurnEvidenceRef(
                turn_id=evidence_only.id,
                evidence_order=1,
                citation_label="E1",
                source_label="manual.pdf",
                excerpt="Sensitive excerpt.",
                source_document_id=source.id,
                source_block_id="block-a",
            )
        )
        composer_only = _turn(
            db,
            conversation,
            client_request_id="direct-composer",
            route=TURN_ROUTE_DIRECT_LLM,
            assistant_answer="Composer-linked answer.",
        )
        db.add(
            ConversationTurnComposerRef(
                turn_id=composer_only.id,
                ref_order=1,
                ref_kind="source",
                safe_label="Source ref",
                safe_description="Linked source",
                domain_id="domain-a",
                source_document_id=source.id,
            )
        )
        unrelated = _turn(
            db,
            conversation,
            client_request_id="other-domain",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id="domain-b",
            assistant_answer="Other domain answer.",
        )
        db.commit()

        changed = redact_turns_for_domain(db, "domain-a")
        assert changed == 3
        db.refresh(domain_rag)
        db.refresh(evidence_only)
        db.refresh(composer_only)
        db.refresh(unrelated)
        assert domain_rag.status == TURN_STATUS_REDACTED
        assert evidence_only.status == TURN_STATUS_REDACTED
        assert composer_only.status == TURN_STATUS_REDACTED
        assert unrelated.status == TURN_STATUS_COMPLETED
        assert unrelated.assistant_answer == "Other domain answer."
    finally:
        db.close()


def _seed_domain(db: Session, *, domain_id: str = "domain-a") -> tuple[User, Domain, SourceDocument]:
    admin = User(
        username="admin-redact@example.test",
        password_hash="synthetic-password-hash",
        role=ROLE_ADMINISTRATOR,
    )
    provider = ProviderConfig(
        provider_kind="openai",
        display_name="OpenAI",
        requires_credentials=True,
    )
    profile = ModelProfile(
        id="embed-profile",
        name="Embedding",
        profile_kind="embedding",
        provider_kind="openai",
        model_name="text-embedding-3-small",
        vector_dimensions=1536,
    )
    domain = Domain(
        id=domain_id,
        display_name="Manuals",
        state=DOMAIN_STATE_STOPPED,
        embedding_profile_id=profile.id,
    )
    source = SourceDocument(
        id="source-a",
        public_ref="document-source-a",
        domain_id=domain.id,
        original_filename="manual.pdf",
        content_type="application/pdf",
        original_sha256="b" * 64,
        original_size_bytes=128,
        original_object_key="source/source-a",
        state="prepared",
        parser_kind="docling",
    )
    db.add_all([admin, provider, profile, domain, source])
    db.flush()
    return admin, domain, source


def test_enqueue_delete_domain_redacts_and_expires_tokens_in_fence(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        admin, domain, source = _seed_domain(db)
        _, conversation = _owner_conversation(db)
        turn = _turn(
            db,
            conversation,
            client_request_id="domain-enqueue",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id=domain.id,
            assistant_answer="Must redact at enqueue.",
        )
        evidence_turn = _turn(
            db,
            conversation,
            client_request_id="evidence-enqueue",
            route=TURN_ROUTE_DIRECT_LLM,
            assistant_answer="Evidence linked.",
        )
        evidence_ref = ConversationTurnEvidenceRef(
            turn_id=evidence_turn.id,
            evidence_order=1,
            citation_label="E1",
            source_label="manual.pdf",
            excerpt="Sensitive excerpt.",
            source_document_id=source.id,
            source_block_id="block-a",
        )
        db.add(evidence_ref)
        db.flush()
        future = utc_now() + timedelta(hours=1)
        source_token = ComposerRefToken(
            token_hash="c" * 64,
            owner_user_id=admin.id,
            ref_kind=COMPOSER_REF_KIND_SOURCE,
            target_id=source.id,
            domain_id=domain.id,
            expires_at=future,
        )
        evidence_token = ComposerRefToken(
            token_hash="d" * 64,
            owner_user_id=admin.id,
            ref_kind=COMPOSER_REF_KIND_EVIDENCE,
            target_id=evidence_ref.id,
            domain_id=domain.id,
            expires_at=future,
        )
        db.add_all([source_token, evidence_token])
        db.commit()
        domain_version = domain.version

        operation = enqueue_delete_domain(
            db,
            domain_id=domain.id,
            requested_by_user=admin,
            expected_version=domain_version,
            audit_context=None,
        )
        db.refresh(domain)
        db.refresh(turn)
        db.refresh(evidence_turn)
        db.refresh(source_token)
        db.refresh(evidence_token)

        assert operation.status == "queued"
        assert domain.state == DOMAIN_STATE_DELETING
        assert turn.status == TURN_STATUS_REDACTED
        assert turn.assistant_answer is None
        assert evidence_turn.status == TURN_STATUS_REDACTED
        assert source_token.expires_at <= utc_now()
        assert evidence_token.expires_at <= utc_now()
    finally:
        db.close()


def test_redacted_turn_blocks_non_redacted_event_append(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        _, conversation = _owner_conversation(db)
        turn = _turn(
            db,
            conversation,
            client_request_id="running-fence",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id="domain-a",
            status=TURN_STATUS_RUNNING,
            assistant_answer=None,
        )
        turn.execution_generation = 1
        db.commit()

        assert redact_turns_for_domain(db, "domain-a") == 1
        db.refresh(turn)
        assert turn.status == TURN_STATUS_REDACTED
        assert _execution_fence_open(db, turn, 1) is False
        with pytest.raises(RuntimeError, match="Cannot append an event to a terminal turn"):
            _persist_event(
                db,
                turn=turn,
                event_type=TURN_EVENT_ANSWER_DELTA,
                payload={"text": "Late answer."},
                execution_generation=1,
            )
    finally:
        db.close()


def test_source_delete_enqueue_omits_public_projection_and_terminal_snapshot(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        admin, domain, source = _seed_domain(db, domain_id="domain-src")
        _, conversation = _owner_conversation(db)
        turn = _turn(
            db,
            conversation,
            client_request_id="source-delete-omission",
            route=TURN_ROUTE_DIRECT_LLM,
            status=TURN_STATUS_RUNNING,
            assistant_answer=None,
        )
        db.flush()
        _persist_event(
            db,
            turn=turn,
            event_type=TURN_EVENT_ANSWER_DELTA,
            payload={"text": "SENTINEL_ANSWER_MUST_OMIT"},
            commit=False,
        )
        db.add(
            ConversationTurnEvidenceRef(
                turn_id=turn.id,
                evidence_order=1,
                citation_label="E1",
                source_label="manual.pdf",
                excerpt="SENTINEL_EXCERPT_MUST_OMIT",
                source_document_id=source.id,
                source_block_id="block-src",
            )
        )
        turn = _complete_turn(
            db,
            turn=turn,
            stop_reason=TURN_STOP_REASON_DIRECT_LLM,
            assistant_answer="SENTINEL_ANSWER_MUST_OMIT",
        )
        db.commit()

        enqueue_delete_source(
            db,
            domain_id=domain.id,
            source_id=source.id,
            expected_version=source.version,
            requested_by_user=admin,
            audit_context=None,
        )
        db.refresh(turn)
        settings = Settings(database_url="sqlite+pysqlite:///:memory:", testing=True)
        dto = safe_turn_dto(db, settings, turn)
        snapshot = _terminal_snapshot(db, settings, turn)
        events = list(_stored_events(db, turn))
        serialized = str(dto) + str(snapshot) + str([event.payload for event in events])

        assert turn.status == TURN_STATUS_REDACTED
        assert turn.user_message == "Retained question."
        assert dto["status"] == TURN_STATUS_REDACTED
        assert dto["assistantAnswer"] is None
        assert dto["evidence"] == []
        assert dto["acceptedRefs"] == []
        assert dto["userMessage"] == "Retained question."
        assert snapshot == {
            "turnId": turn.public_ref,
            "status": TURN_STATUS_REDACTED,
            "answer": None,
            "evidence": [],
            "citations": [],
        }
        assert events[-1].event_type == TURN_EVENT_REDACTED
        assert "SENTINEL_ANSWER_MUST_OMIT" not in serialized
        assert "SENTINEL_EXCERPT_MUST_OMIT" not in serialized
    finally:
        db.close()


def test_m11_source_delete_clears_accepted_refs_and_expires_composer_tokens(tmp_path: Path) -> None:
    """P11-03 U4 / AE5 — real accepted-ref rows omit publicly; source tokens expire."""
    db = _session(tmp_path)
    try:
        admin, domain, source = _seed_domain(db, domain_id="domain-composer-src")
        owner, conversation = _owner_conversation(db)
        turn = _turn(
            db,
            conversation,
            client_request_id="source-delete-accepted-refs",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id=domain.id,
            status=TURN_STATUS_RUNNING,
            assistant_answer=None,
        )
        db.flush()
        db.add(
            ConversationTurnComposerRef(
                turn_id=turn.id,
                ref_order=1,
                ref_kind=COMPOSER_REF_KIND_SOURCE,
                safe_label="SENTINEL_ACCEPTED_LABEL",
                safe_description="SENTINEL_ACCEPTED_DESC",
                domain_id=domain.id,
                source_document_id=source.id,
            )
        )
        raw = "ce-p11-03-delete-token-raw"
        now = utc_now()
        db.add(
            ComposerRefToken(
                token_hash=_token_hash(raw),
                owner_user_id=owner.id,
                ref_kind=COMPOSER_REF_KIND_SOURCE,
                target_id=source.id,
                domain_id=domain.id,
                safe_label="Live source token",
                safe_description=None,
                expires_at=now + timedelta(hours=1),
                created_at=now,
            )
        )
        turn = _complete_turn(
            db,
            turn=turn,
            stop_reason=TURN_STOP_REASON_DIRECT_LLM,
            assistant_answer="SENTINEL_ANSWER_MUST_OMIT",
        )
        db.commit()

        settings = Settings(database_url="sqlite+pysqlite:///:memory:", testing=True)
        before = safe_turn_dto(db, settings, turn)
        assert before["acceptedRefs"]
        assert before["acceptedRefs"][0]["label"] == "SENTINEL_ACCEPTED_LABEL"

        enqueue_delete_source(
            db,
            domain_id=domain.id,
            source_id=source.id,
            expected_version=source.version,
            requested_by_user=admin,
            audit_context=None,
        )
        db.refresh(turn)
        dto = safe_turn_dto(db, settings, turn)
        accepted_row = db.scalar(
            select(ConversationTurnComposerRef).where(ConversationTurnComposerRef.turn_id == turn.id)
        )
        token_row = db.scalar(
            select(ComposerRefToken).where(ComposerRefToken.token_hash == _token_hash(raw))
        )

        assert turn.status == TURN_STATUS_REDACTED
        assert turn.user_message == "Retained question."
        assert turn.assistant_answer is None
        assert dto["acceptedRefs"] == []
        assert dto["assistantAnswer"] is None
        assert dto["evidence"] == []
        assert accepted_row is not None
        assert accepted_row.redacted_at is not None
        assert accepted_row.safe_label is None
        assert accepted_row.safe_description is None
        assert token_row is not None
        assert token_row.expires_at <= utc_now() + timedelta(seconds=1)

        with pytest.raises(ComposerRefError) as error:
            validate_composer_ref_tokens(
                db,
                settings=settings,
                owner=owner,
                conversation_id=conversation.id,
                domain_id=domain.id,
                tokens=[raw],
            )
        assert error.value.code == "composer_ref_unavailable"
        assert source.id not in error.value.message
        assert raw not in error.value.message
    finally:
        db.close()


def test_late_complete_after_redaction_cannot_unredact(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        _, conversation = _owner_conversation(db)
        turn = _turn(
            db,
            conversation,
            client_request_id="late-complete",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id="domain-a",
            status=TURN_STATUS_RUNNING,
            assistant_answer=None,
        )
        turn.execution_generation = 2
        db.commit()

        assert redact_turns_for_domain(db, "domain-a") == 1
        late = _complete_turn(
            db,
            turn=turn,
            stop_reason=TURN_STOP_REASON_DIRECT_LLM,
            assistant_answer="LATE_ANSWER_MUST_NOT_LAND",
            execution_generation=2,
        )
        db.refresh(late)
        assert late.status == TURN_STATUS_REDACTED
        assert late.assistant_answer is None
        assert "LATE_ANSWER_MUST_NOT_LAND" not in (late.assistant_answer or "")
    finally:
        db.close()
