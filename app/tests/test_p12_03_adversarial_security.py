"""P12-03 gap-fill adversarial security proofs (authz / leakage / delete / retrieval).

Inventory: docs/_scratch/p12-03-adversarial-security-inventory.md
Credit cells remain in prior suites; this module covers inventory gap-fill only.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.adapters.object_storage import ObjectStorageError
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    COMPOSER_REF_KIND_SOURCE,
    DOMAIN_STATE_DELETING,
    DOMAIN_STATE_RUNNING,
    DOMAIN_STATE_STOPPED,
    ROLE_ADMINISTRATOR,
    SOURCE_INDEX_STATE_READY,
    SOURCE_PREP_OPERATION_DELETE,
    SOURCE_PREP_STATUS_FAILED,
    SOURCE_STATE_DELETING,
    SOURCE_STATE_PREPARED,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_STATUS_COMPLETED,
    TURN_STATUS_REDACTED,
    TURN_STATUS_RUNNING,
    TURN_STOP_REASON_DIRECT_LLM,
    TURN_STOP_REASON_NO_GROUNDED_CONTEXT,
    AuthSession,
    ComposerRefToken,
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    Domain,
    ModelProfile,
    ProviderConfig,
    SourceDocument,
    SourcePreparationOperation,
    User,
)
from context_engine.services.auth import create_auth_session
from context_engine.services.chat_turns import (
    ChatTurnError,
    TurnOrchestrator,
    TurnStartResult,
    safe_turn_dto,
    start_or_replay_turn,
)
from context_engine.services.composer_refs import (
    ComposerRefError,
    _token_hash,
    consume_composer_ref_tokens,
    validate_composer_ref_tokens,
)
from context_engine.services.documents import DocumentError, get_document_content
from context_engine.services.domains import enqueue_delete_domain
from context_engine.services.evidence import (
    FrozenRetrievalScope,
    FrozenSourceIdentity,
    ScopedRetrievalCandidate,
    map_retrieval_hits_to_internal_evidence,
)
from context_engine.services.runtime_config import TrustedModelRuntimeConfig
from context_engine.services.sources import SourceDeleteWorker, enqueue_delete_source
from tests.test_chat_orchestration import CountingRetrievalPort, ScriptedSynthesis, _completed_payload
from tests.test_scoped_retrieval import _MappingSession


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'p12-03.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
        domain_runtime_root=str(tmp_path / "runtime-root"),
        domain_runtime_controller_kind="local",
    )


def _session(tmp_path: Path) -> Session:
    settings = _settings(tmp_path)
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_domain_source(
    db: Session,
    *,
    domain_id: str = "domain-p1203",
    domain_state: str = DOMAIN_STATE_STOPPED,
) -> tuple[User, Domain, SourceDocument]:
    admin = User(
        username=f"admin-{uuid4().hex[:8]}@example.test",
        password_hash="synthetic-password-hash",
        role=ROLE_ADMINISTRATOR,
    )
    provider = ProviderConfig(provider_kind="openai", display_name="OpenAI", requires_credentials=True)
    profile = ModelProfile(
        id=f"embed-{uuid4().hex[:8]}",
        name="Embedding",
        profile_kind="embedding",
        provider_kind="openai",
        model_name="text-embedding-3-small",
        vector_dimensions=1536,
    )
    domain = Domain(
        id=domain_id,
        display_name="P12-03 Domain",
        state=domain_state,
        embedding_profile_id=profile.id,
        control_generation=1,
        runtime_instance_id="runtime-p1203",
    )
    source = SourceDocument(
        id=str(uuid4()),
        public_ref=f"document_{uuid4().hex}",
        domain_id=domain.id,
        original_filename="manual.pdf",
        content_type="application/pdf",
        original_sha256="c" * 64,
        original_size_bytes=128,
        original_object_key=f"source/{uuid4().hex}",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
        index_state=SOURCE_INDEX_STATE_READY,
        index_generation=1,
        index_content_hash="d" * 64,
        index_request_id="req-index-p1203",
        version=1,
    )
    db.add_all([admin, provider, profile, domain, source])
    db.flush()
    return admin, domain, source


def _owner_conversation(db: Session) -> tuple[User, Conversation, AuthSession, Settings]:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", testing=True)
    owner = User(username=f"member-{uuid4().hex[:8]}@example.test", password_hash="synthetic")
    conversation = Conversation(owner=owner, title="P12-03 conversation")
    db.add_all([owner, conversation])
    db.flush()
    _, auth_session = create_auth_session(db, owner, settings)
    return owner, conversation, auth_session, settings


def test_g1_document_content_unknown_and_deleting_share_document_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C-04 — library content denies unknown and deleting sources with the same public code."""
    import context_engine.services.documents as documents_module

    db = _session(tmp_path)
    settings = _settings(tmp_path)
    try:
        _, domain, source = _seed_domain_source(db)
        db.commit()
        unknown_ref = "document_" + ("z" * 32)
        with pytest.raises(DocumentError) as unknown:
            get_document_content(db, settings, unknown_ref)
        assert unknown.value.status_code == 404
        assert unknown.value.code == "document_not_found"

        source.state = SOURCE_STATE_DELETING
        db.commit()
        monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: True)
        with pytest.raises(DocumentError) as deleting:
            get_document_content(db, settings, source.public_ref)
        assert deleting.value.status_code == 404
        assert deleting.value.code == "document_not_found"
        assert deleting.value.message == unknown.value.message
    finally:
        db.close()


def test_g1_document_content_ineligible_matches_unknown_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import context_engine.services.documents as documents_module

    db = _session(tmp_path)
    settings = _settings(tmp_path)
    try:
        _, _, source = _seed_domain_source(db)
        db.commit()
        monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: False)
        with pytest.raises(DocumentError) as ineligible:
            get_document_content(db, settings, source.public_ref)
        with pytest.raises(DocumentError) as unknown:
            get_document_content(db, settings, "document_" + ("y" * 32))
        assert ineligible.value.status_code == unknown.value.status_code == 404
        assert ineligible.value.code == unknown.value.code == "document_not_found"
        assert ineligible.value.message == unknown.value.message
    finally:
        db.close()


def test_g2_cleanup_failure_then_retry_keeps_redaction_tokens_and_fence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-09 — cleanup fail then retry never restores answer, tokens, or eligibility."""
    import context_engine.services.sources as sources_module

    db = _session(tmp_path)
    settings = _settings(tmp_path)
    try:
        admin, domain, source = _seed_domain_source(db)
        owner, conversation, _, _ = _owner_conversation(db)
        now = utc_now()
        turn = ConversationTurn(
            conversation_id=conversation.id,
            client_request_id=f"cleanup-{uuid4().hex}",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id=domain.id,
            status=TURN_STATUS_COMPLETED,
            stop_reason=TURN_STOP_REASON_DIRECT_LLM,
            user_message="Retained question.",
            assistant_answer="SENTINEL_ANSWER_MUST_STAY_REDACTED",
            started_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        raw = f"ce-p12-03-cleanup-{uuid4().hex}"
        db.add(turn)
        db.flush()
        db.add(
            ConversationTurnEvidenceRef(
                turn_id=turn.id,
                evidence_order=1,
                citation_label="E1",
                source_label="manual.pdf",
                excerpt="SENTINEL_EXCERPT_MUST_STAY_REDACTED",
                source_document_id=source.id,
                source_block_id="block-cleanup",
            )
        )
        db.add(
            ComposerRefToken(
                token_hash=_token_hash(raw),
                owner_user_id=owner.id,
                ref_kind=COMPOSER_REF_KIND_SOURCE,
                target_id=source.id,
                domain_id=domain.id,
                safe_label="Live source token",
                expires_at=now + timedelta(hours=1),
                created_at=now,
            )
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
        db.refresh(source)
        assert turn.status == TURN_STATUS_REDACTED
        assert turn.assistant_answer is None
        assert source.state == SOURCE_STATE_DELETING

        monkeypatch.setattr(
            sources_module,
            "cleanup_index_before_source_delete",
            lambda *_a, **_k: None,
        )
        calls = {"n": 0}

        class _BoomStorage:
            def delete_source_files(self, *_args: Any, **_kwargs: Any) -> None:
                calls["n"] += 1
                if calls["n"] == 1:
                    raise ObjectStorageError("storage unavailable")

        monkeypatch.setattr(sources_module, "storage_from_settings", lambda _settings: _BoomStorage())
        worker = SourceDeleteWorker(settings)
        assert worker.run_once(db) is True
        failed = db.scalar(
            select(SourcePreparationOperation).where(
                SourcePreparationOperation.source_document_id == source.id,
                SourcePreparationOperation.operation_type == SOURCE_PREP_OPERATION_DELETE,
            )
        )
        assert failed is not None
        assert failed.status == SOURCE_PREP_STATUS_FAILED
        db.refresh(turn)
        db.refresh(source)
        token = db.scalar(select(ComposerRefToken).where(ComposerRefToken.token_hash == _token_hash(raw)))
        assert turn.status == TURN_STATUS_REDACTED
        assert turn.assistant_answer is None
        assert source.state == SOURCE_STATE_DELETING
        assert token is not None and token.expires_at <= utc_now() + timedelta(seconds=1)
        dto = safe_turn_dto(db, settings, turn)
        assert dto["assistantAnswer"] is None
        assert "SENTINEL_ANSWER_MUST_STAY_REDACTED" not in str(dto)

        # Admin re-queues after FAILED (not active). Second worker pass succeeds.
        db.refresh(source)
        enqueue_delete_source(
            db,
            domain_id=domain.id,
            source_id=source.id,
            expected_version=source.version,
            requested_by_user=admin,
            audit_context=None,
        )
        assert worker.run_once(db) is True
        assert db.get(SourceDocument, source.id) is None
        db.refresh(turn)
        assert turn.status == TURN_STATUS_REDACTED
        assert turn.assistant_answer is None
        assert turn.user_message == "Retained question."
    finally:
        db.close()


def test_g3_composer_consume_after_delete_driven_expiry_is_unavailable(tmp_path: Path) -> None:
    """M-09 ∩ A-09 — consume after delete fence fails closed without echoing token/id."""
    db = _session(tmp_path)
    try:
        admin, domain, source = _seed_domain_source(db)
        owner, conversation, _, settings = _owner_conversation(db)
        raw = f"ce-p12-03-consume-{uuid4().hex}"
        now = utc_now()
        db.add(
            ComposerRefToken(
                token_hash=_token_hash(raw),
                owner_user_id=owner.id,
                ref_kind=COMPOSER_REF_KIND_SOURCE,
                target_id=source.id,
                domain_id=domain.id,
                safe_label="Source chip",
                expires_at=now + timedelta(hours=1),
                created_at=now,
            )
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
        with pytest.raises(ComposerRefError) as validate_error:
            validate_composer_ref_tokens(
                db,
                settings=settings,
                owner=owner,
                conversation_id=conversation.id,
                domain_id=domain.id,
                tokens=[raw],
            )
        assert validate_error.value.code == "composer_ref_unavailable"
        assert raw not in validate_error.value.message
        assert source.id not in validate_error.value.message

        with pytest.raises(ComposerRefError) as consume_error:
            consume_composer_ref_tokens(db, owner=owner, tokens=(raw,))
        assert consume_error.value.code == "composer_ref_unavailable"
        assert raw not in consume_error.value.message
    finally:
        db.close()


def test_g4_all_adversarial_hits_map_empty_then_grounded_refusal(tmp_path: Path) -> None:
    """M-03 — only unmapped/wrong-domain hits → empty Evidence → no synthesis."""
    source = SourceDocument(
        id="source-adv",
        public_ref="docref-source-adv",
        domain_id="domain-retrieval",
        original_filename="manual.pdf",
        content_type="application/pdf",
        original_sha256="b" * 64,
        original_size_bytes=128,
        original_object_key="obj/source-adv",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
        index_state=SOURCE_INDEX_STATE_READY,
        index_generation=1,
        index_request_id="source-adv-1-request",
        index_content_hash="c" * 64,
    )
    scope = FrozenRetrievalScope(
        domain_id=source.domain_id,
        control_generation=1,
        runtime_instance_id="runtime-1",
        sources=(
            FrozenSourceIdentity(
                source_document_id=source.id,
                preparation_generation=source.preparation_generation,
                index_generation=source.index_generation,
                index_request_id=source.index_request_id or "",
                index_content_hash=source.index_content_hash or "",
                original_sha256=source.original_sha256,
            ),
        ),
    )
    mapping_db = _MappingSession([])
    mapped = map_retrieval_hits_to_internal_evidence(
        mapping_db,  # type: ignore[arg-type]
        hits=[
            ScopedRetrievalCandidate(text="[CE_BLOCK id=block-legacy order=1]\nlegacy"),
            ScopedRetrievalCandidate(
                text=(
                    f"[CE_BLOCK schema=2 source_id=wrong-source source_sha256={source.original_sha256} "
                    "block_id=block-1 order=1]\nwrong source"
                )
            ),
            ScopedRetrievalCandidate(
                text=(
                    f"[CE_BLOCK schema=2 source_id={source.id} source_sha256={'e' * 64} "
                    "block_id=block-1 order=1]\nwrong hash"
                )
            ),
        ],
        frozen_scope=scope,
    )
    assert mapped == []

    settings = _settings(tmp_path)
    db = _session(tmp_path)
    try:
        owner = User(username="orch-adv@example.test", password_hash="synthetic")
        conversation = Conversation(owner=owner, title="Adversarial hits")
        now = utc_now()
        turn = ConversationTurn(
            conversation=conversation,
            client_request_id="adv-unmapped-only",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id="domain-retrieval",
            status=TURN_STATUS_RUNNING,
            user_message="Where is the relief valve?",
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(turn)
        db.commit()
        db.refresh(turn)
        retrieval = CountingRetrievalPort([])  # post-mapping empty (all hits discarded)
        synthesis = ScriptedSynthesis()
        start = TurnStartResult(
            turn=turn,
            replay=False,
            synthesis=TrustedModelRuntimeConfig(
                profile_id="openai-synthesis-default",
                provider_kind="openai",
                model_name="gpt-4.1-mini",
                credential="sk-test",
            ),
            prior_user_questions=(),
            request_id="req-adv-1",
        )
        list(
            TurnOrchestrator(synthesis_adapter=synthesis, retrieval_port=retrieval).stream_turn(
                db, settings=settings, start=start
            )
        )
        db.refresh(turn)
        assert turn.status == "completed" or turn.status == TURN_STATUS_COMPLETED
        assert turn.stop_reason == TURN_STOP_REASON_NO_GROUNDED_CONTEXT
        assert turn.assistant_answer is None
        assert retrieval.calls == 1
        assert synthesis.grounded_calls == 0
        assert synthesis.direct_calls == 0
        payload = _completed_payload(db, turn)
        assert payload["stopReason"] == TURN_STOP_REASON_NO_GROUNDED_CONTEXT
    finally:
        db.close()


def test_g5_post_domain_delete_new_domain_rag_fails_closed(tmp_path: Path) -> None:
    """A-04 / A-08 / A-09 — after domain delete fence, new domain_rag cannot start."""
    db = _session(tmp_path)
    try:
        admin, domain, _source = _seed_domain_source(db, domain_state=DOMAIN_STATE_RUNNING)
        owner, conversation, auth_session, settings = _owner_conversation(db)
        db.commit()
        request_id = f"post-delete-{uuid4().hex}"
        enqueue_delete_domain(
            db,
            domain_id=domain.id,
            expected_version=domain.version,
            requested_by_user=admin,
            audit_context=None,
        )
        db.refresh(domain)
        assert domain.state == DOMAIN_STATE_DELETING

        with pytest.raises(ChatTurnError) as error:
            start_or_replay_turn(
                db,
                settings=settings,
                owner=owner,
                auth_session=auth_session,
                conversation_id=conversation.public_ref,
                client_request_id=request_id,
                message="What does the manual say about relief valves?",
                domain_id=domain.id,
                composer_ref_tokens=[],
            )
        assert error.value.status_code == 409
        assert error.value.code == "domain_state_conflict"
        created = db.scalar(
            select(ConversationTurn).where(ConversationTurn.client_request_id == request_id)
        )
        assert created is None
    finally:
        db.close()


def test_g6_enqueue_delete_public_projection_omits_answer_sentinel(tmp_path: Path) -> None:
    """FR-09 / M-11 — full enqueue_delete_source path omits planted answer from public DTO."""
    db = _session(tmp_path)
    settings = _settings(tmp_path)
    try:
        admin, domain, source = _seed_domain_source(db)
        _, conversation, _, _ = _owner_conversation(db)
        now = utc_now()
        turn = ConversationTurn(
            conversation_id=conversation.id,
            client_request_id=f"privacy-{uuid4().hex}",
            route=TURN_ROUTE_DOMAIN_RAG,
            domain_id=domain.id,
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
                source_label="manual.pdf",
                excerpt="SECRET_EXCERPT_SENTINEL",
                source_document_id=source.id,
                source_block_id="block-privacy",
            )
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
        dto = safe_turn_dto(db, settings, turn)
        blob = str(dto)
        assert turn.status == TURN_STATUS_REDACTED
        assert "SECRET_ANSWER_SENTINEL" not in blob
        assert dto["userMessage"] == "SECRET_PROMPT_SENTINEL"
        assert dto["assistantAnswer"] is None
    finally:
        db.close()
