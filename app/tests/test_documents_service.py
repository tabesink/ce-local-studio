from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DbSession

from context_engine.api.catalog_schemas import DocumentSummaryDto, EvidenceLocationResponseDto
from context_engine.config import Settings
from context_engine.db import Base
from context_engine.models import (
    SOURCE_BLOCK_KIND_FIGURE,
    SOURCE_BLOCK_KIND_TEXT,
    SOURCE_INDEX_STATE_READY,
    SOURCE_STATE_DELETING,
    SOURCE_STATE_PREPARED,
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_COMPLETED,
    TURN_STATUS_REDACTED,
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    Domain,
    ModelProfile,
    ProviderConfig,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.evidence import (
    project_persisted_evidence_anchor,
    safe_section_label,
)
from context_engine.services import documents as documents_module
from context_engine.services.documents import (
    DocumentError,
    content_disposition_for_label,
    get_document_content,
    get_evidence_location,
    list_documents,
    parse_byte_range,
    preview_etag,
    preview_kind_for_source,
    safe_document_summary,
)
from context_engine.services.indexing import compute_index_request_id
from context_engine.services.sources import SourceStorage, new_document_public_ref


class _ScalarSession:
    def __init__(self, page_count: int | None = 3) -> None:
        self._page_count = page_count

    def scalar(self, _statement):  # noqa: ANN001
        return self._page_count


def _domain() -> Domain:
    return Domain(
        id="domain-manuals",
        display_name="Equipment Manuals",
        state="running",
        embedding_profile_id="emb-1",
        control_generation=1,
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 0, 0),
        version=1,
    )


def _source(*, content_type: str = "application/pdf") -> SourceDocument:
    return SourceDocument(
        id=str(uuid4()),
        public_ref=new_document_public_ref(),
        domain_id="domain-manuals",
        original_filename="pump-service-manual.pdf",
        content_type=content_type,
        original_sha256="a" * 64,
        original_size_bytes=2048,
        original_object_key="obj_testkey0123456789",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
        index_state=SOURCE_INDEX_STATE_READY,
        index_generation=1,
        version=2,
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 5, 0),
    )


def test_safe_document_summary_matches_closed_dto_without_private_fields() -> None:
    source = _source()
    projection = safe_document_summary(_ScalarSession(24), source, _domain(), query_eligible=True)

    dto = DocumentSummaryDto.model_validate(projection)
    assert dto.ref == source.public_ref
    assert dto.label == "pump-service-manual.pdf"
    assert dto.content_type == "application/pdf"
    assert dto.preview_kind == "pdf"
    assert dto.page_count == 24
    assert dto.domain.id == "domain-manuals"
    assert dto.domain.query_eligible is True

    rendered = str(projection)
    for forbidden in (
        source.id,
        source.original_sha256,
        source.original_object_key,
        "originalSha256",
        "originalObjectKey",
        "obj_",
        "a" * 64,
    ):
        assert forbidden not in rendered


def test_non_pdf_preview_kind_unavailable_keeps_pdf_content_type_literal() -> None:
    source = _source(content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    source.original_filename = "notes.docx"
    assert preview_kind_for_source(source) == "unavailable"
    projection = safe_document_summary(_ScalarSession(None), source, _domain(), query_eligible=True)
    dto = DocumentSummaryDto.model_validate(projection)
    assert dto.preview_kind == "unavailable"
    assert dto.content_type == "application/pdf"
    assert dto.page_count is None


def test_preview_etag_is_strong_opaque_and_stable() -> None:
    source = _source()
    etag = preview_etag(source)
    assert etag.startswith('"') and etag.endswith('"')
    assert source.original_sha256 not in etag
    assert source.original_object_key not in etag
    assert preview_etag(source) == etag


def test_content_disposition_sanitizes_control_characters() -> None:
    value = content_disposition_for_label('pump\nmanual"x.pdf')
    assert value.startswith("inline; filename=")
    assert "\n" not in value
    assert '\\"' in value or '"' in value


@pytest.mark.parametrize(
    ("header", "total", "expected"),
    [
        (None, 100, None),
        ("bytes=0-9", 100, (0, 9)),
        ("bytes=50-", 100, (50, 99)),
        ("bytes=-10", 100, (90, 99)),
    ],
)
def test_parse_byte_range_accepts_single_ranges(
    header: str | None,
    total: int,
    expected: tuple[int, int] | None,
) -> None:
    assert parse_byte_range(header, total_size=total) == expected


@pytest.mark.parametrize(
    "header",
    [
        "bytes=0-9,10-19",
        "bytes=200-300",
        "bytes=",
        "units=0-9",
    ],
)
def test_parse_byte_range_rejects_unsatisfiable_or_multi(header: str) -> None:
    with pytest.raises(DocumentError) as exc_info:
        parse_byte_range(header, total_size=100)
    assert exc_info.value.status_code == 416
    assert exc_info.value.code == "range_not_satisfiable"
    assert exc_info.value.headers["Content-Range"] == "bytes */100"


def test_evidence_location_response_dto_accepts_contract_shape() -> None:
    payload = {
        "evidence": {"id": "ev_" + "a" * 32, "citationLabel": "[1]", "kind": "figure"},
        "document": {
            "ref": "doc_" + "b" * 32,
            "label": "pump-service-manual.pdf",
            "previewKind": "pdf",
            "pageCount": 24,
        },
        "anchor": {
            "pageNumber": 18,
            "region": None,
            "sectionLabel": "4.2 Relief valve",
            "fallback": "page",
        },
    }
    dto = EvidenceLocationResponseDto.model_validate(payload)
    assert dto.anchor.page_number == 18
    assert dto.document.preview_kind == "pdf"


def test_source_block_fixture_shape_for_location_anchor() -> None:
    block = SourceBlock(
        id=str(uuid4()),
        source_document_id=str(uuid4()),
        domain_id="domain-manuals",
        source_order=1,
        kind=SOURCE_BLOCK_KIND_TEXT,
        canonical_markdown="private",
        page_start=18,
        page_end=18,
        section_path="4.2 Relief valve",
        created_at=datetime(2026, 7, 25, 12, 0, 0),
    )
    assert block.page_start == 18


def test_get_document_content_serves_pdf_ranges_from_object_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = b"%PDF-1.4-" + (b"x" * 40)
    storage = SourceStorage(str(tmp_path / "source-root"))
    key = storage.put_original(pdf_bytes, content_type="application/pdf")
    source = _source()
    source.original_object_key = key
    source.original_size_bytes = len(pdf_bytes)
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'docs-content.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(
        documents_module,
        "_resolve_library_source",
        lambda *_args, **_kwargs: (source, _domain()),
    )

    full = get_document_content(_ScalarSession(), settings, source.public_ref)
    assert full.status_code == 200
    assert full.body == pdf_bytes
    assert full.etag == preview_etag(source)

    partial = get_document_content(
        _ScalarSession(),
        settings,
        source.public_ref,
        range_header="bytes=0-9",
    )
    assert partial.status_code == 206
    assert partial.body == pdf_bytes[:10]
    assert partial.content_range == f"bytes 0-9/{len(pdf_bytes)}"

    mismatched = get_document_content(
        _ScalarSession(),
        settings,
        source.public_ref,
        range_header="bytes=0-9",
        if_range='"stale-etag"',
    )
    assert mismatched.status_code == 200
    assert mismatched.body == pdf_bytes

    with pytest.raises(DocumentError) as exc_info:
        get_document_content(
            _ScalarSession(),
            settings,
            source.public_ref,
            range_header=f"bytes={len(pdf_bytes)}-{len(pdf_bytes) + 10}",
        )
    assert exc_info.value.code == "range_not_satisfiable"


def test_get_document_content_missing_object_is_safe_503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AE3: missing referenced object fails closed without leaking keys."""
    source = _source()
    source.original_object_key = "obj_missing_referenced_key_zzzz"
    source.original_size_bytes = 12
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'docs-missing.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(
        documents_module,
        "_resolve_library_source",
        lambda *_args, **_kwargs: (source, _domain()),
    )
    with pytest.raises(DocumentError) as exc_info:
        get_document_content(_ScalarSession(), settings, source.public_ref)
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "document_content_unavailable"
    body = f"{exc_info.value.code} {exc_info.value.message}"
    assert "obj_missing" not in body
    assert source.original_object_key not in body


def test_get_document_content_rejects_non_pdf_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(content_type="text/markdown")
    source.original_filename = "notes.md"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'docs-nonpdf.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(
        documents_module,
        "_resolve_library_source",
        lambda *_args, **_kwargs: (source, _domain()),
    )
    with pytest.raises(DocumentError) as exc_info:
        get_document_content(_ScalarSession(), settings, source.public_ref)
    assert exc_info.value.code == "document_preview_unavailable"


class _ScalarsResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return list(self._values)


class _LocationSession:
    """Minimal session stub that exercises get_evidence_location ownership fences."""

    def __init__(
        self,
        *,
        evidence: ConversationTurnEvidenceRef | None,
        turn: ConversationTurn | None = None,
        conversation: Conversation | None = None,
        source: SourceDocument | None = None,
        block: SourceBlock | None = None,
        domain: Domain | None = None,
        page_count: int | None = 18,
        image_pages: list[int] | None = None,
    ) -> None:
        self._evidence = evidence
        self._page_count = page_count
        self._image_pages = list(image_pages or [])
        self._by_key: dict[tuple[type, str], object] = {}
        for entity in (turn, conversation, source, block, domain):
            if entity is not None:
                self._by_key[(type(entity), entity.id)] = entity

    def scalar(self, statement):  # noqa: ANN001
        entity = None
        try:
            entity = statement.column_descriptions[0].get("entity")
        except Exception:
            entity = None
        if entity is ConversationTurnEvidenceRef:
            return self._evidence
        return self._page_count

    def scalars(self, statement):  # noqa: ANN001
        return _ScalarsResult(self._image_pages)

    def get(self, model, key):  # noqa: ANN001
        return self._by_key.get((model, key))


def _location_graph(
    *,
    owner_user_id: str = "user-owner",
    kind: str = SOURCE_BLOCK_KIND_TEXT,
    page_start: int | None = 18,
    section_path: str | None = "4.2 Relief valve",
    region: tuple[float, float, float, float] | None = None,
):
    domain = _domain()
    source = _source()
    region_x = region_y = region_width = region_height = None
    if region is not None:
        region_x, region_y, region_width, region_height = region
    block = SourceBlock(
        id=str(uuid4()),
        source_document_id=source.id,
        domain_id=domain.id,
        source_order=1,
        kind=kind,
        canonical_markdown="private body",
        page_start=page_start,
        page_end=page_start,
        section_path=section_path,
        region_x=region_x,
        region_y=region_y,
        region_width=region_width,
        region_height=region_height,
        created_at=datetime(2026, 7, 25, 12, 0, 0),
    )
    conversation = Conversation(
        id=str(uuid4()),
        public_ref="conv_" + "c" * 32,
        owner_user_id=owner_user_id,
        title="Pump question",
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 0, 0),
    )
    turn = ConversationTurn(
        id=str(uuid4()),
        public_ref="turn_" + "t" * 32,
        conversation_id=conversation.id,
        client_request_id="loc-req-1",
        route=TURN_ROUTE_DIRECT_LLM,
        status=TURN_STATUS_COMPLETED,
        user_message="Where is the relief valve?",
        assistant_answer="See [1].",
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 0, 0),
    )
    evidence = ConversationTurnEvidenceRef(
        id=str(uuid4()),
        public_ref="ev_" + "e" * 32,
        turn_id=turn.id,
        evidence_order=1,
        source_document_id=source.id,
        source_block_id=block.id,
        citation_label="[1]",
        source_label="pump-service-manual.pdf",
        excerpt="relief valve",
        created_at=datetime(2026, 7, 25, 12, 0, 0),
    )
    return domain, source, block, conversation, turn, evidence


def test_get_evidence_location_success_for_owner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    domain, source, block, conversation, turn, evidence = _location_graph()
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'loc-ok.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: True)
    session = _LocationSession(
        evidence=evidence,
        turn=turn,
        conversation=conversation,
        source=source,
        block=block,
        domain=domain,
    )

    payload = get_evidence_location(
        session,
        settings,
        owner_user_id="user-owner",
        evidence_ref=evidence.public_ref,
    )
    dto = EvidenceLocationResponseDto.model_validate(payload)
    assert dto.evidence.id == evidence.public_ref
    assert dto.document.ref == source.public_ref
    assert dto.anchor.page_number == 18
    assert dto.anchor.section_label == "4.2 Relief valve"
    assert dto.anchor.region is None
    assert dto.anchor.fallback == "section"
    assert "private body" not in str(payload)
    assert source.id not in str(payload)
    assert block.id not in str(payload)


def test_get_evidence_location_figure_region_for_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # M-04: seeded figure region projects through authorized location.
    domain, source, block, conversation, turn, evidence = _location_graph(
        kind=SOURCE_BLOCK_KIND_FIGURE,
        section_path='["4.2 Relief valve"]',
        region=(0.12, 0.24, 0.66, 0.41),
    )
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'loc-region.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: True)
    session = _LocationSession(
        evidence=evidence,
        turn=turn,
        conversation=conversation,
        source=source,
        block=block,
        domain=domain,
    )

    payload = get_evidence_location(
        session,
        settings,
        owner_user_id="user-owner",
        evidence_ref=evidence.public_ref,
    )
    dto = EvidenceLocationResponseDto.model_validate(payload)
    assert dto.evidence.kind == "figure"
    assert dto.anchor.page_number == 18
    assert dto.anchor.section_label == "4.2 Relief valve"
    assert dto.anchor.fallback == "region"
    assert dto.anchor.region is not None
    assert dto.anchor.region.model_dump() == {
        "x": 0.12,
        "y": 0.24,
        "width": 0.66,
        "height": 0.41,
    }
    rendered = str(payload)
    for forbidden in (
        block.id,
        source.id,
        source.original_object_key,
        "private body",
        "canonical_markdown",
        "region_x",
    ):
        assert forbidden not in rendered


def test_get_evidence_location_figure_page_join_when_page_start_null(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    domain, source, block, conversation, turn, evidence = _location_graph(
        kind=SOURCE_BLOCK_KIND_FIGURE,
        page_start=None,
        section_path=None,
        region=(0.10, 0.30, 0.80, 0.34),
    )
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'loc-page-join.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: True)
    session = _LocationSession(
        evidence=evidence,
        turn=turn,
        conversation=conversation,
        source=source,
        block=block,
        domain=domain,
        image_pages=[21],
    )

    payload = get_evidence_location(
        session,
        settings,
        owner_user_id="user-owner",
        evidence_ref=evidence.public_ref,
    )
    dto = EvidenceLocationResponseDto.model_validate(payload)
    assert dto.anchor.page_number == 21
    assert dto.anchor.fallback == "region"
    assert dto.anchor.region is not None
    assert dto.anchor.region.x == 0.10


def test_project_persisted_evidence_anchor_and_section_label() -> None:
    block = SourceBlock(
        id=str(uuid4()),
        source_document_id=str(uuid4()),
        domain_id="domain-manuals",
        source_order=1,
        kind=SOURCE_BLOCK_KIND_FIGURE,
        canonical_markdown="private",
        page_start=None,
        page_end=None,
        section_path='["4.2 Relief valve"]',
        region_x=0.12,
        region_y=0.24,
        region_width=0.66,
        region_height=0.41,
        created_at=datetime(2026, 7, 25, 12, 0, 0),
    )
    assert safe_section_label(block.section_path) == "4.2 Relief valve"
    assert project_persisted_evidence_anchor(block, image_pages=set()) is None
    anchor = project_persisted_evidence_anchor(block, image_pages={18})
    assert anchor == {
        "pageNumber": 18,
        "region": {"x": 0.12, "y": 0.24, "width": 0.66, "height": 0.41},
        "fallback": "region",
        "sectionLabel": "4.2 Relief valve",
    }
    # Conflicting linked image pages leave page unprovable (no fabrication).
    assert project_persisted_evidence_anchor(block, image_pages={18, 19}) is None


def test_get_evidence_location_wrong_owner_is_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    domain, source, block, conversation, turn, evidence = _location_graph()
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'loc-owner.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: True)
    session = _LocationSession(
        evidence=evidence,
        turn=turn,
        conversation=conversation,
        source=source,
        block=block,
        domain=domain,
    )
    with pytest.raises(DocumentError) as exc_info:
        get_evidence_location(
            session,
            settings,
            owner_user_id="user-other",
            evidence_ref=evidence.public_ref,
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "evidence_not_found"


def test_get_evidence_location_unknown_ref_is_404(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'loc-missing.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    with pytest.raises(DocumentError) as exc_info:
        get_evidence_location(
            _LocationSession(evidence=None),
            settings,
            owner_user_id="user-owner",
            evidence_ref="ev_" + "z" * 32,
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "evidence_not_found"


@pytest.mark.parametrize(
    ("caller_id", "owner_id"),
    [
        ("user-other", "user-owner"),
        ("user-admin", "user-owner"),
    ],
)
def test_get_evidence_location_c04_stable_404_envelope(
    caller_id: str,
    owner_id: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # C-04: unknown, cross-owner, and admin-on-member share evidence_not_found.
    domain, source, block, conversation, turn, evidence = _location_graph(
        owner_user_id=owner_id,
        kind=SOURCE_BLOCK_KIND_FIGURE,
        region=(0.12, 0.24, 0.66, 0.41),
    )
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / f'loc-c04-{caller_id}.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: True)
    owned = _LocationSession(
        evidence=evidence,
        turn=turn,
        conversation=conversation,
        source=source,
        block=block,
        domain=domain,
    )
    missing = _LocationSession(evidence=None)

    denied_owned = pytest.raises(DocumentError)
    denied_missing = pytest.raises(DocumentError)
    with denied_owned as owned_info:
        get_evidence_location(
            owned,
            settings,
            owner_user_id=caller_id,
            evidence_ref=evidence.public_ref,
        )
    with denied_missing as missing_info:
        get_evidence_location(
            missing,
            settings,
            owner_user_id=caller_id,
            evidence_ref="ev_" + "z" * 32,
        )
    assert owned_info.value.status_code == missing_info.value.status_code == 404
    assert owned_info.value.code == missing_info.value.code == "evidence_not_found"
    assert owned_info.value.message == missing_info.value.message == "Evidence not found."
    for body in (str(owned_info.value), str(missing_info.value)):
        assert "0.12" not in body
        assert block.id not in body
        assert source.original_object_key not in body


@pytest.mark.parametrize(
    "mutate",
    [
        "redacted_turn",
        "redacted_evidence",
        "deleting_source",
        "ineligible",
    ],
)
def test_get_evidence_location_delete_and_redaction_fences(
    mutate: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    domain, source, block, conversation, turn, evidence = _location_graph()
    eligible = True
    if mutate == "redacted_turn":
        turn.status = TURN_STATUS_REDACTED
    elif mutate == "redacted_evidence":
        evidence.redacted_at = datetime(2026, 7, 25, 13, 0, 0)
        evidence.citation_label = None
        evidence.source_label = None
        evidence.excerpt = None
    elif mutate == "deleting_source":
        source.state = SOURCE_STATE_DELETING
    else:
        eligible = False

    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / f'loc-{mutate}.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: eligible)
    session = _LocationSession(
        evidence=evidence,
        turn=turn,
        conversation=conversation,
        source=source,
        block=block,
        domain=domain,
    )
    with pytest.raises(DocumentError) as exc_info:
        get_evidence_location(
            session,
            settings,
            owner_user_id="user-owner",
            evidence_ref=evidence.public_ref,
        )
    assert exc_info.value.status_code == 410
    assert exc_info.value.code == "evidence_unavailable"


def test_get_evidence_location_non_pdf_preview_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    domain, source, block, conversation, turn, evidence = _location_graph()
    source.content_type = "text/markdown"
    source.original_filename = "notes.md"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'loc-nonpdf.db'}",
        testing=True,
        source_storage_root=str(tmp_path / "source-root"),
    )
    monkeypatch.setattr(documents_module, "source_is_query_eligible", lambda *_a, **_k: True)
    session = _LocationSession(
        evidence=evidence,
        turn=turn,
        conversation=conversation,
        source=source,
        block=block,
        domain=domain,
    )
    with pytest.raises(DocumentError) as exc_info:
        get_evidence_location(
            session,
            settings,
            owner_user_id="user-owner",
            evidence_ref=evidence.public_ref,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "document_preview_unavailable"


def _library_db(tmp_path: Path) -> tuple[DbSession, Domain]:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'docs-library.db'}")
    Base.metadata.create_all(engine)
    db = DbSession(engine)
    db.add(ProviderConfig(provider_kind="openai", display_name="OpenAI", requires_credentials=False))
    db.add(
        ModelProfile(
            id="emb-1",
            name="embedding",
            profile_kind="embedding",
            provider_kind="openai",
            model_name="text-embedding-3-small",
            vector_dimensions=1536,
        )
    )
    domain = _domain()
    domain.embedding_profile_id = "emb-1"
    db.add(domain)
    db.flush()
    return db, domain


def _eligible_library_source(
    domain_id: str,
    *,
    filename: str,
    updated_at: datetime,
    sha_suffix: str,
) -> SourceDocument:
    source_id = str(uuid4())
    content_hash = "b" * 64
    generation = 1
    return SourceDocument(
        id=source_id,
        public_ref=new_document_public_ref(),
        domain_id=domain_id,
        original_filename=filename,
        content_type="application/pdf",
        original_sha256=(sha_suffix * 64)[:64],
        original_size_bytes=2048,
        original_object_key=f"obj_{sha_suffix}{uuid4().hex[:12]}",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
        index_state=SOURCE_INDEX_STATE_READY,
        index_generation=generation,
        index_content_hash=content_hash,
        index_request_id=compute_index_request_id(source_id, generation, content_hash),
        version=1,
        created_at=updated_at,
        updated_at=updated_at,
    )


def test_list_documents_paginates_and_rejects_expired_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, domain = _library_db(tmp_path)
    try:
        newer = _eligible_library_source(
            domain.id,
            filename="newer.pdf",
            updated_at=datetime(2026, 7, 25, 13, 0, 0),
            sha_suffix="1",
        )
        older = _eligible_library_source(
            domain.id,
            filename="older.pdf",
            updated_at=datetime(2026, 7, 25, 12, 0, 0),
            sha_suffix="2",
        )
        db.add_all([newer, older])
        db.commit()
        monkeypatch.setattr(documents_module, "_available_domains", lambda *_a, **_k: [domain])
        settings = Settings(
            database_url=f"sqlite+pysqlite:///{tmp_path / 'docs-library.db'}",
            testing=True,
            source_storage_root=str(tmp_path / "source-root"),
        )

        page_one = list_documents(db, settings, limit=1)
        assert len(page_one["documents"]) == 1
        assert page_one["documents"][0]["label"] == "newer.pdf"
        assert page_one["nextCursor"] is not None

        page_two = list_documents(db, settings, cursor=page_one["nextCursor"], limit=1)
        assert len(page_two["documents"]) == 1
        assert page_two["documents"][0]["label"] == "older.pdf"
        assert page_two["nextCursor"] is None

        with pytest.raises(DocumentError) as exc_info:
            list_documents(db, settings, cursor="not-a-cursor")
        assert exc_info.value.code == "cursor_expired"
    finally:
        db.close()
