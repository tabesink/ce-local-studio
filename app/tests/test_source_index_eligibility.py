from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from context_engine.api.routes import _source_index_api_error
from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    DOMAIN_STATE_RUNNING,
    DOMAIN_STATE_STOPPED,
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_QUEUED,
    SOURCE_INDEX_STATE_READY,
    SOURCE_INDEX_STATE_SUBMITTING,
    SOURCE_STATE_PENDING,
    SOURCE_STATE_PREPARED,
    Domain,
    SourceDocument,
)
from context_engine.services.indexing import (
    SOURCE_INDEX_UNCERTAIN_CODE,
    IndexReadiness,
    IndexSubmitResult,
    SourceIndexError,
    SourceIndexWorker,
    compute_index_request_id,
    mark_index_uncertain_if_current,
    schedule_index_poll_backoff,
    source_is_query_eligible,
)


@dataclass
class _Controller:
    healthy: bool = True

    def health(self, domain: Domain, **_kwargs):  # noqa: ANN003
        return MagicMock(healthy=self.healthy, outcome="succeeded")


def _domain(*, state: str = DOMAIN_STATE_RUNNING) -> Domain:
    return Domain(
        id="domain-index-elig",
        display_name="Eligibility",
        state=state,
        embedding_profile_id="openai-embedding-default",
        runtime_instance_id="runtime-1",
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 0, 0),
    )


def _source(
    domain: Domain,
    *,
    state: str = SOURCE_STATE_PREPARED,
    index_state: str = SOURCE_INDEX_STATE_READY,
    generation: int = 1,
    content_hash: str = "c" * 64,
) -> SourceDocument:
    source_id = str(uuid4())
    return SourceDocument(
        id=source_id,
        public_ref=f"doc_{uuid4().hex[:16]}",
        domain_id=domain.id,
        original_filename="manual.pdf",
        content_type="application/pdf",
        original_sha256="a" * 64,
        original_size_bytes=32,
        original_object_key=f"obj/{uuid4().hex}",
        state=state,
        parser_kind="docling",
        preparation_generation=1,
        index_state=index_state,
        index_generation=generation,
        index_content_hash=content_hash,
        index_request_id=compute_index_request_id(source_id, generation, content_hash),
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 0, 0),
    )


def test_a08_source_query_eligible_only_when_ready_with_current_identity() -> None:
    domain = _domain()
    db = MagicMock()
    db.scalar.return_value = None  # no active domain operation
    controller = _Controller(healthy=True)

    ready = _source(domain, index_state=SOURCE_INDEX_STATE_READY)
    assert source_is_query_eligible(db, ready, domain, controller=controller) is True

    processing = _source(domain, index_state=SOURCE_INDEX_STATE_ACCEPTED)
    assert source_is_query_eligible(db, processing, domain, controller=controller) is False

    queued = _source(domain, index_state=SOURCE_INDEX_STATE_QUEUED)
    assert source_is_query_eligible(db, queued, domain, controller=controller) is False

    pending = _source(domain, state=SOURCE_STATE_PENDING, index_state=SOURCE_INDEX_STATE_READY)
    assert source_is_query_eligible(db, pending, domain, controller=controller) is False

    stale = _source(domain, index_state=SOURCE_INDEX_STATE_READY)
    stale.index_request_id = "mismatched-request"
    assert source_is_query_eligible(db, stale, domain, controller=controller) is False

    stopped = _domain(state=DOMAIN_STATE_STOPPED)
    assert source_is_query_eligible(db, ready, stopped, controller=controller) is False

    unhealthy = _Controller(healthy=False)
    assert source_is_query_eligible(db, ready, domain, controller=unhealthy) is False


def test_source_index_http_errors_map_to_approved_codes() -> None:
    mapped = _source_index_api_error(SourceIndexError(409, "source_index_in_progress", "busy"))
    assert mapped.status_code == 409
    assert mapped.code == "operation_conflict"

    timeout = _source_index_api_error(SourceIndexError(504, "source_index_timeout", "timed out"))
    assert timeout.status_code == 504
    assert timeout.code == "dependency_unavailable"

    missing = _source_index_api_error(SourceIndexError(404, "source_not_found", "missing"))
    assert missing.status_code == 404
    assert missing.code == "not_found"


class _ScriptedClient:
    def __init__(self) -> None:
        self.submit_calls = 0
        self.readiness_calls = 0
        self._readiness: list[IndexReadiness] = []
        self._submit_error: SourceIndexError | None = None

    def queue_readiness(self, *values: IndexReadiness) -> None:
        self._readiness.extend(values)

    def fail_submit(self, exc: SourceIndexError) -> None:
        self._submit_error = exc

    def submit(self, domain, *, request_id: str, content_hash: str, rendered_text: str) -> IndexSubmitResult:  # noqa: ANN001
        self.submit_calls += 1
        if self._submit_error is not None:
            raise self._submit_error
        return IndexSubmitResult(remote_document_id="remote-1")

    def readiness(self, domain, *, request_id: str) -> IndexReadiness:  # noqa: ANN001
        self.readiness_calls += 1
        if not self._readiness:
            return IndexReadiness(ready=False, failed=True, error_code="source_index_missing", error_message="missing")
        return self._readiness.pop(0)

    def delete(self, domain, *, request_id: str) -> None:  # noqa: ANN001
        return None

    def is_absent(self, domain, *, request_id: str) -> bool:  # noqa: ANN001
        return True

    def retrieve(self, domain, *, question: str):  # noqa: ANN001
        return ()


def test_timeout_leaves_submitting_uncertain_and_probe_avoids_resubmit(tmp_path, monkeypatch) -> None:
    settings = Settings(
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        session_cookie_secure=False,
        domain_runtime_controller_kind="local",
        domain_runtime_root=str(tmp_path / "runtimes"),
        source_storage_root=str(tmp_path / "storage"),
        source_index_worker_id="index-worker",
        source_index_lease_seconds=30,
        source_index_timeout_seconds=10,
        source_index_poll_backoff_seconds=5,
        lightrag_client_kind="local",
    )
    client = _ScriptedClient()
    client.queue_readiness(
        IndexReadiness(ready=False, failed=True, error_code="source_index_missing", error_message="missing")
    )
    worker = SourceIndexWorker(settings, client=client)

    def _timeout_submit(*_args, **_kwargs):
        client.submit_calls += 1
        raise SourceIndexError(504, "source_index_timeout", "Source index runtime timed out.")

    monkeypatch.setattr(worker, "_submit_with_lease_heartbeat", _timeout_submit)

    source = SourceDocument(
        id="src-timeout",
        public_ref="doc_timeout",
        domain_id="domain-x",
        original_filename="a.pdf",
        content_type="application/pdf",
        original_sha256="a" * 64,
        original_size_bytes=10,
        original_object_key="obj/timeout",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
        index_state=SOURCE_INDEX_STATE_SUBMITTING,
        index_generation=1,
        index_content_hash="d" * 64,
        index_request_id=compute_index_request_id("src-timeout", 1, "d" * 64),
        index_lease_owner="index-worker",
        index_lease_expires_at=utc_now() + timedelta(seconds=30),
        index_updated_at=utc_now(),
    )
    domain = _domain()
    domain.id = "domain-x"

    db = MagicMock()
    db.get.side_effect = lambda model, key: source if model is SourceDocument else domain
    db.refresh = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.scalar = MagicMock(return_value=source)

    assert worker.run_once(db) is True
    assert client.submit_calls == 1
    assert source.index_state == SOURCE_INDEX_STATE_SUBMITTING
    assert source.index_error_code == SOURCE_INDEX_UNCERTAIN_CODE
    assert source.index_lease_owner is None
    assert source.index_lease_expires_at is not None

    # Reclaim: readiness says ready → accept/ready without another submit.
    source.index_lease_owner = "index-worker"
    source.index_lease_expires_at = utc_now() + timedelta(seconds=30)
    client.queue_readiness(IndexReadiness(ready=True))
    db.scalar = MagicMock(return_value=source)
    assert worker.run_once(db) is True
    assert client.submit_calls == 1
    assert source.index_state == SOURCE_INDEX_STATE_READY


def test_schedule_index_poll_backoff_gates_accepted_rows() -> None:
    source = SourceDocument(
        id="src-backoff",
        public_ref="doc_backoff",
        domain_id="domain-x",
        original_filename="a.pdf",
        content_type="application/pdf",
        original_sha256="a" * 64,
        original_size_bytes=10,
        original_object_key="obj/backoff",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
        index_state=SOURCE_INDEX_STATE_ACCEPTED,
        index_generation=2,
        index_content_hash="e" * 64,
        index_request_id=compute_index_request_id("src-backoff", 2, "e" * 64),
        index_lease_owner="index-worker",
        index_lease_expires_at=utc_now() + timedelta(seconds=30),
        index_updated_at=utc_now(),
    )
    db = MagicMock()
    db.get.return_value = source
    before = utc_now()
    assert (
        schedule_index_poll_backoff(
            db,
            source_id=source.id,
            generation=2,
            request_id=source.index_request_id,
            backoff_seconds=7,
        )
        is True
    )
    assert source.index_lease_owner is None
    assert source.index_lease_expires_at is not None
    assert source.index_lease_expires_at >= before + timedelta(seconds=6)


def test_mark_index_uncertain_rejects_stale_generation() -> None:
    source = SourceDocument(
        id="src-stale",
        public_ref="doc_stale",
        domain_id="domain-x",
        original_filename="a.pdf",
        content_type="application/pdf",
        original_sha256="a" * 64,
        original_size_bytes=10,
        original_object_key="obj/stale",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
        index_state=SOURCE_INDEX_STATE_SUBMITTING,
        index_generation=3,
        index_content_hash="f" * 64,
        index_request_id=compute_index_request_id("src-stale", 3, "f" * 64),
    )
    db = MagicMock()
    db.get.return_value = source
    assert (
        mark_index_uncertain_if_current(
            db,
            source_id=source.id,
            generation=2,
            request_id=source.index_request_id,
            backoff_seconds=5,
        )
        is False
    )
    assert source.index_error_code is None


def test_poll_backoff_settings_validated() -> None:
    with pytest.raises(ValueError, match="source_index_poll_backoff_seconds must be positive"):
        Settings(
            testing=True,
            source_index_lease_seconds=30,
            source_index_timeout_seconds=10,
            source_index_poll_backoff_seconds=0,
        )
    with pytest.raises(ValueError, match="source_index_poll_backoff_seconds must be less than"):
        Settings(
            testing=True,
            source_index_lease_seconds=30,
            source_index_timeout_seconds=10,
            source_index_poll_backoff_seconds=30,
        )
