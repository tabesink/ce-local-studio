"""Document parser port and Docling/Reducto adapter implementations.

Adapters return one canonical parser-independent PreparedSource. They never
authorize, commit product state, or expose raw provider payloads.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from context_engine.models import (
    PARSER_DOCLING,
    PARSER_REDUCTO,
    SOURCE_BLOCK_KIND_FIGURE,
    SOURCE_BLOCK_KIND_TABLE,
    SOURCE_BLOCK_KIND_TEXT,
)

_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_FORBIDDEN_PREPARED_KEYS = {
    "bbox",
    "confidence",
    "granular_confidence",
    "image_url",
    "job_id",
    "native_id",
    "parser_payload",
    "pdf_url",
    "provider_payload",
    "self_ref",
    "studio_link",
    "task_id",
    "url",
}


class ParserAdapterError(Exception):
    def __init__(self, code: str, message: str = "Source preparation failed.", status_code: int = 502) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class PreparedWarning:
    code: str
    message: str


@dataclass(frozen=True)
class PreparedBlock:
    source_order: int
    kind: str
    canonical_markdown: str
    heading_level: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    section_path: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PreparedImage:
    source_order: int
    content_hash: str
    mime_type: str
    bytes_data: bytes
    alt_text: str | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class PreparedSource:
    source_document_id: str
    parser_kind: str
    blocks: list[PreparedBlock]
    images: list[PreparedImage] = field(default_factory=list)
    warnings: list[PreparedWarning] = field(default_factory=list)


@dataclass(frozen=True)
class ParserRequest:
    source_document_id: str
    parser_kind: str
    original_bytes: bytes
    content_type: str | None = None
    filename: str | None = None
    credential: str | None = None


class DocumentParser(Protocol):
    def parse(self, request: ParserRequest) -> PreparedSource: ...


DoclingConverter = Callable[[bytes, str | None, str | None], dict[str, Any]]
ReductoTransport = Callable[[ParserRequest, float], dict[str, Any]]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _page_from_native(value: Any) -> int | None:
    if isinstance(value, dict):
        for key in ("page", "page_no", "page_number"):
            page = value.get(key)
            if isinstance(page, int) and page >= 1:
                return page
        bbox = value.get("bbox")
        if isinstance(bbox, dict):
            return _page_from_native(bbox)
    if isinstance(value, list):
        for item in value:
            page = _page_from_native(item)
            if page is not None:
                return page
    return None


def _heading_markdown(text: str, level: int) -> str:
    text = text.lstrip("# ").strip()
    prefix = "#" * max(1, min(level, 6))
    return f"{prefix} {text}"


def normalize_reducto_parse_response(source_document_id: str, parser_kind: str, payload: dict[str, Any]) -> PreparedSource:
    result = payload.get("result", payload)
    if isinstance(result, dict) and result.get("type") == "url":
        raise ParserAdapterError(
            "parser_malformed_response",
            "Parser response could not be normalized.",
        )
    chunks = result.get("chunks") if isinstance(result, dict) else None
    if not isinstance(chunks, list):
        raise ParserAdapterError("parser_malformed_response", "Parser response could not be normalized.")

    blocks: list[PreparedBlock] = []
    images: list[PreparedImage] = []
    section_path: list[str] = []
    order = 1
    for chunk in chunks:
        native_blocks = chunk.get("blocks", []) if isinstance(chunk, dict) else []
        if not native_blocks and isinstance(chunk, dict) and chunk.get("content"):
            native_blocks = [{"type": "Text", "content": chunk.get("content")}]
        for native in native_blocks:
            if not isinstance(native, dict):
                continue
            native_type = _safe_text(native.get("type") or native.get("label")).lower()
            content = _safe_text(native.get("content") or native.get("text") or native.get("caption"))
            page = _page_from_native(native)
            heading_level: int | None = None
            kind = SOURCE_BLOCK_KIND_TEXT
            if native_type in {"title"}:
                heading_level = 1
                if content:
                    section_path = [content]
                    content = _heading_markdown(content, heading_level)
            elif native_type in {"section header", "section_header", "header", "heading"}:
                heading_level = 2
                if content:
                    section_path = (section_path[:1] if section_path else []) + [content]
                    content = _heading_markdown(content, heading_level)
            elif "table" in native_type:
                kind = SOURCE_BLOCK_KIND_TABLE
            elif "figure" in native_type or "picture" in native_type or "image" in native_type:
                kind = SOURCE_BLOCK_KIND_FIGURE
            if not content and kind == SOURCE_BLOCK_KIND_FIGURE:
                content = _safe_text(native.get("alt_text")) or "Figure"
            blocks.append(
                PreparedBlock(
                    source_order=order,
                    kind=kind,
                    canonical_markdown=content,
                    heading_level=heading_level,
                    page_start=page,
                    page_end=page,
                    section_path=list(section_path),
                )
            )
            image_bytes = native.get("image_bytes")
            if kind == SOURCE_BLOCK_KIND_FIGURE and isinstance(image_bytes, bytes):
                mime_type = _safe_text(native.get("mime_type") or "image/png").lower()
                images.append(
                    PreparedImage(
                        source_order=order,
                        content_hash=hashlib.sha256(image_bytes).hexdigest(),
                        mime_type=mime_type,
                        bytes_data=image_bytes,
                        alt_text=_safe_text(native.get("alt_text")) or None,
                        page_number=page,
                    )
                )
            order += 1
    return PreparedSource(source_document_id=source_document_id, parser_kind=parser_kind, blocks=blocks, images=images)


def normalize_docling_document(source_document_id: str, parser_kind: str, payload: dict[str, Any]) -> PreparedSource:
    items_by_ref: dict[str, dict[str, Any]] = {}
    for list_name in ("texts", "tables", "pictures"):
        values = payload.get(list_name, [])
        if isinstance(values, list):
            for index, item in enumerate(values):
                if isinstance(item, dict):
                    ref = str(item.get("self_ref") or f"#/{list_name}/{index}")
                    items_by_ref[ref] = item

    ordered_items: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref") or node.get("self_ref") or node.get("ref")
            if isinstance(ref, str) and ref in items_by_ref:
                ordered_items.append(items_by_ref[ref])
            for child in node.get("children", []) or []:
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    body = payload.get("body")
    walk(body)
    if not ordered_items:
        for list_name in ("texts", "tables", "pictures"):
            values = payload.get(list_name, [])
            if isinstance(values, list):
                ordered_items.extend(item for item in values if isinstance(item, dict))

    blocks: list[PreparedBlock] = []
    images: list[PreparedImage] = []
    section_path: list[str] = []
    for order, item in enumerate(ordered_items, start=1):
        label = _safe_text(item.get("label") or item.get("type") or item.get("name")).lower()
        text = _safe_text(item.get("text") or item.get("content") or item.get("caption"))
        page = _page_from_native(item.get("prov") or item)
        heading_level: int | None = None
        kind = SOURCE_BLOCK_KIND_TEXT
        if "title" in label:
            heading_level = 1
            if text:
                section_path = [text]
                text = _heading_markdown(text, heading_level)
        elif "section" in label or "header" in label:
            heading_level = int(item.get("level") or 2)
            if text:
                section_path = (section_path[: max(0, heading_level - 1)] if section_path else []) + [text]
                text = _heading_markdown(text, heading_level)
        elif "table" in label:
            kind = SOURCE_BLOCK_KIND_TABLE
        elif "picture" in label or "figure" in label or "image" in label:
            kind = SOURCE_BLOCK_KIND_FIGURE
        if not text and kind == SOURCE_BLOCK_KIND_FIGURE:
            text = _safe_text(item.get("alt_text")) or "Figure"
        blocks.append(
            PreparedBlock(
                source_order=order,
                kind=kind,
                canonical_markdown=text,
                heading_level=heading_level,
                page_start=page,
                page_end=page,
                section_path=list(section_path),
            )
        )
        image_bytes = item.get("image_bytes")
        if kind == SOURCE_BLOCK_KIND_FIGURE and isinstance(image_bytes, bytes):
            mime_type = _safe_text(item.get("mime_type") or "image/png").lower()
            images.append(
                PreparedImage(
                    source_order=order,
                    content_hash=hashlib.sha256(image_bytes).hexdigest(),
                    mime_type=mime_type,
                    bytes_data=image_bytes,
                    alt_text=_safe_text(item.get("alt_text")) or None,
                    page_number=page,
                )
            )
    return PreparedSource(source_document_id=source_document_id, parser_kind=parser_kind, blocks=blocks, images=images)


def _docling_payload_from_document(document: Any) -> dict[str, Any]:
    if isinstance(document, dict):
        return document
    export = getattr(document, "export_to_dict", None)
    if callable(export):
        payload = export()
        if isinstance(payload, dict):
            return payload
    model_dump = getattr(document, "model_dump", None)
    if callable(model_dump):
        payload = model_dump()
        if isinstance(payload, dict):
            return payload
    raise ParserAdapterError("parser_malformed_response", "Parser response could not be normalized.")


def _default_docling_convert(original_bytes: bytes, content_type: str | None, filename: str | None) -> dict[str, Any]:
    del content_type
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ParserAdapterError("parser_unavailable", "Parser is not available.", 503) from exc

    import tempfile
    from pathlib import Path

    suffix = Path(filename or "source.bin").suffix or ".bin"
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as handle:
            handle.write(original_bytes)
            handle.flush()
            converter = DocumentConverter()
            result = converter.convert(handle.name)
            document = getattr(result, "document", result)
            return _docling_payload_from_document(document)
    except ParserAdapterError:
        raise
    except TimeoutError as exc:
        raise ParserAdapterError("parser_timeout", "Parser timed out.", 504) from exc
    except Exception as exc:  # noqa: BLE001 - adapter boundary maps vendor failures
        raise ParserAdapterError("parser_unavailable", "Parser failed.", 502) from exc


def _default_reducto_transport(request: ParserRequest, timeout_seconds: float) -> dict[str, Any]:
    if not request.credential:
        raise ParserAdapterError("parser_not_ready", "Parser is not configured.", 409)
    try:
        import reducto  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ParserAdapterError("parser_unavailable", "Parser is not available.", 503) from exc

    from pathlib import Path

    extension = Path(request.filename or "").suffix or _extension_for_content_type(request.content_type)
    try:
        client = reducto.Reducto(api_key=request.credential, timeout=timeout_seconds)
        upload = client.upload(file=request.original_bytes, extension=extension)
        file_id = getattr(upload, "file_id", None) or (upload.get("file_id") if isinstance(upload, dict) else None)
        if not file_id:
            raise ParserAdapterError("parser_malformed_response", "Parser response could not be normalized.")
        result = client.parse.run(input=file_id)
        return _reducto_result_to_payload(result, timeout_seconds=timeout_seconds)
    except ParserAdapterError:
        raise
    except TimeoutError as exc:
        raise ParserAdapterError("parser_timeout", "Parser timed out.", 504) from exc
    except Exception as exc:  # noqa: BLE001 - adapter boundary maps vendor failures
        message = str(exc).lower()
        if "auth" in message or "401" in message or "403" in message:
            raise ParserAdapterError("parser_not_ready", "Parser is not configured.", 409) from exc
        if "timeout" in message or "timed out" in message:
            raise ParserAdapterError("parser_timeout", "Parser timed out.", 504) from exc
        raise ParserAdapterError("parser_unavailable", "Parser failed.", 502) from exc


def _extension_for_content_type(content_type: str | None) -> str:
    mapping = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/plain": ".txt",
        "text/markdown": ".md",
    }
    if content_type is None:
        return ".bin"
    return mapping.get(content_type.lower(), ".bin")


def _reducto_result_to_payload(result: Any, *, timeout_seconds: float) -> dict[str, Any]:
    del timeout_seconds
    if isinstance(result, dict):
        payload = result
    else:
        model_dump = getattr(result, "model_dump", None)
        if callable(model_dump):
            payload = model_dump()
        else:
            payload = {
                "result": getattr(result, "result", None),
                "job_id": getattr(result, "job_id", None),
            }
    if not isinstance(payload, dict):
        raise ParserAdapterError("parser_malformed_response", "Parser response could not be normalized.")

    nested = payload.get("result")
    if nested is not None and not isinstance(nested, dict):
        nested_dump = getattr(nested, "model_dump", None)
        if callable(nested_dump):
            nested = nested_dump()
            payload = {**payload, "result": nested}
        else:
            chunks = getattr(nested, "chunks", None)
            result_type = getattr(nested, "type", None)
            url = getattr(nested, "url", None)
            payload = {
                **payload,
                "result": {
                    "type": result_type,
                    "chunks": chunks,
                    "url": url,
                },
            }
            nested = payload["result"]

    if isinstance(nested, dict) and nested.get("type") == "url":
        # URL results must be resolved by the transport before normalization so
        # private presigned URLs never enter product persistence.
        raise ParserAdapterError(
            "parser_malformed_response",
            "Parser response could not be normalized.",
        )
    return payload


class DoclingDocumentParser:
    def __init__(self, *, convert: DoclingConverter | None = None) -> None:
        self._convert = convert or _default_docling_convert

    def parse(self, request: ParserRequest) -> PreparedSource:
        if request.parser_kind != PARSER_DOCLING:
            raise ParserAdapterError("parser_unavailable", "Parser is not available.", 503)
        try:
            payload = self._convert(request.original_bytes, request.content_type, request.filename)
        except ParserAdapterError:
            raise
        except TimeoutError as exc:
            raise ParserAdapterError("parser_timeout", "Parser timed out.", 504) from exc
        except Exception as exc:  # noqa: BLE001
            raise ParserAdapterError("parser_unavailable", "Parser failed.", 502) from exc
        if not isinstance(payload, dict):
            raise ParserAdapterError("parser_malformed_response", "Parser response could not be normalized.")
        return normalize_docling_document(request.source_document_id, request.parser_kind, payload)


class ReductoDocumentParser:
    def __init__(self, *, transport: ReductoTransport | None = None, timeout_seconds: float = 60.0) -> None:
        self._transport = transport or _default_reducto_transport
        self._timeout_seconds = timeout_seconds

    def parse(self, request: ParserRequest) -> PreparedSource:
        if request.parser_kind != PARSER_REDUCTO:
            raise ParserAdapterError("parser_unavailable", "Parser is not available.", 503)
        if not request.credential:
            raise ParserAdapterError("parser_not_ready", "Parser is not configured.", 409)
        try:
            payload = self._transport(request, self._timeout_seconds)
        except ParserAdapterError:
            raise
        except TimeoutError as exc:
            raise ParserAdapterError("parser_timeout", "Parser timed out.", 504) from exc
        except Exception as exc:  # noqa: BLE001
            raise ParserAdapterError("parser_unavailable", "Parser failed.", 502) from exc
        if not isinstance(payload, dict):
            raise ParserAdapterError("parser_malformed_response", "Parser response could not be normalized.")
        # Privacy: never pass through top-level provider URLs into normalization inputs beyond chunks.
        sanitized = {"result": payload.get("result", payload)}
        return normalize_reducto_parse_response(request.source_document_id, request.parser_kind, sanitized)


def default_parser_registry(*, reducto_timeout_seconds: float = 60.0) -> dict[str, DocumentParser]:
    return {
        PARSER_DOCLING: DoclingDocumentParser(),
        PARSER_REDUCTO: ReductoDocumentParser(timeout_seconds=reducto_timeout_seconds),
    }


def validate_prepared_source(prepared: PreparedSource) -> None:
    from context_engine.models import SOURCE_BLOCK_KINDS

    if not prepared.blocks:
        raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
    seen: set[int] = set()
    figure_orders = {block.source_order for block in prepared.blocks if block.kind == SOURCE_BLOCK_KIND_FIGURE}
    for block in prepared.blocks:
        if block.source_order < 1 or block.source_order in seen:
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        seen.add(block.source_order)
        if block.kind not in SOURCE_BLOCK_KINDS:
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        if block.kind in {SOURCE_BLOCK_KIND_TEXT, SOURCE_BLOCK_KIND_TABLE} and not block.canonical_markdown.strip():
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        if block.kind == SOURCE_BLOCK_KIND_FIGURE and not block.canonical_markdown.strip():
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        if block.heading_level is not None and block.heading_level < 1:
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        if block.page_start is not None and block.page_start < 1:
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        if block.page_end is not None and block.page_end < 1:
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        if block.page_start is not None and block.page_end is not None and block.page_end < block.page_start:
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        as_dict = block.__dict__
        if _FORBIDDEN_PREPARED_KEYS.intersection(as_dict):
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
    for image in prepared.images:
        if image.source_order not in figure_orders:
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        if image.mime_type not in _IMAGE_MIME_TYPES:
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)
        if hashlib.sha256(image.bytes_data).hexdigest() != image.content_hash:
            raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)


def dump_prepared_source_for_privacy_scan(prepared: PreparedSource) -> str:
    """Serialize public prepared fields only for privacy regression scans."""
    return json.dumps(
        {
            "sourceDocumentId": prepared.source_document_id,
            "parserKind": prepared.parser_kind,
            "blocks": [
                {
                    "sourceOrder": block.source_order,
                    "kind": block.kind,
                    "canonicalMarkdown": block.canonical_markdown,
                    "headingLevel": block.heading_level,
                    "pageStart": block.page_start,
                    "pageEnd": block.page_end,
                    "sectionPath": block.section_path,
                }
                for block in prepared.blocks
            ],
            "images": [
                {
                    "sourceOrder": image.source_order,
                    "contentHash": image.content_hash,
                    "mimeType": image.mime_type,
                    "altText": image.alt_text,
                    "pageNumber": image.page_number,
                }
                for image in prepared.images
            ],
        },
        sort_keys=True,
    )
