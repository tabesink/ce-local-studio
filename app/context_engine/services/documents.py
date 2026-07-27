"""Member document library, governed PDF content, and evidence location."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from context_engine.adapters.object_storage import ObjectStorageError
from context_engine.config import Settings
from context_engine.models import (
    SOURCE_STATE_DELETING,
    TURN_STATUS_REDACTED,
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    Domain,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.auth import iso_utc
from context_engine.services.domains import (
    controller_from_settings,
    domain_available,
    safe_member_domain,
)
from context_engine.services.evidence import safe_section_label
from context_engine.services.indexing import source_is_query_eligible
from context_engine.services.sources import (
    SourceStorageError,
    sanitize_original_filename,
    storage_from_settings,
)

PDF_CONTENT_TYPE = "application/pdf"
DEFAULT_DOCUMENT_PAGE_SIZE = 50
MAX_DOCUMENT_PAGE_SIZE = 100

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


class DocumentError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}
        super().__init__(message)


@dataclass(frozen=True)
class DocumentContentResult:
    status_code: int
    body: bytes
    total_size: int
    etag: str
    content_disposition: str
    content_range: str | None = None


def preview_kind_for_source(source: SourceDocument) -> str:
    return "pdf" if source.content_type == PDF_CONTENT_TYPE else "unavailable"


def preview_etag(source: SourceDocument) -> str:
    """Strong opaque ETag derived from governed preview identity (never the raw object key)."""
    material = f"ce-preview:{source.original_sha256}:{source.version}:{source.original_size_bytes}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f'"{digest}"'


def content_disposition_for_label(label: str) -> str:
    safe = sanitize_original_filename(label)
    safe = _CONTROL_CHARS_RE.sub("_", safe)
    if not safe.lower().endswith(".pdf"):
        stem = safe.rsplit(".", 1)[0] if "." in safe else safe
        safe = f"{stem or 'document'}.pdf"
    escaped = safe.replace("\\", "\\\\").replace('"', '\\"')
    return f'inline; filename="{escaped}"'


def document_page_count(db: Session, source: SourceDocument) -> int | None:
    maximum = db.scalar(
        select(func.max(func.coalesce(SourceBlock.page_end, SourceBlock.page_start))).where(
            SourceBlock.source_document_id == source.id
        )
    )
    if maximum is None or int(maximum) < 1:
        return None
    return int(maximum)


def safe_document_summary(
    db: Session,
    source: SourceDocument,
    domain: Domain,
    *,
    query_eligible: bool,
) -> dict[str, Any]:
    return {
        "ref": source.public_ref,
        "label": sanitize_original_filename(source.original_filename),
        "domain": {
            **safe_member_domain(domain),
            "queryEligible": query_eligible,
        },
        "contentType": PDF_CONTENT_TYPE,
        "previewKind": preview_kind_for_source(source),
        "pageCount": document_page_count(db, source),
        "updatedAt": iso_utc(source.updated_at),
    }


def _encode_cursor(source: SourceDocument) -> str:
    payload = json.dumps(
        {"version": 1, "documentRef": source.public_ref},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> str:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        document_ref = str(payload["documentRef"])
        if (
            set(payload) != {"version", "documentRef"}
            or payload["version"] != 1
            or not document_ref.startswith("doc_")
        ):
            raise ValueError
        return document_ref
    except (KeyError, TypeError, ValueError):
        raise DocumentError(410, "cursor_expired", "The cursor has expired.") from None


def _matches_query(*, query: str | None, values: tuple[str | None, ...]) -> bool:
    if query is None:
        return True
    needle = query.casefold()
    return any(value is not None and needle in value.casefold() for value in values)


def _available_domains(
    db: Session,
    settings: Settings,
    *,
    domain_id: str | None,
) -> list[Domain]:
    controller = controller_from_settings(settings)
    statement = select(Domain)
    if domain_id is not None:
        statement = statement.where(Domain.id == domain_id)
    domains = list(db.scalars(statement.order_by(Domain.id)))
    return [domain for domain in domains if domain_available(db, domain, controller)]


def _resolve_library_source(
    db: Session,
    settings: Settings,
    document_ref: str,
) -> tuple[SourceDocument, Domain]:
    source = db.scalar(select(SourceDocument).where(SourceDocument.public_ref == document_ref))
    if source is None or source.state == SOURCE_STATE_DELETING:
        raise DocumentError(404, "document_not_found", "Document not found.")
    domain = db.get(Domain, source.domain_id)
    controller = controller_from_settings(settings)
    if domain is None or not source_is_query_eligible(
        db, source, domain, settings=settings, controller=controller
    ):
        raise DocumentError(404, "document_not_found", "Document not found.")
    return source, domain


def list_documents(
    db: Session,
    settings: Settings,
    *,
    domain_id: str | None = None,
    query: str | None = None,
    cursor: str | None = None,
    limit: int = DEFAULT_DOCUMENT_PAGE_SIZE,
) -> dict[str, Any]:
    if not 1 <= limit <= MAX_DOCUMENT_PAGE_SIZE:
        raise DocumentError(422, "validation_error", "Request validation failed.")

    domains = _available_domains(db, settings, domain_id=domain_id)
    if domain_id is not None and not domains:
        # Unknown or ineligible domain filter → empty library (no existence leak).
        return {"documents": [], "nextCursor": None}
    if not domains:
        return {"documents": [], "nextCursor": None}

    domain_by_id = {domain.id: domain for domain in domains}
    controller = controller_from_settings(settings)
    statement = select(SourceDocument).where(SourceDocument.domain_id.in_(list(domain_by_id.keys())))
    if cursor:
        anchor_ref = _decode_cursor(cursor)
        anchor = db.scalar(select(SourceDocument).where(SourceDocument.public_ref == anchor_ref))
        if anchor is None or anchor.domain_id not in domain_by_id:
            raise DocumentError(410, "cursor_expired", "The cursor has expired.")
        statement = statement.where(
            or_(
                SourceDocument.updated_at < anchor.updated_at,
                and_(
                    SourceDocument.updated_at == anchor.updated_at,
                    SourceDocument.id < anchor.id,
                ),
            )
        )

    candidates = db.scalars(
        statement.order_by(SourceDocument.updated_at.desc(), SourceDocument.id.desc())
    )

    matched: list[tuple[SourceDocument, dict[str, Any]]] = []
    for source in candidates:
        domain = domain_by_id.get(source.domain_id)
        if domain is None:
            continue
        if source.state == SOURCE_STATE_DELETING:
            continue
        if not source_is_query_eligible(db, source, domain, settings=settings, controller=controller):
            continue
        label = sanitize_original_filename(source.original_filename)
        if not _matches_query(query=query, values=(label, source.content_type)):
            continue
        matched.append((source, safe_document_summary(db, source, domain, query_eligible=True)))
        if len(matched) >= limit + 1:
            break

    has_more = len(matched) > limit
    page_rows = matched[:limit]
    return {
        "documents": [projection for _source, projection in page_rows],
        "nextCursor": _encode_cursor(page_rows[-1][0]) if has_more and page_rows else None,
    }


def get_document(db: Session, settings: Settings, document_ref: str) -> dict[str, Any]:
    source, domain = _resolve_library_source(db, settings, document_ref)
    return {
        "document": safe_document_summary(db, source, domain, query_eligible=True),
    }


def parse_byte_range(range_header: str | None, *, total_size: int) -> tuple[int, int] | None:
    """Return inclusive (start, end) for a single bytes range, or None for full body.

    Raises DocumentError(416) for malformed, multi-range, or unsatisfiable ranges.
    """
    if range_header is None or not range_header.strip():
        return None
    raw = range_header.strip()
    if "," in raw:
        raise DocumentError(
            416,
            "range_not_satisfiable",
            "Requested range is not satisfiable.",
            headers={"Content-Range": f"bytes */{total_size}"},
        )
    match = _RANGE_RE.fullmatch(raw)
    if match is None:
        raise DocumentError(
            416,
            "range_not_satisfiable",
            "Requested range is not satisfiable.",
            headers={"Content-Range": f"bytes */{total_size}"},
        )
    start_raw, end_raw = match.group(1), match.group(2)
    if total_size <= 0:
        raise DocumentError(
            416,
            "range_not_satisfiable",
            "Requested range is not satisfiable.",
            headers={"Content-Range": "bytes */0"},
        )
    if start_raw == "" and end_raw == "":
        raise DocumentError(
            416,
            "range_not_satisfiable",
            "Requested range is not satisfiable.",
            headers={"Content-Range": f"bytes */{total_size}"},
        )
    if start_raw == "":
        suffix = int(end_raw)
        if suffix <= 0:
            raise DocumentError(
                416,
                "range_not_satisfiable",
                "Requested range is not satisfiable.",
                headers={"Content-Range": f"bytes */{total_size}"},
            )
        start = max(total_size - suffix, 0)
        end = total_size - 1
    else:
        start = int(start_raw)
        end = int(end_raw) if end_raw != "" else total_size - 1
        if end < start or start >= total_size:
            raise DocumentError(
                416,
                "range_not_satisfiable",
                "Requested range is not satisfiable.",
                headers={"Content-Range": f"bytes */{total_size}"},
            )
        end = min(end, total_size - 1)
    return start, end


def get_document_content(
    db: Session,
    settings: Settings,
    document_ref: str,
    *,
    range_header: str | None = None,
    if_range: str | None = None,
) -> DocumentContentResult:
    source, _domain = _resolve_library_source(db, settings, document_ref)
    if preview_kind_for_source(source) != "pdf":
        raise DocumentError(
            409,
            "document_preview_unavailable",
            "A governed PDF preview is not available for this document.",
        )
    if not source.original_object_key:
        raise DocumentError(
            503,
            "document_content_unavailable",
            "Document content is temporarily unavailable.",
        )

    etag = preview_etag(source)
    disposition = content_disposition_for_label(source.original_filename)
    total_size = int(source.original_size_bytes)
    effective_range = range_header
    if if_range is not None and if_range.strip() and if_range.strip() != etag:
        # Stale/mismatched If-Range → ignore Range and return full entity (HTTP semantics).
        effective_range = None

    byte_range = parse_byte_range(effective_range, total_size=total_size)
    storage = storage_from_settings(settings)
    try:
        if byte_range is None:
            body = storage.store.get(source.original_object_key)
            return DocumentContentResult(
                status_code=200,
                body=body,
                total_size=total_size,
                etag=etag,
                content_disposition=disposition,
            )
        start, end = byte_range
        body = storage.store.get_range(source.original_object_key, start, end)
        return DocumentContentResult(
            status_code=206,
            body=body,
            total_size=total_size,
            etag=etag,
            content_disposition=disposition,
            content_range=f"bytes {start}-{end}/{total_size}",
        )
    except (ObjectStorageError, SourceStorageError, OSError) as exc:
        raise DocumentError(
            503,
            "document_content_unavailable",
            "Document content is temporarily unavailable.",
        ) from exc


def get_evidence_location(
    db: Session,
    settings: Settings,
    *,
    owner_user_id: str,
    evidence_ref: str,
) -> dict[str, Any]:
    evidence_ref_row = db.scalar(
        select(ConversationTurnEvidenceRef).where(ConversationTurnEvidenceRef.public_ref == evidence_ref)
    )
    if evidence_ref_row is None:
        raise DocumentError(404, "evidence_not_found", "Evidence not found.")

    turn = db.get(ConversationTurn, evidence_ref_row.turn_id)
    if turn is None:
        raise DocumentError(404, "evidence_not_found", "Evidence not found.")
    conversation = db.get(Conversation, turn.conversation_id)
    if conversation is None or conversation.owner_user_id != owner_user_id:
        raise DocumentError(404, "evidence_not_found", "Evidence not found.")

    if turn.status == TURN_STATUS_REDACTED or evidence_ref_row.redacted_at is not None:
        raise DocumentError(410, "evidence_unavailable", "Evidence is no longer available.")

    source = db.get(SourceDocument, evidence_ref_row.source_document_id)
    block = db.get(SourceBlock, evidence_ref_row.source_block_id)
    if source is None or block is None or block.source_document_id != source.id:
        raise DocumentError(410, "evidence_unavailable", "Evidence is no longer available.")
    if source.state == SOURCE_STATE_DELETING:
        raise DocumentError(410, "evidence_unavailable", "Evidence is no longer available.")

    domain = db.get(Domain, source.domain_id)
    controller = controller_from_settings(settings)
    if domain is None or not source_is_query_eligible(
        db, source, domain, settings=settings, controller=controller
    ):
        raise DocumentError(410, "evidence_unavailable", "Evidence is no longer available.")

    kind = preview_kind_for_source(source)
    if kind != "pdf":
        raise DocumentError(
            409,
            "document_preview_unavailable",
            "A governed PDF preview is not available for this document.",
        )

    if evidence_ref_row.citation_label is None or block.page_start is None:
        raise DocumentError(410, "evidence_unavailable", "Evidence is no longer available.")

    section_label = safe_section_label(block.section_path)
    return {
        "evidence": {
            "id": evidence_ref_row.public_ref,
            "citationLabel": evidence_ref_row.citation_label,
            "kind": block.kind,
        },
        "document": {
            "ref": source.public_ref,
            "label": sanitize_original_filename(source.original_filename),
            "previewKind": kind,
            "pageCount": document_page_count(db, source),
        },
        "anchor": {
            "pageNumber": block.page_start,
            "region": None,
            "sectionLabel": section_label,
            "fallback": "section" if section_label else "page",
        },
    }
