from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.models import (
    DOMAIN_OPERATION_ACTIVE_STATUSES,
    DOMAIN_STATE_RUNNING,
    Domain,
    DomainOperation,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.domains import DomainRuntimeController, controller_from_settings, domain_available
from context_engine.services.indexing import RawRetrievalHit, SourceIndexError, index_client_from_settings, source_is_query_eligible

EVIDENCE_RESULT_FOUND = "evidence_found"
EVIDENCE_RESULT_NO_CONTEXT = "no_grounded_context"
MAX_EVIDENCE_EXCERPT_CHARS = 500
MAX_SOURCE_LABEL_CHARS = 255
_CE_BLOCK_TOKEN_RE = re.compile(r"\[CE_BLOCK[^\]]*\]")
_CE_BLOCK_MARKER_RE = re.compile(r"^\[CE_BLOCK id=([^\]\s]+) order=([1-9]\d*)\]$")


class EvidenceRetrievalError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class CEBlockMarker:
    block_id: str
    source_order: int


@dataclass(frozen=True)
class EvidenceItem:
    excerpt: str
    source_label: str


@dataclass(frozen=True)
class InternalMappedEvidence:
    source_document_id: str
    source_block_id: str
    source_label: str
    excerpt: str
    retrieval_order: int


class RetrievalClient(Protocol):
    def retrieve(self, domain: Domain, *, question: str) -> tuple[RawRetrievalHit, ...]: ...


def parse_ce_block_marker(text: str) -> CEBlockMarker | None:
    tokens = _CE_BLOCK_TOKEN_RE.findall(text)
    if len(tokens) != 1:
        return None
    match = _CE_BLOCK_MARKER_RE.fullmatch(tokens[0])
    if match is None:
        return None
    return CEBlockMarker(block_id=match.group(1), source_order=int(match.group(2)))


def _safe_excerpt(markdown: str) -> str:
    excerpt = " ".join(markdown.split())
    if len(excerpt) <= MAX_EVIDENCE_EXCERPT_CHARS:
        return excerpt
    return excerpt[:MAX_EVIDENCE_EXCERPT_CHARS].rstrip()


def safe_evidence_item(block: SourceBlock, source: SourceDocument) -> EvidenceItem | None:
    excerpt = _safe_excerpt(block.canonical_markdown or "")
    if not excerpt:
        return None
    return EvidenceItem(excerpt=excerpt, source_label=source.original_filename[:MAX_SOURCE_LABEL_CHARS])


def _active_domain_operation_exists(db: Session, domain_id: str) -> bool:
    return (
        db.scalar(
            select(DomainOperation.id).where(
                DomainOperation.domain_id == domain_id,
                DomainOperation.status.in_(DOMAIN_OPERATION_ACTIVE_STATUSES),
            )
        )
        is not None
    )


def resolve_available_domain(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    controller: DomainRuntimeController | None = None,
) -> tuple[Domain, DomainRuntimeController]:
    domain = db.get(Domain, domain_id)
    if domain is None:
        raise EvidenceRetrievalError(404, "domain_not_found", "Domain not found.")
    if domain.state != DOMAIN_STATE_RUNNING or _active_domain_operation_exists(db, domain.id):
        raise EvidenceRetrievalError(409, "domain_state_conflict", "Domain lifecycle state does not allow this operation.")
    controller = controller or controller_from_settings(settings)
    if not domain_available(db, domain, controller):
        raise EvidenceRetrievalError(502, "domain_runtime_unavailable", "Knowledge domain runtime is unavailable.")
    return domain, controller


def eligible_sources_for_domain(
    db: Session,
    *,
    settings: Settings,
    domain: Domain,
    controller: DomainRuntimeController,
) -> list[SourceDocument]:
    sources = list(
        db.scalars(
            select(SourceDocument)
            .where(SourceDocument.domain_id == domain.id)
            .order_by(SourceDocument.created_at, SourceDocument.id)
        )
    )
    return [source for source in sources if source_is_query_eligible(db, source, domain, settings=settings, controller=controller)]


def map_retrieval_hits_to_evidence(
    db: Session,
    *,
    settings: Settings,
    domain: Domain,
    hits: tuple[RawRetrievalHit, ...] | list[RawRetrievalHit],
    controller: DomainRuntimeController | None = None,
) -> list[EvidenceItem]:
    return [
        EvidenceItem(excerpt=item.excerpt, source_label=item.source_label)
        for item in map_retrieval_hits_to_internal_evidence(
            db,
            settings=settings,
            domain=domain,
            hits=hits,
            controller=controller,
        )
    ]


def map_retrieval_hits_to_internal_evidence(
    db: Session,
    *,
    settings: Settings,
    domain: Domain,
    hits: tuple[RawRetrievalHit, ...] | list[RawRetrievalHit],
    controller: DomainRuntimeController | None = None,
) -> list[InternalMappedEvidence]:
    controller = controller or controller_from_settings(settings)
    evidence: list[InternalMappedEvidence] = []
    seen_blocks: set[str] = set()
    current_domain = db.get(Domain, domain.id)
    if current_domain is None or not domain_available(db, current_domain, controller):
        return evidence

    for hit in hits:
        marker = parse_ce_block_marker(hit.text)
        if marker is None or marker.block_id in seen_blocks:
            continue
        block = db.get(SourceBlock, marker.block_id)
        if block is None or block.domain_id != current_domain.id or block.source_order != marker.source_order:
            continue
        source = db.get(SourceDocument, block.source_document_id)
        if source is None or source.domain_id != current_domain.id:
            continue
        if not source_is_query_eligible(db, source, current_domain, settings=settings, controller=controller):
            continue
        item = safe_evidence_item(block, source)
        if item is None:
            continue
        seen_blocks.add(block.id)
        evidence.append(
            InternalMappedEvidence(
                source_document_id=source.id,
                source_block_id=block.id,
                source_label=item.source_label,
                excerpt=item.excerpt,
                retrieval_order=len(evidence) + 1,
            )
        )
    return evidence


def retrieve_scoped_evidence(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    question: str,
    client: RetrievalClient | None = None,
    controller: DomainRuntimeController | None = None,
) -> dict[str, object]:
    domain, controller = resolve_available_domain(db, settings=settings, domain_id=domain_id, controller=controller)
    if not eligible_sources_for_domain(db, settings=settings, domain=domain, controller=controller):
        raise EvidenceRetrievalError(
            409,
            "domain_no_eligible_sources",
            "This knowledge domain has no eligible sources for retrieval.",
        )

    db.commit()
    client = client or index_client_from_settings(settings, controller)
    try:
        hits = client.retrieve(domain, question=question)
    except SourceIndexError as exc:
        raise EvidenceRetrievalError(502, "domain_runtime_unavailable", "Knowledge domain runtime is unavailable.") from exc

    evidence = map_retrieval_hits_to_evidence(db, settings=settings, domain=domain, hits=hits, controller=controller)
    if not evidence:
        return {"result": EVIDENCE_RESULT_NO_CONTEXT, "evidence": []}
    return {
        "result": EVIDENCE_RESULT_FOUND,
        "evidence": [{"excerpt": item.excerpt, "sourceLabel": item.source_label} for item in evidence],
    }
