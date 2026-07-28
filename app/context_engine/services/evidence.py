from __future__ import annotations

import json
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import exists, select, tuple_
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.models import (
    DOMAIN_OPERATION_ACTIVE_STATUSES,
    DOMAIN_STATE_RUNNING,
    SOURCE_BLOCK_KIND_FIGURE,
    SOURCE_INDEX_STATE_READY,
    SOURCE_STATE_PREPARED,
    Domain,
    DomainOperation,
    SourceBlock,
    SourceDocument,
    SourceImage,
)
from context_engine.services.domains import (
    DomainRuntimeController,
    controller_from_settings,
)
from context_engine.services.indexing import (
    LIGHTRAG_HANDOFF_SCHEMA_VERSION,
    SourceIndexError,
    index_client_from_settings,
    render_blocks_to_lightrag_handoff,
    source_has_current_index_identity,
)
from context_engine.services.sources import sanitize_original_filename

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
    kind: str
    document_ref: str
    document_label: str
    anchor: dict[str, object] | None
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
class InternalScopedRetrievalResult:
    had_eligible_sources: bool
    evidence: tuple[InternalMappedEvidence, ...] = ()


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


def _ensure_before_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise _retrieval_failure("retrieval_timeout")


@contextmanager
def _retrieval_admission(settings: Settings, domain_id: str):
    deadline = time.monotonic() + settings.retrieval_timeout_seconds
    global_gate, domain_key, domain_entry = _retrieval_gates(settings, domain_id)
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
        yield deadline
    finally:
        if domain_acquired:
            domain_gate.release()
        if global_acquired:
            global_gate.release()
        _release_domain_gate_reference(domain_key, domain_entry)


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
        except UnicodeEncodeError:
            candidate_bytes = None
        if candidate_bytes is None:
            raise _retrieval_failure("retrieval_malformed")
        aggregate_bytes += candidate_bytes
        if (
            candidate_bytes > settings.retrieval_max_candidate_bytes
            or aggregate_bytes > settings.retrieval_max_aggregate_bytes
        ):
            raise _retrieval_failure("retrieval_malformed")
    return bounded


def _call_scoped_retrieval(
    client: ScopedRetrievalPort,
    domain: Domain,
    *,
    question: str,
    deadline: float,
) -> tuple[object | None, str | None]:
    try:
        return client.retrieve(domain, question=question, deadline=deadline), None
    except ScopedRetrievalError as exc:
        if exc.code in {
            "retrieval_saturated",
            "retrieval_timeout",
            "retrieval_unavailable",
            "retrieval_malformed",
        }:
            return None, exc.code
        return None, "retrieval_unavailable"
    except SourceIndexError as exc:
        code = "retrieval_timeout" if exc.code == "source_index_timeout" else "retrieval_unavailable"
        return None, code
    except TimeoutError:
        return None, "retrieval_timeout"
    except Exception:  # noqa: BLE001 - dependency failures cross a closed safe-error boundary
        return None, "retrieval_unavailable"


def retrieve_bounded_candidates(
    *,
    settings: Settings,
    domain: Domain,
    question: str,
    client: ScopedRetrievalPort,
) -> tuple[ScopedRetrievalCandidate, ...]:
    if not isinstance(question, str) or not question.strip():
        raise _retrieval_failure("retrieval_malformed")

    with _retrieval_admission(settings, domain.id) as deadline:
        return _retrieve_bounded_candidates_before_deadline(
            settings=settings,
            domain=domain,
            question=question,
            client=client,
            deadline=deadline,
        )


def _retrieve_bounded_candidates_before_deadline(
    *,
    settings: Settings,
    domain: Domain,
    question: str,
    client: ScopedRetrievalPort,
    deadline: float,
) -> tuple[ScopedRetrievalCandidate, ...]:
    result, failure_code = _call_scoped_retrieval(
        client,
        domain,
        question=question,
        deadline=deadline,
    )
    if failure_code is not None:
        raise _retrieval_failure(failure_code)
    _ensure_before_deadline(deadline)
    return normalize_scoped_retrieval_result(result, settings=settings)


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
    return EvidenceItem(
        excerpt=excerpt,
        source_label=sanitize_original_filename(source.original_filename)[:MAX_SOURCE_LABEL_CHARS],
    )


def safe_section_label(section_path: str | None) -> str | None:
    if not section_path:
        return None
    raw = section_path.strip()
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list) and parsed:
            raw = str(parsed[-1])
    label = " ".join(raw.split())[:160].rstrip()
    return label or None


def resolve_block_page_number(block: SourceBlock, *, image_pages: set[int]) -> int | None:
    page_number = block.page_start
    if page_number is None and block.kind == SOURCE_BLOCK_KIND_FIGURE and len(image_pages) == 1:
        page_number = next(iter(image_pages))
    return page_number


def _block_region_dto(block: SourceBlock) -> dict[str, float] | None:
    if (
        block.region_x is None
        or block.region_y is None
        or block.region_width is None
        or block.region_height is None
    ):
        return None
    return {
        "x": float(block.region_x),
        "y": float(block.region_y),
        "width": float(block.region_width),
        "height": float(block.region_height),
    }


def project_persisted_evidence_anchor(
    block: SourceBlock,
    *,
    image_pages: set[int],
) -> dict[str, object] | None:
    """Location/turn/SSE anchor projection — may include optional region."""
    page_number = resolve_block_page_number(block, image_pages=image_pages)
    if page_number is None:
        return None
    section_label = safe_section_label(block.section_path)
    region = _block_region_dto(block)
    if region is not None:
        fallback = "region"
    elif section_label:
        fallback = "section"
    else:
        fallback = "page"
    anchor: dict[str, object] = {
        "pageNumber": page_number,
        "region": region,
        "fallback": fallback,
    }
    if section_label:
        anchor["sectionLabel"] = section_label
    return anchor


def _evidence_anchor(
    block: SourceBlock,
    *,
    image_pages: set[int],
) -> dict[str, object] | None:
    """Retrieval-list anchor — page/section only; never includes region."""
    page_number = resolve_block_page_number(block, image_pages=image_pages)
    if page_number is None:
        return None
    section_label = safe_section_label(block.section_path)
    anchor: dict[str, object] = {
        "pageNumber": page_number,
        "fallback": "section" if section_label else "page",
    }
    if section_label:
        anchor["sectionLabel"] = section_label
    return anchor


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


def _assert_runtime_healthy(controller: DomainRuntimeController, domain: Domain) -> None:
    try:
        health = controller.health(domain)
    except Exception:  # noqa: BLE001 - normalize arbitrary controller failures
        raise EvidenceRetrievalError(
            503,
            "domain_runtime_dependency_unavailable",
            "Knowledge domain runtime health is unavailable.",
        ) from None
    if not health.healthy:
        raise EvidenceRetrievalError(
            502,
            "domain_runtime_unavailable",
            "Knowledge domain runtime is unavailable.",
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
    _assert_runtime_healthy(controller, domain)
    return domain, controller


def eligible_sources_for_domain(
    db: Session,
    *,
    domain: Domain,
) -> list[SourceDocument]:
    rows = db.execute(
        select(SourceDocument, SourceBlock)
        .outerjoin(SourceBlock, SourceBlock.source_document_id == SourceDocument.id)
        .where(
            SourceDocument.domain_id == domain.id,
            SourceDocument.state == SOURCE_STATE_PREPARED,
            SourceDocument.index_state == SOURCE_INDEX_STATE_READY,
            SourceDocument.index_request_id.is_not(None),
            SourceDocument.index_content_hash.is_not(None),
        )
        .order_by(
            SourceDocument.created_at,
            SourceDocument.id,
            SourceBlock.source_order,
            SourceBlock.id,
        )
        .execution_options(populate_existing=True)
    ).all()
    sources_with_blocks: dict[str, tuple[SourceDocument, list[SourceBlock]]] = {}
    for source, block in rows:
        current = sources_with_blocks.setdefault(source.id, (source, []))
        if block is not None:
            current[1].append(block)

    eligible: list[SourceDocument] = []
    for source, blocks in sources_with_blocks.values():
        if not source_has_current_index_identity(source):
            continue
        try:
            rendered = render_blocks_to_lightrag_handoff(
                source_id=source.id,
                original_sha256=source.original_sha256,
                blocks=blocks,
            )
        except SourceIndexError:
            continue
        if rendered.content_hash == source.index_content_hash:
            eligible.append(source)
    return eligible


def freeze_retrieval_scope(
    domain: Domain,
    sources: list[SourceDocument],
) -> FrozenRetrievalScope:
    frozen_sources: list[FrozenSourceIdentity] = []
    for source in sources:
        if (identity := _frozen_source_identity(source)) is not None:
            frozen_sources.append(identity)
    return FrozenRetrievalScope(
        domain_id=domain.id,
        control_generation=domain.control_generation,
        runtime_instance_id=domain.runtime_instance_id,
        sources=tuple(frozen_sources),
    )


def _frozen_source_identity(source: SourceDocument) -> FrozenSourceIdentity | None:
    if not source.index_request_id or not source.index_content_hash:
        return None
    return FrozenSourceIdentity(
        source_document_id=source.id,
        preparation_generation=source.preparation_generation,
        index_generation=source.index_generation,
        index_request_id=source.index_request_id,
        index_content_hash=source.index_content_hash,
        original_sha256=source.original_sha256,
    )


def reauthorize_frozen_retrieval_scope(
    db: Session,
    *,
    frozen_scope: FrozenRetrievalScope,
    controller: DomainRuntimeController,
) -> None:
    current_domain = db.scalar(
        select(Domain)
        .where(
            Domain.id == frozen_scope.domain_id,
            Domain.state == DOMAIN_STATE_RUNNING,
            Domain.control_generation == frozen_scope.control_generation,
            Domain.runtime_instance_id == frozen_scope.runtime_instance_id,
        )
        .execution_options(populate_existing=True)
    )
    if current_domain is None or _active_domain_operation_exists(db, frozen_scope.domain_id):
        raise EvidenceRetrievalError(
            409,
            "domain_state_conflict",
            "Domain lifecycle state does not allow this operation.",
        )

    _assert_runtime_healthy(controller, current_domain)

    frozen_source_ids = tuple(source.source_document_id for source in frozen_scope.sources)
    eligible_sources = db.scalars(
        select(SourceDocument)
        .where(
            SourceDocument.id.in_(frozen_source_ids),
            SourceDocument.domain_id == current_domain.id,
            SourceDocument.state == SOURCE_STATE_PREPARED,
            SourceDocument.index_state == SOURCE_INDEX_STATE_READY,
            SourceDocument.index_request_id.is_not(None),
            SourceDocument.index_content_hash.is_not(None),
        )
        .execution_options(populate_existing=True)
    ).all()
    current_identities = {
        identity.source_document_id: identity
        for source in eligible_sources
        if source_has_current_index_identity(source)
        if (identity := _frozen_source_identity(source)) is not None
    }
    if not current_identities or any(
        current_identities.get(frozen.source_document_id) != frozen for frozen in frozen_scope.sources
    ):
        raise EvidenceRetrievalError(
            409,
            "domain_no_eligible_sources",
            "This knowledge domain has no eligible sources for retrieval.",
        )


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
        select(SourceBlock, SourceDocument, SourceImage.page_number)
        .join(SourceDocument, SourceDocument.id == SourceBlock.source_document_id)
        .join(Domain, Domain.id == SourceDocument.domain_id)
        .outerjoin(SourceImage, SourceImage.source_block_id == SourceBlock.id)
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
    current_by_block_id: dict[str, tuple[SourceBlock, SourceDocument, set[int]]] = {}
    for block, source, image_page in current_rows:
        current = current_by_block_id.setdefault(block.id, (block, source, set()))
        if image_page is not None:
            current[2].add(image_page)

    evidence: list[InternalMappedEvidence] = []
    seen_blocks: set[str] = set()
    for marker in parsed_markers:
        if marker.block_id in seen_blocks:
            continue
        current = current_by_block_id.get(marker.block_id)
        if current is None:
            continue
        block, source, image_pages = current
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
                kind=block.kind,
                document_ref=source.public_ref,
                document_label=sanitize_original_filename(source.original_filename),
                anchor=_evidence_anchor(block, image_pages=image_pages),
                retrieval_order=len(evidence) + 1,
            )
        )
    return evidence


def retrieve_internal_scoped_evidence(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    question: str,
    client: ScopedRetrievalPort | None = None,
    controller: DomainRuntimeController | None = None,
) -> InternalScopedRetrievalResult:
    if not isinstance(question, str) or not question.strip():
        raise _retrieval_failure("retrieval_malformed")

    with _retrieval_admission(settings, domain_id) as deadline:
        domain, controller = resolve_available_domain(
            db,
            settings=settings,
            domain_id=domain_id,
            controller=controller,
        )
        _ensure_before_deadline(deadline)
        eligible_sources = eligible_sources_for_domain(db, domain=domain)
        _ensure_before_deadline(deadline)
        if not eligible_sources:
            return InternalScopedRetrievalResult(had_eligible_sources=False)

        frozen_scope = freeze_retrieval_scope(domain, eligible_sources)
        db.commit()
        client = client or index_client_from_settings(settings, controller)
        hits = _retrieve_bounded_candidates_before_deadline(
            settings=settings,
            domain=domain,
            question=question,
            client=client,
            deadline=deadline,
        )
        mapped_evidence = tuple(
            map_retrieval_hits_to_internal_evidence(
                db,
                hits=hits,
                frozen_scope=frozen_scope,
            )
        )
        _ensure_before_deadline(deadline)
        reauthorize_frozen_retrieval_scope(
            db,
            frozen_scope=frozen_scope,
            controller=controller,
        )
        _ensure_before_deadline(deadline)
        return InternalScopedRetrievalResult(
            had_eligible_sources=True,
            evidence=mapped_evidence,
        )


def retrieve_scoped_evidence(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    question: str,
    client: ScopedRetrievalPort | None = None,
    controller: DomainRuntimeController | None = None,
) -> dict[str, object]:
    try:
        result = retrieve_internal_scoped_evidence(
            db,
            settings=settings,
            domain_id=domain_id,
            question=question,
            client=client,
            controller=controller,
        )
    except ScopedRetrievalError as exc:
        if exc.code == "retrieval_saturated":
            raise EvidenceRetrievalError(
                503,
                "retrieval_capacity_unavailable",
                "Scoped retrieval capacity is unavailable.",
            ) from exc
        raise EvidenceRetrievalError(
            503,
            "retrieval_dependency_unavailable",
            "Scoped retrieval dependency is unavailable.",
        ) from exc
    if not result.had_eligible_sources:
        raise EvidenceRetrievalError(
            409,
            "domain_no_eligible_sources",
            "This knowledge domain has no eligible sources for retrieval.",
        )
    evidence = result.evidence
    if not evidence:
        return {"result": EVIDENCE_RESULT_NO_CONTEXT, "evidence": []}
    return {
        "result": EVIDENCE_RESULT_FOUND,
        "evidence": [
            {
                "citationLabel": f"[{index}]",
                "sourceLabel": item.source_label,
                "excerpt": item.excerpt,
                "kind": item.kind,
                "documentRef": item.document_ref,
                "documentLabel": item.document_label,
                "anchor": item.anchor,
            }
            for index, item in enumerate(evidence, start=1)
        ],
    }
