"""Authorized bounded Knowledge Domain graph projection (P12-07 U9)."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.adapters.domain_runtime_controller import DomainRuntimeController
from context_engine.config import Settings
from context_engine.models import DOMAIN_STATE_RUNNING, Domain
from context_engine.services.evidence import EvidenceRetrievalError, resolve_available_domain
from context_engine.services.indexing import LightRAGClientProtocol, SourceIndexError, index_client_from_settings

_GRAPH_MAX_NODES = 500
_GRAPH_MAX_EDGES = 2000
_GRAPH_TIMEOUT_SECONDS = 10
_GRAPH_MAX_UPSTREAM_BYTES = 2 * 1024 * 1024
_LABEL_Q_MIN = 2
_LABEL_Q_MAX = 160
_LABEL_LIMIT_MAX = 50
_SAFE_LABEL_RE = re.compile(r"^[\w][\w .,:;+/\-()']{0,254}$", re.UNICODE)
_CONTROL_OR_BIDI = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]"
)
_MARKUP_HINT = re.compile(r"[<>&`]|https?://", re.IGNORECASE)

TEST_GRAPH_REF_KEY = "ce-test-graph-ref-key-do-not-use-in-production!!"

_admission_lock = threading.Lock()
_global_gate: threading.BoundedSemaphore | None = None
_global_limit: int | None = None
_domain_gates: dict[str, _DomainGateEntry] = {}
_principal_gates: dict[str, _DomainGateEntry] = {}


class GraphServiceError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retry_after: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


@dataclass
class _DomainGateEntry:
    gate: threading.BoundedSemaphore
    refs: int
    limit: int


class _GraphClient(Protocol):
    def graph_snapshot(
        self,
        domain: Domain,
        *,
        label: str | None = None,
        max_nodes: int = 500,
        max_edges: int = 2000,
        deadline: float | None = None,
    ) -> dict[str, Any]: ...

    def graph_label_search(
        self,
        domain: Domain,
        *,
        q: str,
        limit: int = 50,
        deadline: float | None = None,
    ) -> dict[str, Any]: ...


def _graph_failure(
    code: str,
    *,
    status: int = 503,
    message: str | None = None,
    retry_after: int | None = None,
) -> GraphServiceError:
    defaults = {
        "graph_not_found": (404, "not_found", "Domain not found."),
        "graph_not_eligible": (
            409,
            "domain_not_query_eligible",
            "This knowledge domain is not currently available for queries.",
        ),
        "graph_refreshing": (
            409,
            "graph_refreshing",
            "The knowledge graph is refreshing after a corpus change.",
        ),
        "graph_validation": (422, "validation_error", "Graph request validation failed."),
        "graph_rate_limited": (429, "rate_limited", "Graph read capacity is temporarily limited."),
        "graph_capacity": (503, "capacity_unavailable", "Graph read capacity is temporarily unavailable."),
        "graph_dependency": (503, "dependency_unavailable", "Graph runtime is temporarily unavailable."),
    }
    mapped = defaults.get(code)
    if mapped is None:
        return GraphServiceError(status, code, message or "Graph request failed.", retry_after=retry_after)
    status_code, err_code, err_message = mapped
    return GraphServiceError(status_code, err_code, message or err_message, retry_after=retry_after)


def require_graph_ref_key(settings: Settings) -> str:
    key = (settings.graph_ref_key or "").strip()
    if not key:
        if settings.testing:
            return TEST_GRAPH_REF_KEY
        raise GraphServiceError(
            503,
            "dependency_unavailable",
            "Graph reference key is not configured.",
        )
    if len(key.encode("utf-8")) < 32:
        raise GraphServiceError(
            503,
            "dependency_unavailable",
            "Graph reference key is not configured.",
        )
    return key


def sanitize_graph_label(value: object) -> str | None:
    """Return a SafeLabel or None when the vendor string is unsafe/overlength."""
    if not isinstance(value, str):
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if _CONTROL_OR_BIDI.search(value) is not None:
        return None
    if _MARKUP_HINT.search(value) is not None:
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 255:
        return None
    if not _SAFE_LABEL_RE.fullmatch(cleaned):
        return None
    return cleaned


def opaque_graph_ref(*, key: str, domain_id: str, kind: str, private_id: str) -> str:
    digest = hmac.new(
        key.encode("utf-8"),
        f"graph-v1|{domain_id}|{kind}|{private_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]
    prefix = "gn" if kind == "node" else "ge" if kind == "edge" else "gx"
    return f"{prefix}_{digest}"


def reset_graph_admission_for_tests() -> None:
    """Drop process-local graph admission gates (tests only)."""
    global _global_gate, _global_limit
    with _admission_lock:
        _global_gate = None
        _global_limit = None
        _domain_gates.clear()
        _principal_gates.clear()


def _entry_for(
    store: dict[str, _DomainGateEntry],
    key: str,
    limit: int,
) -> _DomainGateEntry:
    existing = store.get(key)
    if existing is None or existing.limit != limit:
        entry = _DomainGateEntry(gate=threading.BoundedSemaphore(limit), refs=1, limit=limit)
        store[key] = entry
        return entry
    existing.refs += 1
    return existing


def _release_entry(store: dict[str, _DomainGateEntry], key: str, entry: _DomainGateEntry) -> None:
    with _admission_lock:
        current = store.get(key)
        if current is None or current is not entry:
            return
        current.refs -= 1
        if current.refs <= 0:
            store.pop(key, None)


def _try_acquire(gate: threading.BoundedSemaphore) -> bool:
    # Zero-length wait queue: never block waiting for a permit.
    return gate.acquire(blocking=False)


@contextmanager
def _graph_admission(
    settings: Settings,
    *,
    domain_id: str,
    principal_id: str,
) -> Iterator[float]:
    deadline = time.monotonic() + min(int(settings.graph_timeout_seconds), _GRAPH_TIMEOUT_SECONDS)
    with _admission_lock:
        global _global_gate, _global_limit
        global_limit = int(settings.graph_global_concurrency)
        if _global_gate is None or _global_limit != global_limit:
            _global_gate = threading.BoundedSemaphore(global_limit)
            _global_limit = global_limit
        global_gate = _global_gate
        principal_entry = _entry_for(
            _principal_gates,
            principal_id,
            int(settings.graph_per_principal_concurrency),
        )
        domain_entry = _entry_for(
            _domain_gates,
            domain_id,
            int(settings.graph_per_domain_concurrency),
        )

    principal_acquired = False
    domain_acquired = False
    global_acquired = False
    try:
        principal_acquired = _try_acquire(principal_entry.gate)
        if not principal_acquired:
            raise _graph_failure("graph_rate_limited", retry_after=1)
        domain_acquired = _try_acquire(domain_entry.gate)
        if not domain_acquired:
            raise _graph_failure("graph_capacity")
        global_acquired = _try_acquire(global_gate)
        if not global_acquired:
            raise _graph_failure("graph_capacity")
        yield deadline
    finally:
        if global_acquired:
            global_gate.release()
        if domain_acquired:
            domain_entry.gate.release()
        if principal_acquired:
            principal_entry.gate.release()
        _release_entry(_domain_gates, domain_id, domain_entry)
        _release_entry(_principal_gates, principal_id, principal_entry)


def _assert_generation_eligible(domain: Domain) -> None:
    if int(domain.graph_desired_generation) > int(domain.graph_applied_generation):
        raise _graph_failure("graph_refreshing")


def _map_evidence_error(exc: EvidenceRetrievalError) -> GraphServiceError:
    if exc.code == "domain_not_found":
        return _graph_failure("graph_not_found")
    if exc.code in {
        "domain_state_conflict",
        "domain_runtime_unavailable",
        "domain_no_eligible_sources",
    }:
        return _graph_failure("graph_not_eligible")
    if exc.code in {
        "domain_runtime_dependency_unavailable",
        "retrieval_dependency_unavailable",
    }:
        return _graph_failure("graph_dependency")
    return _graph_failure("graph_dependency")


def _upstream_bytes(raw: dict[str, Any]) -> int:
    try:
        return len(json.dumps(raw, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise _graph_failure("graph_dependency") from exc


def _compute_degrees(raw_edges: list[Any]) -> dict[str, int]:
    degrees: dict[str, int] = {}
    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source")
        target = edge.get("target")
        if source is None or target is None:
            continue
        source_id = str(source)
        target_id = str(target)
        degrees[source_id] = degrees.get(source_id, 0) + 1
        degrees[target_id] = degrees.get(target_id, 0) + 1
    return degrees


def _project_snapshot(
    *,
    settings: Settings,
    domain: Domain,
    raw: dict[str, Any],
) -> dict[str, Any]:
    key = require_graph_ref_key(settings)
    if _upstream_bytes(raw) > _GRAPH_MAX_UPSTREAM_BYTES:
        raise _graph_failure("graph_dependency")

    raw_nodes = raw.get("nodes") if isinstance(raw.get("nodes"), list) else []
    raw_edges = raw.get("edges") if isinstance(raw.get("edges"), list) else []
    truncated = bool(raw.get("truncated")) or len(raw_nodes) > _GRAPH_MAX_NODES or len(raw_edges) > _GRAPH_MAX_EDGES
    degrees = _compute_degrees(raw_edges)

    nodes_out: list[dict[str, Any]] = []
    id_to_ref: dict[str, str] = {}
    for node in raw_nodes[:_GRAPH_MAX_NODES]:
        if not isinstance(node, dict):
            continue
        # Drop unapproved bags: only allowlisted fields are read below.
        private_id = node.get("id")
        if private_id is None:
            continue
        label = sanitize_graph_label(node.get("label"))
        if label is None:
            continue
        kind = sanitize_graph_label(node.get("kind"))
        private_key = str(private_id)
        degree_raw = node.get("degree", degrees.get(private_key, 0))
        try:
            degree = int(degree_raw)
        except (TypeError, ValueError):
            degree = degrees.get(private_key, 0)
        if degree < 0:
            degree = 0
        ref = opaque_graph_ref(key=key, domain_id=domain.id, kind="node", private_id=private_key)
        id_to_ref[private_key] = ref
        nodes_out.append({"ref": ref, "label": label, "kind": kind, "degree": degree})

    edges_out: list[dict[str, Any]] = []
    for edge in raw_edges[:_GRAPH_MAX_EDGES]:
        if not isinstance(edge, dict):
            continue
        source = id_to_ref.get(str(edge.get("source")))
        target = id_to_ref.get(str(edge.get("target")))
        if not source or not target:
            continue
        private_edge = edge.get("id") or f"{edge.get('source')}:{edge.get('target')}:{edge.get('label')}"
        edges_out.append(
            {
                "ref": opaque_graph_ref(
                    key=key,
                    domain_id=domain.id,
                    kind="edge",
                    private_id=str(private_edge),
                ),
                "sourceRef": source,
                "targetRef": target,
                "label": sanitize_graph_label(edge.get("label")),
            }
        )

    if len(edges_out) > _GRAPH_MAX_EDGES:
        edges_out = edges_out[:_GRAPH_MAX_EDGES]
        truncated = True

    return {
        "domain": {"ref": domain.id, "name": domain.display_name},
        "nodes": nodes_out,
        "edges": edges_out,
        "truncated": truncated,
    }


def _project_labels(*, settings: Settings, domain: Domain, raw: dict[str, Any]) -> dict[str, Any]:
    key = require_graph_ref_key(settings)
    if _upstream_bytes(raw) > _GRAPH_MAX_UPSTREAM_BYTES:
        raise _graph_failure("graph_dependency")
    items_out: list[dict[str, Any]] = []
    for item in raw.get("items") or []:
        if not isinstance(item, dict):
            continue
        private_id = item.get("id")
        label = sanitize_graph_label(item.get("label"))
        if private_id is None or label is None:
            continue
        items_out.append(
            {
                "nodeRef": opaque_graph_ref(
                    key=key,
                    domain_id=domain.id,
                    kind="node",
                    private_id=str(private_id),
                ),
                "label": label,
                "kind": sanitize_graph_label(item.get("kind")),
            }
        )
    return {"items": items_out[:_LABEL_LIMIT_MAX]}


def _reauthorize_after_call(
    db: Session,
    *,
    domain_id: str,
    desired_before: int,
    applied_before: int,
    control_generation: int,
    runtime_instance_id: str,
) -> Domain:
    current = db.scalar(
        select(Domain)
        .where(Domain.id == domain_id)
        .execution_options(populate_existing=True)
    )
    if current is None:
        raise _graph_failure("graph_not_found")
    if (
        current.state != DOMAIN_STATE_RUNNING
        or int(current.control_generation) != control_generation
        or current.runtime_instance_id != runtime_instance_id
    ):
        raise _graph_failure("graph_not_eligible")
    if (
        int(current.graph_desired_generation) != desired_before
        or int(current.graph_applied_generation) != applied_before
        or int(current.graph_desired_generation) > int(current.graph_applied_generation)
    ):
        raise _graph_failure("graph_refreshing")
    return current


def _call_graph(
    client: _GraphClient | LightRAGClientProtocol,
    *,
    op: str,
    domain: Domain,
    deadline: float,
    label: str | None = None,
    q: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    try:
        if op == "snapshot":
            raw = client.graph_snapshot(  # type: ignore[call-arg]
                domain,
                label=label,
                max_nodes=_GRAPH_MAX_NODES,
                max_edges=_GRAPH_MAX_EDGES,
                deadline=deadline,
            )
        else:
            assert q is not None
            raw = client.graph_label_search(  # type: ignore[call-arg]
                domain,
                q=q,
                limit=limit,
                deadline=deadline,
            )
    except SourceIndexError as exc:
        if exc.code == "source_index_timeout":
            raise _graph_failure("graph_dependency") from exc
        raise _graph_failure("graph_dependency") from exc
    except TypeError:
        # Local/test clients may not accept deadline= yet.
        try:
            if op == "snapshot":
                raw = client.graph_snapshot(
                    domain,
                    label=label,
                    max_nodes=_GRAPH_MAX_NODES,
                    max_edges=_GRAPH_MAX_EDGES,
                )
            else:
                assert q is not None
                raw = client.graph_label_search(domain, q=q, limit=limit)
        except Exception as exc:  # noqa: BLE001 - closed dependency boundary
            raise _graph_failure("graph_dependency") from exc
    except Exception as exc:  # noqa: BLE001 - closed dependency boundary
        raise _graph_failure("graph_dependency") from exc
    if not isinstance(raw, dict):
        raise _graph_failure("graph_dependency")
    return raw


def get_domain_graph_snapshot(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    principal_id: str,
    label: str | None = None,
    controller: DomainRuntimeController | None = None,
    client: LightRAGClientProtocol | None = None,
) -> dict[str, Any]:
    if label is not None:
        if not isinstance(label, str):
            raise _graph_failure("graph_validation")
        cleaned = label.strip()
        if cleaned and sanitize_graph_label(cleaned) is None:
            raise _graph_failure("graph_validation")
        label = cleaned or None

    try:
        domain, controller = resolve_available_domain(
            db,
            settings=settings,
            domain_id=domain_id,
            controller=controller,
        )
    except EvidenceRetrievalError as exc:
        raise _map_evidence_error(exc) from exc

    _assert_generation_eligible(domain)
    desired_before = int(domain.graph_desired_generation)
    applied_before = int(domain.graph_applied_generation)
    control_generation = int(domain.control_generation)
    runtime_instance_id = domain.runtime_instance_id
    # End DB work before the private runtime call.
    db.commit()

    http = client or index_client_from_settings(settings, controller)
    with _graph_admission(settings, domain_id=domain.id, principal_id=principal_id) as deadline:
        if time.monotonic() > deadline:
            raise _graph_failure("graph_dependency")
        raw = _call_graph(http, op="snapshot", domain=domain, deadline=deadline, label=label)

    domain = _reauthorize_after_call(
        db,
        domain_id=domain.id,
        desired_before=desired_before,
        applied_before=applied_before,
        control_generation=control_generation,
        runtime_instance_id=runtime_instance_id,
    )
    applied_remote = raw.get("appliedGeneration")
    if applied_remote is not None:
        try:
            if int(applied_remote) != int(domain.graph_applied_generation):
                raise _graph_failure("graph_refreshing")
        except (TypeError, ValueError) as exc:
            raise _graph_failure("graph_dependency") from exc

    return _project_snapshot(settings=settings, domain=domain, raw=raw)


def search_domain_graph_labels(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    principal_id: str,
    q: str,
    limit: int = 50,
    controller: DomainRuntimeController | None = None,
    client: LightRAGClientProtocol | None = None,
) -> dict[str, Any]:
    if not isinstance(q, str):
        raise _graph_failure("graph_validation")
    needle = q.strip()
    if len(needle) < _LABEL_Q_MIN or len(needle) > _LABEL_Q_MAX:
        raise _graph_failure("graph_validation")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > _LABEL_LIMIT_MAX:
        raise _graph_failure("graph_validation")

    try:
        domain, controller = resolve_available_domain(
            db,
            settings=settings,
            domain_id=domain_id,
            controller=controller,
        )
    except EvidenceRetrievalError as exc:
        raise _map_evidence_error(exc) from exc

    _assert_generation_eligible(domain)
    desired_before = int(domain.graph_desired_generation)
    applied_before = int(domain.graph_applied_generation)
    control_generation = int(domain.control_generation)
    runtime_instance_id = domain.runtime_instance_id
    db.commit()

    http = client or index_client_from_settings(settings, controller)
    with _graph_admission(settings, domain_id=domain.id, principal_id=principal_id) as deadline:
        if time.monotonic() > deadline:
            raise _graph_failure("graph_dependency")
        raw = _call_graph(http, op="labels", domain=domain, deadline=deadline, q=needle, limit=limit)

    domain = _reauthorize_after_call(
        db,
        domain_id=domain.id,
        desired_before=desired_before,
        applied_before=applied_before,
        control_generation=control_generation,
        runtime_instance_id=runtime_instance_id,
    )
    return _project_labels(settings=settings, domain=domain, raw=raw)
