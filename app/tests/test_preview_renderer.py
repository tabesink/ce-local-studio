"""P10-06 U2: governed preview renderer port (AE1/AE2 fixture half, bounds, privacy)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from context_engine.adapters.preview_renderer import (
    DOCX_CONTENT_TYPE,
    MARKDOWN_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    PLAIN_TEXT_CONTENT_TYPE,
    RENDERER_VERSION_PDF_PASSTHROUGH,
    RENDERER_VERSION_TEXT,
    PreviewRendererError,
    render_governed_preview,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "documents"
ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
PYPROJECT = ROOT / "pyproject.toml"


def _minimal_docx_bytes(paragraphs: list[str]) -> bytes:
    """Build a tiny OOXML docx without requiring python-docx at fixture-write time."""
    body = []
    for text in paragraphs:
        body.append(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>")
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body)}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


def test_packaging_declares_preview_renderer_extra_and_image_gate() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "preview-renderer" in pyproject
    assert "python-docx" in pyproject
    assert "ARG CE_STACK_PREVIEW_IMAGE=0" in dockerfile
    assert "--extra preview-renderer" in dockerfile


def test_pdf_passthrough_preserves_bytes_and_identity_map() -> None:
    pdf = (FIXTURES / "ppe_solvent_a.pdf").read_bytes()
    first = render_governed_preview(pdf, PDF_CONTENT_TYPE)
    second = render_governed_preview(pdf, PDF_CONTENT_TYPE)
    assert first.reused_original_bytes is True
    assert first.pdf_bytes == pdf
    assert first.checksum_sha256 == second.checksum_sha256
    assert first.renderer_version == RENDERER_VERSION_PDF_PASSTHROUGH
    assert first.page_map["pageCount"] == first.page_count
    assert first.page_count >= 1


def test_markdown_and_text_are_deterministic() -> None:
    md = (FIXTURES / "sample_preview.md").read_bytes()
    txt = (FIXTURES / "sample_preview.txt").read_bytes()
    md_a = render_governed_preview(md, MARKDOWN_CONTENT_TYPE)
    md_b = render_governed_preview(md, MARKDOWN_CONTENT_TYPE)
    txt_a = render_governed_preview(txt, PLAIN_TEXT_CONTENT_TYPE)
    assert md_a.checksum_sha256 == md_b.checksum_sha256
    assert md_a.page_map == md_b.page_map
    assert md_a.renderer_version == RENDERER_VERSION_TEXT
    assert md_a.pdf_bytes.startswith(b"%PDF-")
    assert txt_a.pdf_bytes.startswith(b"%PDF-")
    assert txt_a.page_count >= 1
    assert md_a.reused_original_bytes is False


def test_docx_fixture_produces_valid_pdf_and_map() -> None:
    pytest.importorskip("docx")
    docx_bytes = _minimal_docx_bytes(
        [
            "Governed Preview DOCX Sample",
            "Relief valve downstream of the pump.",
        ]
    )
    result = render_governed_preview(docx_bytes, DOCX_CONTENT_TYPE)
    assert result.pdf_bytes.startswith(b"%PDF-")
    assert result.page_count >= 1
    assert result.checksum_sha256
    assert result.renderer_version == RENDERER_VERSION_TEXT
    assert len(result.page_map["pages"]) == result.page_count
    again = render_governed_preview(docx_bytes, DOCX_CONTENT_TYPE)
    assert again.checksum_sha256 == result.checksum_sha256


def test_unsupported_content_type_fails_closed() -> None:
    with pytest.raises(PreviewRendererError) as exc_info:
        render_governed_preview(b"hello", "application/vnd.ms-powerpoint")
    assert exc_info.value.code == "preview_unsupported_content_type"
    assert exc_info.value.status_code == 400


def test_malformed_pdf_passthrough_fails_closed() -> None:
    with pytest.raises(PreviewRendererError) as exc_info:
        render_governed_preview(b"not-a-pdf", PDF_CONTENT_TYPE)
    assert exc_info.value.code == "preview_malformed_output"


def test_timeout_kills_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    # Spawn re-imports the worker target; mock Process so the parent timeout/
    # terminate path is proven without a real hung child.
    class _HungProc:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._alive = True
            self.exitcode = None

        def start(self) -> None:
            return None

        def join(self, timeout: float | None = None) -> None:
            del timeout
            return None

        def is_alive(self) -> bool:
            return self._alive

        def terminate(self) -> None:
            self._alive = False

        def kill(self) -> None:
            self._alive = False

    class _Ctx:
        def Process(self, *args, **kwargs):  # noqa: N802 - mirrors multiprocessing API
            del args, kwargs
            return _HungProc()

    monkeypatch.setattr(
        "context_engine.adapters.preview_renderer.mp.get_context",
        lambda *_args, **_kwargs: _Ctx(),
    )
    with pytest.raises(PreviewRendererError) as exc_info:
        render_governed_preview(b"hello world", PLAIN_TEXT_CONTENT_TYPE, timeout_seconds=0.2)
    assert exc_info.value.code == "preview_timeout"
    assert exc_info.value.status_code == 504


def test_error_messages_do_not_include_temp_paths_or_source_text() -> None:
    with pytest.raises(PreviewRendererError) as exc_info:
        render_governed_preview(b"not-a-pdf", PDF_CONTENT_TYPE)
    blob = f"{exc_info.value.code}:{exc_info.value.message}".lower()
    assert "/tmp" not in blob
    assert "not-a-pdf" not in blob
    assert "traceback" not in blob
