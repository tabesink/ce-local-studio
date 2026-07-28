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
    SOURCE_BLOCK_KIND_FIGURE,
    SOURCE_INDEX_STATE_READY,
    SOURCE_STATE_DELETING,
    SOURCE_STATE_PREPARED,
    TURN_STATUS_REDACTED,
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    Domain,
    SourceBlock,
    SourceDocument,
    SourceImage,
)
from context_engine.services.auth import iso_utc
from context_engine.services.domains import (
    controller_from_settings,
    domain_available,
    safe_member_domain,
)
from context_engine.services.evidence import (
    project_persisted_evidence_anchor,
    remap_anchor_through_page_map,
)
from context_engine.services.indexing import source_has_current_index_identity, source_is_query_eligible
from context_engine.services.preview import preview_is_ready
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
    return "pdf" if preview_is_ready(source) else "unavailable"


def preview_etag(source: SourceDocument) -> str:
    """Strong opaque ETag derived from governed preview identity (never the raw object key)."""
    checksum = source.preview_sha256 or source.original_sha256
    version = int(source.preview_version or 0)
    size = int(source.preview_size_bytes or source.original_size_bytes)
    material = f"ce-preview:{checksum}:{version}:{size}"
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
    if preview_is_ready(source) and source.preview_page_count is not None and int(source.preview_page_count) >= 1:
        return int(source.preview_page_count)
    maximum = db.scalar(
        select(func.max(func.coalesce(SourceBlock.page_end, SourceBlock.page_start))).where(
            SourceBlock.source_document_id == source.id
        )
    )
    if maximum is None or int(maximum) < 1:
        return None
    return int(maximum)


def document_page_counts(db: Session, source_ids: list[str]) -> dict[str, int]:
    if not source_ids:
        return {}
    page_expr = func.max(func.coalesce(SourceBlock.page_end, SourceBlock.page_start))
    rows = db.execute(
        select(SourceBlock.source_document_id, page_expr)
        .where(SourceBlock.source_document_id.in_(source_ids))
        .group_by(SourceBlock.source_document_id)
    ).all()
    counts: dict[str, int] = {}
    for source_id, maximum in rows:
        if maximum is None or int(maximum) < 1:
            continue
        counts[str(source_id)] = int(maximum)
    return counts


def safe_document_summary(
    db: Session,
    source: SourceDocument,
    domain: Domain,
    *,
    query_eligible: bool,
    page_count: int | None = None,
    page_count_resolved: bool = False,
) -> dict[str, Any]:
    resolved_page_count = page_count if page_count_resolved else document_page_count(db, source)
    return {
        "ref": source.public_ref,
        "label": sanitize_original_filename(source.original_filename),
        "domain": {
            **safe_member_domain(domain),
            "queryEligible": query_eligible,
        },
        "contentType": PDF_CONTENT_TYPE,
        "previewKind": preview_kind_for_source(source),
        "pageCount": resolved_page_count,
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
    statement = select(SourceDocument).where(
        SourceDocument.domain_id.in_(list(domain_by_id.keys())),
        SourceDocument.state == SOURCE_STATE_PREPARED,
        SourceDocument.index_state == SOURCE_INDEX_STATE_READY,
    )
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

    matched_sources: list[SourceDocument] = []
    for source in candidates:
        domain = domain_by_id.get(source.domain_id)
        if domain is None:
            continue
        # Domains in domain_by_id are already available; only re-check frozen index identity.
        if not source_has_current_index_identity(source):
            continue
        label = sanitize_original_filename(source.original_filename)
        if not _matches_query(query=query, values=(label, source.content_type)):
            continue
        matched_sources.append(source)
        if len(matched_sources) >= limit + 1:
            break

    has_more = len(matched_sources) > limit
    page_sources = matched_sources[:limit]
    page_counts = document_page_counts(db, [source.id for source in page_sources])
    documents = [
        safe_document_summary(
            db,
            source,
            domain_by_id[source.domain_id],
            query_eligible=True,
            page_count=page_counts.get(source.id),
            page_count_resolved=True,
        )
        for source in page_sources
    ]
    return {
        "documents": documents,
        "nextCursor": _encode_cursor(page_sources[-1]) if has_more and page_sources else None,
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
    if preview_kind_for_source(source) != "pdf" or not source.preview_object_key:
        raise DocumentError(
            409,
            "document_preview_unavailable",
            "A governed PDF preview is not available for this document.",
        )

    etag = preview_etag(source)
    disposition = content_disposition_for_label(source.original_filename)
    total_size = int(source.preview_size_bytes or source.original_size_bytes)
    preview_key = source.preview_object_key
    effective_range = range_header
    if if_range is not None and if_range.strip() and if_range.strip() != etag:
        # Stale/mismatched If-Range → ignore Range and return full entity (HTTP semantics).
        effective_range = None

    byte_range = parse_byte_range(effective_range, total_size=total_size)
    storage = storage_from_settings(settings)
    try:
        if byte_range is None:
            body = storage.store.get(preview_key)
            return DocumentContentResult(
                status_code=200,
                body=body,
                total_size=total_size,
                etag=etag,
                content_disposition=disposition,
            )
        start, end = byte_range
        body = storage.store.get_range(preview_key, start, end)
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

    image_pages: set[int] = set()
    if block.kind == SOURCE_BLOCK_KIND_FIGURE and block.page_start is None:
        pages = db.scalars(
            select(SourceImage.page_number).where(
                SourceImage.source_block_id == block.id,
                SourceImage.page_number.is_not(None),
            )
        ).all()
        image_pages = {int(page) for page in pages if page is not None}

    anchor = project_persisted_evidence_anchor(block, image_pages=image_pages)
    page_map: dict[str, Any] | None = None
    if source.preview_page_map_object_key:
        try:
            raw_map = storage_from_settings(settings).store.get(source.preview_page_map_object_key)
            loaded = json.loads(raw_map.decode("utf-8"))
            if isinstance(loaded, dict):
                page_map = loaded
        except (ObjectStorageError, SourceStorageError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            page_map = None
    anchor = remap_anchor_through_page_map(
        anchor,
        page_map=page_map,
        page_count=document_page_count(db, source),
    )
    if evidence_ref_row.citation_label is None or anchor is None:
        raise DocumentError(410, "evidence_unavailable", "Evidence is no longer available.")

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
            "pageNumber": anchor["pageNumber"],
            "region": anchor.get("region"),
            "sectionLabel": anchor.get("sectionLabel"),
            "fallback": anchor["fallback"],
        },
    }
