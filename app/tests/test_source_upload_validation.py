from __future__ import annotations

import io
import zipfile
from datetime import datetime
from uuid import uuid4

import pytest

from context_engine.models import (
    PARSER_DOCLING,
    PARSER_REDUCTO,
    SOURCE_STATE_PENDING,
    SourceDocument,
)
from context_engine.services.source_upload import (
    MAX_SOURCE_FILE_SIZE_BYTES,
    UploadValidationError,
    ValidatedUpload,
    assert_safe_container,
    sniff_source_content_type,
    validate_upload_bytes,
)


def _docx_bytes(*, uncompressed_pad: int = 0) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "<w:document></w:document>")
        if uncompressed_pad:
            archive.writestr("word/padding.bin", b"A" * uncompressed_pad)
    return buffer.getvalue()


def test_sniff_rejects_declared_pdf_spoof() -> None:
    # Declared PDF is ignored; binary/null payload is not an allowlisted sniffed type.
    with pytest.raises(UploadValidationError) as exc:
        validate_upload_bytes(
            b"\x00MZ-not-a-pdf",
            filename="manual.pdf",
            declared_content_type="application/pdf",
        )
    assert exc.value.code == "content_rejected"
    assert exc.value.status_code == 422

    # Text that is not PDF is accepted as text even when declared as PDF.
    accepted = validate_upload_bytes(
        b"plain notes",
        filename="manual.pdf",
        declared_content_type="application/pdf",
    )
    assert accepted.content_type == "text/plain"


def test_sniff_accepts_pdf_and_docx_and_markdown() -> None:
    pdf = validate_upload_bytes(b"%PDF-1.4 hello", filename="a.bin", declared_content_type="application/octet-stream")
    assert pdf.content_type == "application/pdf"
    assert len(pdf.sha256) == 64

    docx = validate_upload_bytes(_docx_bytes(), filename="a.bin", declared_content_type="text/plain")
    assert docx.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    md = validate_upload_bytes(b"# Title\n\nBody\n", filename="notes.md", declared_content_type="application/octet-stream")
    assert md.content_type == "text/markdown"


def test_oversize_upload_is_content_rejected() -> None:
    with pytest.raises(UploadValidationError) as exc:
        validate_upload_bytes(
            b"x" * (MAX_SOURCE_FILE_SIZE_BYTES + 1),
            filename="big.txt",
            declared_content_type="text/plain",
        )
    assert exc.value.code == "content_rejected"
    assert exc.value.status_code == 413


def test_docx_bomb_is_content_rejected() -> None:
    # Highly compressible payload that expands past the governed uncompressed budget.
    bomb = _docx_bytes(uncompressed_pad=MAX_SOURCE_FILE_SIZE_BYTES + 1024)
    assert len(bomb) < MAX_SOURCE_FILE_SIZE_BYTES
    with pytest.raises(UploadValidationError) as exc:
        validate_upload_bytes(bomb, filename="bomb.docx", declared_content_type="application/octet-stream")
    assert exc.value.code == "content_rejected"


def test_sniff_helpers_are_deterministic() -> None:
    assert sniff_source_content_type(b"%PDF-1.7", filename="x") == "application/pdf"
    assert sniff_source_content_type(_docx_bytes(), filename="x") == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert sniff_source_content_type(b"plain text", filename="note.txt") == "text/plain"
    with pytest.raises(UploadValidationError):
        assert_safe_container(
            b"PK\x03\x04not-a-zip",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


def test_frozen_parser_kind_is_source_owned() -> None:
    source = SourceDocument(
        id=str(uuid4()),
        public_ref=f"doc_{uuid4().hex}",
        domain_id="domain-manuals",
        original_filename="manual.pdf",
        content_type="application/pdf",
        original_sha256="b" * 64,
        original_size_bytes=12,
        original_object_key=f"obj_{uuid4().hex}",
        state=SOURCE_STATE_PENDING,
        parser_kind=PARSER_DOCLING,
        preparation_generation=1,
        version=1,
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 0, 0),
    )
    assert source.parser_kind == PARSER_DOCLING
    assert source.parser_kind != PARSER_REDUCTO
    assert ValidatedUpload(b"%PDF-1.4", "application/pdf", "a" * 64, 8).size_bytes == 8
