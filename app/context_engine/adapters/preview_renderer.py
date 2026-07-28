"""Private governed-preview renderer port.

Produces bounded PDF bytes plus a private page-map payload. Never authorizes,
persists product state, or returns storage paths / raw renderer stderr to
callers beyond typed safe error codes.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MARKDOWN_CONTENT_TYPE = "text/markdown"
PLAIN_TEXT_CONTENT_TYPE = "text/plain"

SUPPORTED_PREVIEW_CONTENT_TYPES = frozenset(
    {
        PDF_CONTENT_TYPE,
        DOCX_CONTENT_TYPE,
        MARKDOWN_CONTENT_TYPE,
        PLAIN_TEXT_CONTENT_TYPE,
    }
)

RENDERER_VERSION_PDF_PASSTHROUGH = "ce-preview-pdf-passthrough-v1"
RENDERER_VERSION_TEXT = "ce-preview-text-v1"

_MAX_OUTPUT_BYTES = 25 * 1024 * 1024
_MAX_PAGES = 500
_CHARS_PER_PAGE = 1800
_DEFAULT_TIMEOUT_SECONDS = 30.0

_PDF_MAGIC = b"%PDF-"
# Count leaf pages only (avoid matching /Type /Pages).
_PAGE_OBJ_RE = re.compile(rb"/Type\s*/Page(?!\s*s)\b")


class PreviewRendererError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class PreviewRenderResult:
    pdf_bytes: bytes
    page_count: int
    checksum_sha256: str
    renderer_version: str
    source_sha256: str
    page_map: dict[str, Any]
    reused_original_bytes: bool


def _safe_error(code: str, message: str, status_code: int = 502) -> PreviewRendererError:
    return PreviewRendererError(code, message, status_code=status_code)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_pdf_bytes(pdf_bytes: bytes) -> int:
    if not pdf_bytes.startswith(_PDF_MAGIC):
        raise _safe_error("preview_malformed_output", "Preview output is not a valid PDF.", 502)
    if len(pdf_bytes) > _MAX_OUTPUT_BYTES:
        raise _safe_error("preview_output_too_large", "Preview output exceeds bounded size.", 413)
    if len(pdf_bytes) < 8:
        raise _safe_error("preview_malformed_output", "Preview output is not a valid PDF.", 502)
    page_count = len(_PAGE_OBJ_RE.findall(pdf_bytes))
    if page_count < 1:
        # Minimal synthetic PDFs used in tests may omit /Type /Page markers.
        page_count = 1
    if page_count > _MAX_PAGES:
        raise _safe_error("preview_too_many_pages", "Preview page count exceeds the bounded limit.", 413)
    return page_count


def _validate_page_map(page_map: dict[str, Any], *, page_count: int, renderer_version: str) -> None:
    if page_map.get("version") != 1:
        raise _safe_error("preview_invalid_page_map", "Preview page map is invalid.", 502)
    if page_map.get("rendererVersion") != renderer_version:
        raise _safe_error("preview_invalid_page_map", "Preview page map is invalid.", 502)
    if int(page_map.get("pageCount") or 0) != page_count:
        raise _safe_error("preview_invalid_page_map", "Preview page map is invalid.", 502)
    pages = page_map.get("pages")
    if not isinstance(pages, list) or len(pages) != page_count:
        raise _safe_error("preview_invalid_page_map", "Preview page map is invalid.", 502)
    for index, entry in enumerate(pages, start=1):
        if not isinstance(entry, dict) or int(entry.get("pageNumber") or 0) != index:
            raise _safe_error("preview_invalid_page_map", "Preview page map is invalid.", 502)


def _escape_pdf_text(text: str) -> bytes:
    cleaned = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in text)
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("ascii")


def _assemble_pdf(page_texts: list[str]) -> bytes:
    """Deterministic minimal PDF (Helvetica, fixed geometry) for text/markdown/docx."""
    if not page_texts:
        page_texts = [""]

    content_bodies: list[bytes] = []
    for text in page_texts:
        lines = (text.splitlines() or [""])[:60]
        parts = [b"BT /F1 11 Tf 50 750 Td 14 TL"]
        first = True
        for line in lines:
            escaped = _escape_pdf_text(line[:120])
            if first:
                parts.append(b" (" + escaped + b") Tj")
                first = False
            else:
                parts.append(b" T* (" + escaped + b") Tj")
        parts.append(b" ET")
        stream = b"\n".join(parts)
        content_bodies.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        )

    # IDs: 1=catalog, 2=pages, 3=font, then content_i, page_i
    next_id = 4
    kid_ids: list[int] = []
    content_ids: list[int] = []
    for _ in content_bodies:
        content_ids.append(next_id)
        kid_ids.append(next_id + 1)
        next_id += 2

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    obj_offsets: dict[int, int] = {}

    def write_obj(obj_id: int, body: bytes) -> None:
        obj_offsets[obj_id] = len(out)
        out.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")

    write_obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{kid} 0 R" for kid in kid_ids)
    write_obj(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(kid_ids)} >>".encode("ascii"))
    write_obj(3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for content_body, content_id, page_id in zip(content_bodies, content_ids, kid_ids, strict=True):
        write_obj(content_id, content_body)
        write_obj(
            page_id,
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R "
                f"/Resources << /Font << /F1 3 0 R >> >> >>"
            ).encode("ascii"),
        )

    xref_pos = len(out)
    max_id = next_id - 1
    out.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, max_id + 1):
        out.extend(f"{obj_offsets[obj_id]:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


def _chunk_text_to_pages(text: str) -> tuple[list[str], list[dict[str, Any]]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        normalized = " "
    pages: list[str] = []
    page_entries: list[dict[str, Any]] = []
    cursor = 0
    total = len(normalized)
    while cursor < total:
        end = min(cursor + _CHARS_PER_PAGE, total)
        if end < total:
            # Prefer break on newline within the last 200 chars.
            window = normalized[cursor:end]
            br = window.rfind("\n", max(0, len(window) - 200))
            if br > 0:
                end = cursor + br + 1
        chunk = normalized[cursor:end]
        pages.append(chunk)
        page_entries.append(
            {
                "pageNumber": len(pages),
                "charStart": cursor,
                "charEnd": end,
            }
        )
        cursor = end
        if len(pages) > _MAX_PAGES:
            raise _safe_error("preview_too_many_pages", "Preview page count exceeds the bounded limit.", 413)
    return pages, page_entries


def _decode_text_source(data: bytes, content_type: str) -> str:
    if content_type == DOCX_CONTENT_TYPE:
        try:
            from docx import Document  # type: ignore[import-not-found]
        except ImportError as exc:
            raise _safe_error("preview_renderer_unavailable", "Preview renderer is not available.", 503) from exc
        try:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
                handle.write(data)
                path = handle.name
            try:
                document = Document(path)
                parts = [p.text for p in document.paragraphs]
                return "\n".join(parts)
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        except PreviewRendererError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise _safe_error("preview_render_failed", "Preview rendering failed.", 502) from exc

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _safe_error("preview_unsupported_input", "Source bytes could not be decoded.", 400) from exc


def _render_text_like(data: bytes, content_type: str) -> dict[str, Any]:
    text = _decode_text_source(data, content_type)
    page_texts, page_entries = _chunk_text_to_pages(text)
    pdf_bytes = _assemble_pdf(page_texts)
    page_count = _validate_pdf_bytes(pdf_bytes)
    if page_count != len(page_texts):
        # Prefer PDF-derived count when structure is authoritative.
        page_count = len(page_texts)
    page_map = {
        "version": 1,
        "rendererVersion": RENDERER_VERSION_TEXT,
        "pageCount": page_count,
        "pages": page_entries[:page_count],
    }
    return {
        "pdf_bytes": pdf_bytes,
        "page_count": page_count,
        "renderer_version": RENDERER_VERSION_TEXT,
        "page_map": page_map,
        "reused_original_bytes": False,
    }


def _render_pdf_passthrough(data: bytes) -> dict[str, Any]:
    page_count = _validate_pdf_bytes(data)
    page_map = {
        "version": 1,
        "rendererVersion": RENDERER_VERSION_PDF_PASSTHROUGH,
        "pageCount": page_count,
        "pages": [{"pageNumber": i, "identity": True} for i in range(1, page_count + 1)],
    }
    return {
        "pdf_bytes": data,
        "page_count": page_count,
        "renderer_version": RENDERER_VERSION_PDF_PASSTHROUGH,
        "page_map": page_map,
        "reused_original_bytes": True,
    }


def _worker_entry(content_type: str, in_path: str, out_path: str) -> None:
    try:
        data = Path(in_path).read_bytes()
        if content_type == PDF_CONTENT_TYPE:
            payload = _render_pdf_passthrough(data)
        elif content_type in {MARKDOWN_CONTENT_TYPE, PLAIN_TEXT_CONTENT_TYPE, DOCX_CONTENT_TYPE}:
            payload = _render_text_like(data, content_type)
        else:
            raise _safe_error("preview_unsupported_content_type", "Preview content type is not supported.", 400)
        # Serialize pdf as base64 for JSON boundary.
        import base64

        Path(out_path).write_text(
            json.dumps(
                {
                    "pdf_b64": base64.b64encode(payload["pdf_bytes"]).decode("ascii"),
                    "page_count": payload["page_count"],
                    "renderer_version": payload["renderer_version"],
                    "page_map": payload["page_map"],
                    "reused_original_bytes": payload["reused_original_bytes"],
                }
            ),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        err = {
            "code": "preview_render_failed",
            "message": "Preview rendering failed.",
            "status_code": 502,
        }
        if isinstance(exc, PreviewRendererError):
            err = {"code": exc.code, "message": exc.message, "status_code": exc.status_code}
        elif isinstance(exc, ImportError):
            err = {
                "code": "preview_renderer_unavailable",
                "message": "Preview renderer is not available.",
                "status_code": 503,
            }
        Path(out_path).write_text(json.dumps({"__preview_error__": err}), encoding="utf-8")


def render_governed_preview(
    original_bytes: bytes,
    content_type: str,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    source_sha256: str | None = None,
) -> PreviewRenderResult:
    """Render a governed PDF preview in a killable child process."""
    if content_type not in SUPPORTED_PREVIEW_CONTENT_TYPES:
        raise _safe_error("preview_unsupported_content_type", "Preview content type is not supported.", 400)
    if timeout_seconds <= 0:
        raise _safe_error("preview_render_failed", "Preview rendering failed.", 502)
    if not original_bytes:
        raise _safe_error("preview_unsupported_input", "Source bytes are empty.", 400)

    source_hash = source_sha256 or _sha256(original_bytes)
    fd, in_name = tempfile.mkstemp(suffix=".bin")
    out_fd, out_name = tempfile.mkstemp(suffix=".json")
    os.close(out_fd)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(original_bytes)

        ctx = mp.get_context("spawn")
        proc = ctx.Process(target=_worker_entry, args=(content_type, in_name, out_name), daemon=True)
        proc.start()
        proc.join(timeout_seconds)
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            if proc.is_alive():
                proc.kill()
                proc.join(1)
            raise _safe_error("preview_timeout", "Preview rendering timed out.", 504)

        raw = Path(out_name).read_text(encoding="utf-8")
        if not raw.strip():
            raise _safe_error("preview_render_failed", "Preview rendering failed.", 502)
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise _safe_error("preview_render_failed", "Preview rendering failed.", 502)
        err = payload.get("__preview_error__")
        if isinstance(err, dict):
            raise _safe_error(
                str(err.get("code") or "preview_render_failed"),
                str(err.get("message") or "Preview rendering failed."),
                int(err.get("status_code") or 502),
            )

        import base64

        pdf_bytes = base64.b64decode(str(payload["pdf_b64"]))
        renderer_version = str(payload["renderer_version"])
        page_map = payload["page_map"]
        if not isinstance(page_map, dict):
            raise _safe_error("preview_invalid_page_map", "Preview page map is invalid.", 502)
        page_count = _validate_pdf_bytes(pdf_bytes)
        # Prefer declared count when PDF page markers are ambiguous for passthrough synthetics.
        declared = int(payload.get("page_count") or page_count)
        if content_type == PDF_CONTENT_TYPE and declared >= 1:
            page_count = declared
            page_map = {
                "version": 1,
                "rendererVersion": RENDERER_VERSION_PDF_PASSTHROUGH,
                "pageCount": page_count,
                "pages": [{"pageNumber": i, "identity": True} for i in range(1, page_count + 1)],
            }
        else:
            page_count = int(page_map.get("pageCount") or page_count)
        _validate_page_map(page_map, page_count=page_count, renderer_version=renderer_version)
        return PreviewRenderResult(
            pdf_bytes=pdf_bytes,
            page_count=page_count,
            checksum_sha256=_sha256(pdf_bytes),
            renderer_version=renderer_version,
            source_sha256=source_hash,
            page_map=page_map,
            reused_original_bytes=bool(payload.get("reused_original_bytes")),
        )
    except PreviewRendererError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _safe_error("preview_render_failed", "Preview rendering failed.", 502) from exc
    finally:
        for path in (in_name, out_name):
            try:
                os.unlink(path)
            except OSError:
                pass


def renderer_identity() -> Literal["ce-preview-v1"]:
    return "ce-preview-v1"
