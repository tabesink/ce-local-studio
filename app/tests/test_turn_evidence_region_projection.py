"""P4-05 U3b — turn detail and SSE evidence anchors share the location projector."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from context_engine.api.catalog_schemas import EvidenceItemDto
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    DOMAIN_STATE_STOPPED,
    SOURCE_BLOCK_KIND_FIGURE,
    SOURCE_BLOCK_KIND_TEXT,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_STATUS_COMPLETED,
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    Domain,
    ModelProfile,
    ProviderConfig,
    SourceBlock,
    SourceDocument,
    SourceImage,
    User,
)
from context_engine.services.chat_turns import _public_evidence_items, safe_turn_dto
from context_engine.services.documents import get_evidence_location
from context_engine.services import documents as documents_module


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'turn-region.db'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_graph(
    db: Session,
    *,
    page_start: int | None = 18,
    region: tuple[float, float, float, float] | None = (0.12, 0.24, 0.66, 0.41),
    section_path: str | None = '["4.2 Relief valve"]',
    kind: str = SOURCE_BLOCK_KIND_FIGURE,
    image_page: int | None = None,
) -> tuple[User, SourceDocument, SourceBlock, ConversationTurn, ConversationTurnEvidenceRef]:
    owner = User(username="mina-region@example.test", password_hash="synthetic")
    provider = ProviderConfig(
        provider_kind="openai",
        display_name="OpenAI",
        requires_credentials=True,
    )
    profile = ModelProfile(
        id="embed-region",
        name="Embedding",
        profile_kind="embedding",
        provider_kind="openai",
        model_name="text-embedding-3-small",
        vector_dimensions=1536,
    )
    domain = Domain(
        id="domain-manuals-region",
        display_name="Manuals",
        state=DOMAIN_STATE_STOPPED,
        embedding_profile_id=profile.id,
    )
    source = SourceDocument(
        id=str(uuid4()),
        public_ref="doc_" + "r" * 32,
        domain_id=domain.id,
        original_filename="pump-manual.pdf",
        content_type="application/pdf",
        original_sha256="c" * 64,
        original_size_bytes=2048,
        original_object_key="source/doc_pump_region_private",
        state="prepared",
        parser_kind="docling",
    )
    region_x = region_y = region_width = region_height = None
    if region is not None:
        region_x, region_y, region_width, region_height = region
    block = SourceBlock(
        id="block_valve_figure_region",
        source_document_id=source.id,
        domain_id=domain.id,
        source_order=1,
        kind=kind,
        canonical_markdown="Figure 4 private body",
        page_start=page_start,
        page_end=page_start,
        section_path=section_path,
        region_x=region_x,
        region_y=region_y,
        region_width=region_width,
        region_height=region_height,
        created_at=utc_now(),
    )
    conversation = Conversation(owner=owner, title="Region turn")
    turn = ConversationTurn(
        conversation=conversation,
        client_request_id="client_region_001",
        route=TURN_ROUTE_DOMAIN_RAG,
        domain_id=domain.id,
        status=TURN_STATUS_COMPLETED,
        user_message="Where is the relief valve?",
        assistant_answer="See [1].",
        created_at=utc_now(),
        updated_at=utc_now(),
        completed_at=utc_now(),
    )
    evidence = ConversationTurnEvidenceRef(
        public_ref="ev_" + "f" * 32,
        turn=turn,
        evidence_order=1,
        source_document_id=source.id,
        source_block_id=block.id,
        citation_label="[1]",
        source_label="pump-manual.pdf",
        excerpt="relief valve",
        created_at=utc_now(),
    )
    db.add_all([owner, provider, profile, domain, source, block, conversation, turn, evidence])
    if image_page is not None:
        db.add(
            SourceImage(
                source_document_id=source.id,
                source_block_id=block.id,
                object_key=f"source/img-{block.id}",
                content_hash="d" * 64,
                mime_type="image/png",
                page_number=image_page,
                created_at=utc_now(),
            )
        )
    db.commit()
    return owner, source, block, turn, evidence


def test_turn_and_sse_evidence_match_location_region(tmp_path: Path, monkeypatch) -> None:
    # M-04 / AE2: shared projector for turn detail, SSE evidence.delta, and location.
    db = _session(tmp_path)
    try:
        owner, source, block, turn, evidence = _seed_graph(db)
        turn = db.scalar(
            select(ConversationTurn)
            .options(selectinload(ConversationTurn.evidence_refs))
            .where(ConversationTurn.id == turn.id)
        )
        assert turn is not None
        settings = Settings(
            database_url=f"sqlite+pysqlite:///{tmp_path / 'turn-region.db'}",
            testing=True,
            source_storage_root=str(tmp_path / "source-root"),
        )
        monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: True)
        monkeypatch.setattr(documents_module, "document_page_count", lambda *_a, **_k: 24)

        location = get_evidence_location(
            db,
            settings,
            owner_user_id=owner.id,
            evidence_ref=evidence.public_ref,
        )
        dto = safe_turn_dto(db, settings, turn)
        sse_items = _public_evidence_items(db, turn)

        assert len(dto["evidence"]) == 1
        assert len(sse_items) == 1
        assert dto["evidence"][0]["anchor"] == location["anchor"]
        assert sse_items[0]["anchor"] == location["anchor"]
        assert location["anchor"] == {
            "pageNumber": 18,
            "region": {"x": 0.12, "y": 0.24, "width": 0.66, "height": 0.41},
            "sectionLabel": "4.2 Relief valve",
            "fallback": "region",
        }
        EvidenceItemDto.model_validate(dto["evidence"][0])
        EvidenceItemDto.model_validate(sse_items[0])

        rendered = str(dto) + str(sse_items) + str(location)
        for forbidden in (
            block.id,
            source.id,
            source.original_object_key,
            "Figure 4 private body",
            "region_x",
        ):
            assert forbidden not in rendered
    finally:
        db.close()


def test_turn_evidence_page_join_without_fabricated_page_one(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        _owner, source, block, turn, _evidence = _seed_graph(
            db,
            page_start=None,
            image_page=21,
            section_path=None,
        )
        turn = db.scalar(
            select(ConversationTurn)
            .options(selectinload(ConversationTurn.evidence_refs))
            .where(ConversationTurn.id == turn.id)
        )
        assert turn is not None
        settings = Settings(
            database_url=f"sqlite+pysqlite:///{tmp_path / 'turn-region.db'}",
            testing=True,
        )
        dto = safe_turn_dto(db, settings, turn)
        sse_items = _public_evidence_items(db, turn)
        assert dto["evidence"][0]["anchor"]["pageNumber"] == 21
        assert sse_items[0]["anchor"]["pageNumber"] == 21
        assert dto["evidence"][0]["anchor"]["fallback"] == "region"
        assert "pageNumber': 1" not in str(dto["evidence"])
        assert source.original_object_key not in str(sse_items)
        assert block.id not in str(sse_items)
    finally:
        db.close()


def test_text_evidence_keeps_null_region_and_section_fallback(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        _owner, _source, _block, turn, _evidence = _seed_graph(
            db,
            kind=SOURCE_BLOCK_KIND_TEXT,
            region=None,
            section_path="2.1 Lockout",
        )
        turn = db.scalar(
            select(ConversationTurn)
            .options(selectinload(ConversationTurn.evidence_refs))
            .where(ConversationTurn.id == turn.id)
        )
        assert turn is not None
        settings = Settings(
            database_url=f"sqlite+pysqlite:///{tmp_path / 'turn-region.db'}",
            testing=True,
        )
        item = safe_turn_dto(db, settings, turn)["evidence"][0]
        assert item["anchor"]["region"] is None
        assert item["anchor"]["fallback"] == "section"
        assert item["anchor"]["sectionLabel"] == "2.1 Lockout"
        assert item["kind"] == "text"
    finally:
        db.close()


def test_unprovable_page_omits_evidence_instead_of_page_one(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        _owner, _source, _block, turn, _evidence = _seed_graph(
            db,
            page_start=None,
            image_page=None,
            region=None,
            section_path=None,
        )
        turn = db.scalar(
            select(ConversationTurn)
            .options(selectinload(ConversationTurn.evidence_refs))
            .where(ConversationTurn.id == turn.id)
        )
        assert turn is not None
        settings = Settings(
            database_url=f"sqlite+pysqlite:///{tmp_path / 'turn-region.db'}",
            testing=True,
        )
        assert safe_turn_dto(db, settings, turn)["evidence"] == []
        assert _public_evidence_items(db, turn) == []
    finally:
        db.close()
