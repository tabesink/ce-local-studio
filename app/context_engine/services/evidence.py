from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import exists, select, tuple_
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.models import (
    DOMAIN_OPERATION_ACTIVE_STATUSES,
    DOMAIN_STATE_RUNNING,
    SOURCE_INDEX_STATE_READY,
    SOURCE_STATE_PREPARED,
    Domain,
    DomainOperation,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.domains import (
    DomainRuntimeController,
    controller_from_settings,
)
from context_engine.services.indexing import (
    LIGHTRAG_HANDOFF_SCHEMA_VERSION,
    SourceIndexError,
    index_client_from_settings,
    source_has_current_index_identity,
)

EVIDENCE_RESULT_FOUND = "evidence_found"
EVIDENCE_RESULT_NO_CONTEXT = "no_grounded_context"
MAX_EVIDENCE_EXCERPT_CHARS = 500
MAX_SOURCE_LABEL_CHARS = 255
_RESERVED_PROVENANCE_TOKEN_RE = re.compile(r"\[CE_(?:SOURCE|BLOCK)\b")
_CE_BLOCK_MARKER_RE = re.compile(
    rf"^\[CE_BLOCK schema={re.escape(LIGHTRAG_HANDOFF_SCHEMA_VERSION)} "
    r"source_id=([^\]\s]+) source_sha256=([^\]\s]{64}) "
    r"block_id=([^\]\s]+) order=([1-9]\d*)\]$"
)
_RETRIEVAL_GATE_LOCK = threading.Lock()
_RETRIEVAL_GLOBAL_GATES: dict[int, threading.BoundedSemaphore] = {}


@dataclass
class _DomainGateEntry:
    gate: threading.BoundedSemaphore
    users: int = 0


_RETRIEVAL_DOMAIN_GATES: dict[tuple[int, str], _DomainGateEntry] = {}


class EvidenceRetrievalError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class CEBlockMarker:
    source_id: str
    source_sha256: str
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
class FrozenSourceIdentity:
    source_document_id: str
    preparation_generation: int
    index_generation: int
    index_request_id: str
    index_content_hash: str
    original_sha256: str


@dataclass(frozen=True)
class FrozenRetrievalScope:
    domain_id: str
    control_generation: int
    runtime_instance_id: str
    sources: tuple[FrozenSourceIdentity, ...]


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


def _retrieval_failure(code: str) -> ScopedRetrievalError:
    messages = {
        "retrieval_saturated": "Scoped retrieval capacity is unavailable.",
        "retrieval_timeout": "Scoped retrieval timed out.",
        "retrieval_unavailable": "Scoped retrieval is unavailable.",
        "retrieval_malformed": "Scoped retrieval returned an invalid result.",
    }
    return ScopedRetrievalError(code, messages[code])


def _retrieval_gates(
    settings: Settings,
    domain_id: str,
) -> tuple[threading.BoundedSemaphore, tuple[int, str], _DomainGateEntry]:
    global_limit = settings.retrieval_global_concurrency
    domain_limit = settings.retrieval_per_domain_concurrency
    domain_key = (domain_limit, domain_id)
    with _RETRIEVAL_GATE_LOCK:
        global_gate = _RETRIEVAL_GLOBAL_GATES.setdefault(global_limit, threading.BoundedSemaphore(global_limit))
        domain_entry = _RETRIEVAL_DOMAIN_GATES.setdefault(
            domain_key,
            _DomainGateEntry(threading.BoundedSemaphore(domain_limit)),
        )
        domain_entry.users += 1
    return global_gate, domain_key, domain_entry


def _release_domain_gate_reference(domain_key: tuple[int, str], domain_entry: _DomainGateEntry) -> None:
    with _RETRIEVAL_GATE_LOCK:
        domain_entry.users -= 1
        if domain_entry.users == 0 and _RETRIEVAL_DOMAIN_GATES.get(domain_key) is domain_entry:
            del _RETRIEVAL_DOMAIN_GATES[domain_key]


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
    global_gate, domain_key, domain_entry = _retrieval_gates(settings, domain.id)
    domain_gate = domain_entry.gate
    global_acquired = False
    domain_acquired = False
    try:
        domain_acquired = _acquire_before(domain_gate, deadline)
        if not domain_acquired:
            raise _retrieval_failure("retrieval_saturated")
        global_acquired = _acquire_before(global_gate, deadline)
        if not global_acquired:
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
        _release_domain_gate_reference(domain_key, domain_entry)


def parse_ce_block_marker(text: str) -> CEBlockMarker | None:
    first_line, separator, body = text.partition("\n")
    if not separator or _RESERVED_PROVENANCE_TOKEN_RE.search(body):
        return None
    match = _CE_BLOCK_MARKER_RE.fullmatch(first_line)
    if match is None:
        return None
    return CEBlockMarker(
        source_id=match.group(1),
        source_sha256=match.group(2),
        block_id=match.group(3),
        source_order=int(match.group(4)),
    )


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
    if not controller.health(domain).healthy:
        raise EvidenceRetrievalError(502, "domain_runtime_unavailable", "Knowledge domain runtime is unavailable.")
    return domain, controller


def eligible_sources_for_domain(
    db: Session,
    *,
    domain: Domain,
) -> list[SourceDocument]:
    sources = list(
        db.scalars(
            select(SourceDocument)
            .where(
                SourceDocument.domain_id == domain.id,
                SourceDocument.state == SOURCE_STATE_PREPARED,
                SourceDocument.index_state == SOURCE_INDEX_STATE_READY,
                SourceDocument.index_request_id.is_not(None),
                SourceDocument.index_content_hash.is_not(None),
            )
            .order_by(SourceDocument.created_at, SourceDocument.id)
        )
    )
    return [source for source in sources if source_has_current_index_identity(source)]


def freeze_retrieval_scope(
    domain: Domain,
    sources: list[SourceDocument],
) -> FrozenRetrievalScope:
    frozen_sources: list[FrozenSourceIdentity] = []
    for source in sources:
        if not source.index_request_id or not source.index_content_hash:
            continue
        frozen_sources.append(
            FrozenSourceIdentity(
                source_document_id=source.id,
                preparation_generation=source.preparation_generation,
                index_generation=source.index_generation,
                index_request_id=source.index_request_id,
                index_content_hash=source.index_content_hash,
                original_sha256=source.original_sha256,
            )
        )
    return FrozenRetrievalScope(
        domain_id=domain.id,
        control_generation=domain.control_generation,
        runtime_instance_id=domain.runtime_instance_id,
        sources=tuple(frozen_sources),
    )


def map_retrieval_hits_to_evidence(
    db: Session,
    *,
    hits: tuple[ScopedRetrievalCandidate, ...] | list[ScopedRetrievalCandidate],
    frozen_scope: FrozenRetrievalScope,
) -> list[EvidenceItem]:
    return [
        EvidenceItem(excerpt=item.excerpt, source_label=item.source_label)
        for item in map_retrieval_hits_to_internal_evidence(
            db,
            hits=hits,
            frozen_scope=frozen_scope,
        )
    ]


def map_retrieval_hits_to_internal_evidence(
    db: Session,
    *,
    hits: tuple[ScopedRetrievalCandidate, ...] | list[ScopedRetrievalCandidate],
    frozen_scope: FrozenRetrievalScope,
) -> list[InternalMappedEvidence]:
    if not frozen_scope.sources:
        return []

    parsed_markers: list[CEBlockMarker] = []
    for hit in hits:
        marker = parse_ce_block_marker(hit.text)
        if marker is None:
            continue
        parsed_markers.append(marker)
    if not parsed_markers:
        return []

    candidate_source_ids = {marker.source_id for marker in parsed_markers}
    frozen_rows = [
        (
            frozen.source_document_id,
            frozen.preparation_generation,
            frozen.index_generation,
            frozen.index_request_id,
            frozen.index_content_hash,
            frozen.original_sha256,
        )
        for frozen in frozen_scope.sources
        if frozen.source_document_id in candidate_source_ids
    ]
    if not frozen_rows:
        return []
    block_ids = tuple({marker.block_id for marker in parsed_markers})
    active_operation = exists(
        select(DomainOperation.id).where(
            DomainOperation.domain_id == Domain.id,
            DomainOperation.status.in_(DOMAIN_OPERATION_ACTIVE_STATUSES),
        )
    )
    statement = (
        select(SourceBlock, SourceDocument)
        .join(SourceDocument, SourceDocument.id == SourceBlock.source_document_id)
        .join(Domain, Domain.id == SourceDocument.domain_id)
        .where(
            Domain.id == frozen_scope.domain_id,
            Domain.state == DOMAIN_STATE_RUNNING,
            Domain.control_generation == frozen_scope.control_generation,
            Domain.runtime_instance_id == frozen_scope.runtime_instance_id,
            ~active_operation,
            SourceDocument.domain_id == frozen_scope.domain_id,
            SourceDocument.state == SOURCE_STATE_PREPARED,
            SourceDocument.index_state == SOURCE_INDEX_STATE_READY,
            tuple_(
                SourceDocument.id,
                SourceDocument.preparation_generation,
                SourceDocument.index_generation,
                SourceDocument.index_request_id,
                SourceDocument.index_content_hash,
                SourceDocument.original_sha256,
            ).in_(frozen_rows),
            SourceBlock.domain_id == frozen_scope.domain_id,
            SourceBlock.id.in_(block_ids),
        )
    )
    current_rows = db.execute(statement).all()
    current_by_block_id = {block.id: (block, source) for block, source in current_rows}

    evidence: list[InternalMappedEvidence] = []
    seen_blocks: set[str] = set()
    for marker in parsed_markers:
        if marker.block_id in seen_blocks:
            continue
        current = current_by_block_id.get(marker.block_id)
        if current is None:
            continue
        block, source = current
        if (
            marker.source_id != source.id
            or marker.source_sha256 != source.original_sha256
            or marker.source_order != block.source_order
        ):
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
    client: ScopedRetrievalPort | None = None,
    controller: DomainRuntimeController | None = None,
) -> dict[str, object]:
    domain, controller = resolve_available_domain(db, settings=settings, domain_id=domain_id, controller=controller)
    eligible_sources = eligible_sources_for_domain(db, domain=domain)
    if not eligible_sources:
        raise EvidenceRetrievalError(
            409,
            "domain_no_eligible_sources",
            "This knowledge domain has no eligible sources for retrieval.",
        )

    frozen_scope = freeze_retrieval_scope(domain, eligible_sources)
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

    evidence = map_retrieval_hits_to_evidence(
        db,
        hits=hits,
        frozen_scope=frozen_scope,
    )
    if not evidence:
        return {"result": EVIDENCE_RESULT_NO_CONTEXT, "evidence": []}
    return {
        "result": EVIDENCE_RESULT_FOUND,
        "evidence": [{"excerpt": item.excerpt, "sourceLabel": item.source_label} for item in evidence],
    }
