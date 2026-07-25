from __future__ import annotations

import re
import threading
import time
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
from context_engine.services.domains import (
    DomainRuntimeController,
    controller_from_settings,
    domain_available,
)
from context_engine.services.indexing import (
    SourceIndexError,
    index_client_from_settings,
    source_is_query_eligible,
)

EVIDENCE_RESULT_FOUND = "evidence_found"
EVIDENCE_RESULT_NO_CONTEXT = "no_grounded_context"
MAX_EVIDENCE_EXCERPT_CHARS = 500
MAX_SOURCE_LABEL_CHARS = 255
_CE_BLOCK_TOKEN_RE = re.compile(r"\[CE_BLOCK[^\]]*\]")
_CE_BLOCK_MARKER_RE = re.compile(r"^\[CE_BLOCK id=([^\]\s]+) order=([1-9]\d*)\]$")
_RETRIEVAL_GATE_LOCK = threading.Lock()
_RETRIEVAL_GLOBAL_GATES: dict[int, threading.BoundedSemaphore] = {}
_RETRIEVAL_DOMAIN_GATES: dict[tuple[int, str], threading.BoundedSemaphore] = {}


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


@dataclass(frozen=True)
class ScopedRetrievalCandidate:
    """One private, bounded dependency candidate."""

    text: str


@dataclass(frozen=True)
class ScopedRetrievalResult:
    """Closed result envelope returned by the private retrieval port."""

    candidates: tuple[ScopedRetrievalCandidate, ...]


class ScopedRetrievalError(Exception):
    """Safe internal retrieval failure that never includes dependency content."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ScopedRetrievalPort(Protocol):
    def retrieve(
        self,
        domain: Domain,
        *,
        question: str,
        deadline: float,
    ) -> ScopedRetrievalResult: ...


# Kept as a source-compatible name until the P7 orchestration seam is rewired.
RetrievalClient = ScopedRetrievalPort


def _retrieval_failure(code: str) -> ScopedRetrievalError:
    messages = {
        "retrieval_saturated": "Scoped retrieval capacity is unavailable.",
        "retrieval_timeout": "Scoped retrieval timed out.",
        "retrieval_unavailable": "Scoped retrieval is unavailable.",
        "retrieval_malformed": "Scoped retrieval returned an invalid result.",
    }
    return ScopedRetrievalError(code, messages[code])


def _retrieval_gates(settings: Settings, domain_id: str) -> tuple[threading.BoundedSemaphore, threading.BoundedSemaphore]:
    global_limit = settings.retrieval_global_concurrency
    domain_limit = settings.retrieval_per_domain_concurrency
    with _RETRIEVAL_GATE_LOCK:
        global_gate = _RETRIEVAL_GLOBAL_GATES.setdefault(global_limit, threading.BoundedSemaphore(global_limit))
        domain_gate = _RETRIEVAL_DOMAIN_GATES.setdefault(
            (domain_limit, domain_id),
            threading.BoundedSemaphore(domain_limit),
        )
    return global_gate, domain_gate


def _acquire_before(gate: threading.BoundedSemaphore, deadline: float) -> bool:
    remaining = deadline - time.monotonic()
    return remaining > 0 and gate.acquire(timeout=remaining)


def normalize_scoped_retrieval_result(
    result: object,
    *,
    settings: Settings,
) -> tuple[ScopedRetrievalCandidate, ...]:
    if type(result) is not ScopedRetrievalResult or type(result.candidates) is not tuple:
        raise _retrieval_failure("retrieval_malformed")

    bounded = result.candidates[: settings.retrieval_max_candidates]
    aggregate_bytes = 0
    for candidate in bounded:
        if type(candidate) is not ScopedRetrievalCandidate or type(candidate.text) is not str:
            raise _retrieval_failure("retrieval_malformed")
        try:
            candidate_bytes = len(candidate.text.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise _retrieval_failure("retrieval_malformed") from exc
        aggregate_bytes += candidate_bytes
        if (
            candidate_bytes > settings.retrieval_max_candidate_bytes
            or aggregate_bytes > settings.retrieval_max_aggregate_bytes
        ):
            raise _retrieval_failure("retrieval_malformed")
    return bounded


def retrieve_bounded_candidates(
    *,
    settings: Settings,
    domain: Domain,
    question: str,
    client: ScopedRetrievalPort,
) -> tuple[ScopedRetrievalCandidate, ...]:
    if not isinstance(question, str) or not question.strip():
        raise _retrieval_failure("retrieval_malformed")

    deadline = time.monotonic() + settings.retrieval_timeout_seconds
    global_gate, domain_gate = _retrieval_gates(settings, domain.id)
    global_acquired = False
    domain_acquired = False
    try:
        global_acquired = _acquire_before(global_gate, deadline)
        if not global_acquired:
            raise _retrieval_failure("retrieval_saturated")
        domain_acquired = _acquire_before(domain_gate, deadline)
        if not domain_acquired:
            raise _retrieval_failure("retrieval_saturated")
        try:
            result = client.retrieve(domain, question=question, deadline=deadline)
        except ScopedRetrievalError as exc:
            if exc.code not in {
                "retrieval_saturated",
                "retrieval_timeout",
                "retrieval_unavailable",
                "retrieval_malformed",
            }:
                raise _retrieval_failure("retrieval_unavailable") from exc
            raise _retrieval_failure(exc.code) from exc
        except SourceIndexError as exc:
            code = "retrieval_timeout" if exc.code == "source_index_timeout" else "retrieval_unavailable"
            raise _retrieval_failure(code) from exc
        except TimeoutError as exc:
            raise _retrieval_failure("retrieval_timeout") from exc
        except Exception as exc:
            raise _retrieval_failure("retrieval_unavailable") from exc
        if time.monotonic() > deadline:
            raise _retrieval_failure("retrieval_timeout")
        return normalize_scoped_retrieval_result(result, settings=settings)
    finally:
        if domain_acquired:
            domain_gate.release()
        if global_acquired:
            global_gate.release()


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
    hits: tuple[ScopedRetrievalCandidate, ...] | list[ScopedRetrievalCandidate],
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
    hits: tuple[ScopedRetrievalCandidate, ...] | list[ScopedRetrievalCandidate],
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
        hits = retrieve_bounded_candidates(
            settings=settings,
            domain=domain,
            question=question,
            client=client,
        )
    except (SourceIndexError, ScopedRetrievalError) as exc:
        raise EvidenceRetrievalError(502, "domain_runtime_unavailable", "Knowledge domain runtime is unavailable.") from exc

    evidence = map_retrieval_hits_to_evidence(db, settings=settings, domain=domain, hits=hits, controller=controller)
    if not evidence:
        return {"result": EVIDENCE_RESULT_NO_CONTEXT, "evidence": []}
    return {
        "result": EVIDENCE_RESULT_FOUND,
        "evidence": [{"excerpt": item.excerpt, "sourceLabel": item.source_label} for item in evidence],
    }
