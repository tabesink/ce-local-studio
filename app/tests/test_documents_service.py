from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from context_engine.api.catalog_schemas import DocumentSummaryDto, EvidenceLocationResponseDto
from context_engine.config import Settings
from context_engine.models import (
    SOURCE_BLOCK_KIND_TEXT,
    SOURCE_INDEX_STATE_READY,
    SOURCE_STATE_PREPARED,
    Domain,
    SourceBlock,
    SourceDocument,
)
from context_engine.services import documents as documents_module
from context_engine.services.documents import (
    DocumentError,
    content_disposition_for_label,
    get_document_content,
    parse_byte_range,
    preview_etag,
    preview_kind_for_source,
    safe_document_summary,
)
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
