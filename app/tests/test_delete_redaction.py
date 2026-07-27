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
    User,
)
from context_engine.services.chat_turns import (
    _execution_fence_open,
    _persist_event,
    redact_turns_for_domain,
)
from context_engine.services.domains import enqueue_delete_domain


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
