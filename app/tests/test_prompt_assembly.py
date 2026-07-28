"""P11-03 U2: private PromptAssemblyService coverage (M-09 / FR-07)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.db import Base
from context_engine.models import (
    COMPOSER_REF_KIND_EVIDENCE,
    COMPOSER_REF_KIND_SOURCE,
    COMPOSER_REF_KIND_TEMPLATE,
    DOMAIN_STATE_RUNNING,
    PROMPT_TEMPLATE_STATE_APPROVED,
    ROLE_MEMBER,
    SOURCE_STATE_PREPARED,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_STATUS_COMPLETED,
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    Domain,
    ModelProfile,
    PromptTemplate,
    ProviderConfig,
    SourceBlock,
    SourceDocument,
    User,
)
from context_engine.services.composer_refs import ValidatedComposerRef
from context_engine.services.prompt_assembly import (
    SOURCE_CONTEXT_CAP_CHARS,
    TEMPLATE_BODY_CAP_CHARS,
    TOTAL_ASSEMBLY_CAP_CHARS,
    PromptAssemblyService,
)

SEED_CLOCK = datetime(2026, 7, 17, 12, 0, 0)


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'prompt-assembly.db'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_parents(db: Session) -> dict[str, str]:
    db.add(
        ProviderConfig(
            provider_kind="openai",
            display_name="OpenAI",
            requires_credentials=True,
            created_at=SEED_CLOCK,
            updated_at=SEED_CLOCK,
        )
    )
    embed_id = str(uuid4())
    db.add(
        ModelProfile(
            id=embed_id,
            name="embed_384_v1",
            profile_kind="embedding",
            provider_kind="openai",
            model_name="text-embedding-3-small",
            vector_dimensions=384,
            created_at=SEED_CLOCK,
            updated_at=SEED_CLOCK,
        )
    )
    domain_id = "domain_assembly"
    db.add(
        Domain(
            id=domain_id,
            display_name="Assembly domain",
            state=DOMAIN_STATE_RUNNING,
            embedding_profile_id=embed_id,
            created_at=SEED_CLOCK,
            updated_at=SEED_CLOCK,
        )
    )
    owner = User(
        id=str(uuid4()),
        username="assembly.mina",
        password_hash="synthetic",
        role=ROLE_MEMBER,
        created_at=SEED_CLOCK,
        updated_at=SEED_CLOCK,
        password_changed_at=SEED_CLOCK,
    )
    db.add(owner)
    source_id = str(uuid4())
    db.add(
        SourceDocument(
            id=source_id,
            public_ref="doc_assembly_pump",
            domain_id=domain_id,
            original_filename="pump.pdf",
            content_type="application/pdf",
            original_sha256="a" * 64,
            original_size_bytes=128,
            original_object_key="source/assembly",
            state=SOURCE_STATE_PREPARED,
            parser_kind="docling",
            created_at=SEED_CLOCK,
            updated_at=SEED_CLOCK,
        )
    )
    db.add(
        SourceBlock(
            id=str(uuid4()),
            source_document_id=source_id,
            domain_id=domain_id,
            source_order=1,
            kind="text",
            canonical_markdown="Block one relief valve context.",
        )
    )
    db.add(
        SourceBlock(
            id=str(uuid4()),
            source_document_id=source_id,
            domain_id=domain_id,
            source_order=2,
            kind="text",
            canonical_markdown="Block two pump downstream notes.",
        )
    )
    template_id = str(uuid4())
    db.add(
        PromptTemplate(
            id=template_id,
            name="tpl_assembly_safety",
            description="Approved template",
            body="Template body for governed assembly.",
            state=PROMPT_TEMPLATE_STATE_APPROVED,
            created_at=SEED_CLOCK,
            updated_at=SEED_CLOCK,
        )
    )
    conversation = Conversation(
        id=str(uuid4()),
        public_ref="conv_assembly",
        owner_user_id=owner.id,
        title="Assembly",
        version=1,
        created_at=SEED_CLOCK,
        updated_at=SEED_CLOCK,
    )
    db.add(conversation)
    db.flush()
    turn = ConversationTurn(
        id=str(uuid4()),
        public_ref="turn_assembly",
        conversation_id=conversation.id,
        client_request_id="client_assembly_001",
        route=TURN_ROUTE_DOMAIN_RAG,
        domain_id=domain_id,
        status=TURN_STATUS_COMPLETED,
        user_message="Where is the relief valve?",
        assistant_answer="Downstream.",
        created_at=SEED_CLOCK,
        started_at=SEED_CLOCK,
        completed_at=SEED_CLOCK,
        updated_at=SEED_CLOCK,
    )
    db.add(turn)
    db.flush()
    evidence_id = str(uuid4())
    db.add(
        ConversationTurnEvidenceRef(
            id=evidence_id,
            public_ref="ev_assembly_valve",
            turn_id=turn.id,
            evidence_order=1,
            source_document_id=source_id,
            source_block_id="block_1",
            citation_label="1",
            source_label="Pump",
            excerpt="Evidence excerpt: relief valve downstream.",
            created_at=SEED_CLOCK,
        )
    )
    db.commit()
    return {
        "domain_id": domain_id,
        "source_id": source_id,
        "template_id": template_id,
        "evidence_id": evidence_id,
        "turn_id": turn.id,
    }


def test_assemble_template_source_evidence_kinds(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        ids = _seed_parents(db)
        result = PromptAssemblyService(db).assemble(
            (
                ValidatedComposerRef(
                    order=1,
                    kind=COMPOSER_REF_KIND_TEMPLATE,
                    label="Safety",
                    description=None,
                    prompt_template_id=ids["template_id"],
                ),
                ValidatedComposerRef(
                    order=2,
                    kind=COMPOSER_REF_KIND_SOURCE,
                    label="Pump",
                    description=None,
                    source_document_id=ids["source_id"],
                ),
                ValidatedComposerRef(
                    order=3,
                    kind=COMPOSER_REF_KIND_EVIDENCE,
                    label="Valve",
                    description=None,
                    evidence_ref_id=ids["evidence_id"],
                ),
            )
        )
        assert not result.is_empty
        assert [snippet.kind for snippet in result.snippets] == [
            COMPOSER_REF_KIND_TEMPLATE,
            COMPOSER_REF_KIND_SOURCE,
            COMPOSER_REF_KIND_EVIDENCE,
        ]
        assert "Template body" in result.snippets[0].body
        assert "Block one" in result.snippets[1].body
        assert "Block two" in result.snippets[1].body
        assert "Evidence excerpt" in result.snippets[2].body
        assert result.total_chars == sum(len(snippet.body) for snippet in result.snippets)
    finally:
        db.close()


def test_assemble_skips_redacted_evidence(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        ids = _seed_parents(db)
        evidence = db.get(ConversationTurnEvidenceRef, ids["evidence_id"])
        assert evidence is not None
        evidence.redacted_at = SEED_CLOCK
        evidence.citation_label = None
        evidence.source_label = None
        evidence.excerpt = None
        db.commit()

        result = PromptAssemblyService(db).assemble(
            (
                ValidatedComposerRef(
                    order=1,
                    kind=COMPOSER_REF_KIND_EVIDENCE,
                    label="Valve",
                    description=None,
                    evidence_ref_id=ids["evidence_id"],
                ),
            )
        )
        assert result.is_empty
    finally:
        db.close()


def test_assemble_truncates_source_and_total_caps(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        ids = _seed_parents(db)
        # Schema caps template bodies at 2000 (= TEMPLATE_BODY_CAP_CHARS); prove source/total caps.
        assert TEMPLATE_BODY_CAP_CHARS == 2000
        huge_source = "S" * (SOURCE_CONTEXT_CAP_CHARS + 20)
        source = db.get(SourceDocument, ids["source_id"])
        assert source is not None
        for block in db.scalars(
            select(SourceBlock).where(SourceBlock.source_document_id == source.id)
        ):
            block.canonical_markdown = huge_source
        db.commit()

        single = PromptAssemblyService(db).assemble(
            (
                ValidatedComposerRef(
                    order=1,
                    kind=COMPOSER_REF_KIND_SOURCE,
                    label="Pump",
                    description=None,
                    source_document_id=ids["source_id"],
                ),
            )
        )
        assert len(single.snippets[0].body) <= SOURCE_CONTEXT_CAP_CHARS

        multi = PromptAssemblyService(db).assemble(
            tuple(
                ValidatedComposerRef(
                    order=index,
                    kind=COMPOSER_REF_KIND_SOURCE,
                    label=f"Pump {index}",
                    description=None,
                    source_document_id=ids["source_id"],
                )
                for index in range(1, 12)
            )
        )
        assert multi.total_chars <= TOTAL_ASSEMBLY_CAP_CHARS
    finally:
        db.close()


def test_assemble_bodies_not_persisted_on_turn_columns(tmp_path: Path) -> None:
    """Assembly is ephemeral — durable turn columns must not store snippet bodies."""
    db = _session(tmp_path)
    try:
        ids = _seed_parents(db)
        marker = "UNIQUE_ASSEMBLY_MARKER_NOT_FOR_PERSIST"
        template = db.get(PromptTemplate, ids["template_id"])
        assert template is not None
        template.body = marker
        db.commit()

        result = PromptAssemblyService(db).assemble(
            (
                ValidatedComposerRef(
                    order=1,
                    kind=COMPOSER_REF_KIND_TEMPLATE,
                    label="Safety",
                    description=None,
                    prompt_template_id=ids["template_id"],
                ),
            )
        )
        assert marker in result.snippets[0].body

        turn = db.get(ConversationTurn, ids["turn_id"])
        assert turn is not None
        dumped = " ".join(
            str(value)
            for value in (
                turn.assistant_answer,
                turn.user_message,
                turn.safe_error_code,
                turn.safe_error_message,
                turn.stop_reason,
            )
            if value is not None
        )
        assert marker not in dumped
        # Durable events are not written by assemble(); worker/SSE non-persist is covered by
        # chat orchestration privacy patterns + DRIFT-26 HTTP suites (no Approved-context leak).
        from context_engine.models import ConversationTurnEvent

        event_payloads = [
            str(event.payload)
            for event in db.scalars(
                select(ConversationTurnEvent).where(ConversationTurnEvent.turn_id == turn.id)
            )
        ]
        assert all(marker not in payload for payload in event_payloads)
        assert all("Approved context" not in payload for payload in event_payloads)
    finally:
        db.close()
