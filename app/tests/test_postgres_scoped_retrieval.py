from __future__ import annotations

import hashlib
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url

from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory, utc_now
from context_engine.models import (
    DOMAIN_STATE_RUNNING,
    SOURCE_INDEX_STATE_READY,
    SOURCE_STATE_DELETING,
    SOURCE_STATE_PREPARED,
    Domain,
    DomainOperation,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.evidence import (
    EVIDENCE_RESULT_FOUND,
    EVIDENCE_RESULT_NO_CONTEXT,
    EvidenceRetrievalError,
    ScopedRetrievalCandidate,
    ScopedRetrievalResult,
    retrieve_scoped_evidence,
)
from context_engine.services.indexing import (
    compute_index_request_id,
    render_lightrag_input,
)
from context_engine.services.runtime_config import seed_runtime_config

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p601_[a-z0-9_]+$")

pytestmark = pytest.mark.postgresql


def _required_admin_url() -> URL:
    if os.getenv(OPT_IN_ENV) != "1":
        pytest.skip(f"set {OPT_IN_ENV}=1 to allow disposable PostgreSQL database tests")
    raw_url = os.getenv(ADMIN_URL_ENV)
    if not raw_url:
        pytest.fail(f"{ADMIN_URL_ENV} is required when disposable PostgreSQL database tests are enabled")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql" or not url.database:
        pytest.fail(f"{ADMIN_URL_ENV} must name a PostgreSQL administrative database")
    return url


@contextmanager
def _disposable_database(admin_engine: Engine, admin_url: URL, label: str):
    database_name = f"ce_p601_{label}_{uuid4().hex}"
    assert DATABASE_NAME_PATTERN.fullmatch(database_name)
    database_url = admin_url.set(database=database_name)
    with admin_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    try:
        yield database_url
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')


def _assert_postgresql_16(admin_engine: Engine) -> None:
    with admin_engine.connect() as connection:
        version_num = int(connection.scalar(text("SHOW server_version_num")))
    assert 160000 <= version_num < 170000, f"PostgreSQL 16 required, found {version_num}"


class _HealthyController:
    def health(self, _domain: Domain):
        return type("Health", (), {"healthy": True})()


class _BarrierClient:
    def __init__(
        self,
        *,
        retrieval_started: threading.Barrier,
        mutation_committed: threading.Barrier,
        candidate: str,
    ) -> None:
        self._retrieval_started = retrieval_started
        self._mutation_committed = mutation_committed
        self._candidate = candidate

    def retrieve(self, domain: Domain, *, question: str, deadline: float) -> ScopedRetrievalResult:
        self._retrieval_started.wait()
        self._mutation_committed.wait()
        return ScopedRetrievalResult(candidates=(ScopedRetrievalCandidate(text=self._candidate),))


class _StaticClient:
    def __init__(self, candidate: str) -> None:
        self._candidate = candidate
        self.calls = 0

    def retrieve(self, domain: Domain, *, question: str, deadline: float) -> ScopedRetrievalResult:
        self.calls += 1
        return ScopedRetrievalResult(candidates=(ScopedRetrievalCandidate(text=self._candidate),))


class _ConcurrentClient:
    def __init__(self, barrier: threading.Barrier, candidate: str) -> None:
        self._barrier = barrier
        self._candidate = candidate

    def retrieve(self, domain: Domain, *, question: str, deadline: float) -> ScopedRetrievalResult:
        self._barrier.wait()
        return ScopedRetrievalResult(candidates=(ScopedRetrievalCandidate(text=self._candidate),))


@pytest.mark.parametrize(
    "fence",
    ["stop_restart", "active_operation", "reindex_ready", "delete", "replace"],
)
def test_p6_01_post_call_snapshot_rejects_committed_fences(tmp_path: Path, fence: str) -> None:
    """C-01: a committed lifecycle/source fence during retrieval cannot map stale provenance."""
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, fence) as database_url:
            config = Config(str(APP_ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(APP_ROOT / "migrations"))
            config.set_main_option(
                "sqlalchemy.url",
                database_url.render_as_string(hide_password=False).replace("%", "%%"),
            )
            command.upgrade(config, "head")
            settings = Settings(
                database_url=database_url.render_as_string(hide_password=False),
                testing=True,
                domain_runtime_controller_kind="local",
                domain_runtime_root=str(tmp_path / "runtimes"),
            )
            engine = create_db_engine(settings)
            sessions = create_session_factory(engine)
            try:
                with sessions() as db:
                    seed_runtime_config(db)
                    domain = Domain(
                        id=f"domain-{fence}",
                        display_name="Scoped Retrieval",
                        state=DOMAIN_STATE_RUNNING,
                        embedding_profile_id="openai-embedding-default",
                        runtime_instance_id="runtime-before",
                        control_generation=3,
                    )
                    db.add(domain)
                    db.flush()
                    source = SourceDocument(
                        domain_id=domain.id,
                        public_ref=f"docref-{uuid4().hex[:12]}",
                        original_filename="manual.pdf",
                        content_type="application/pdf",
                        original_sha256="b" * 64,
                        original_size_bytes=128,
                        original_object_key=f"obj/{uuid4().hex}",
                        state=SOURCE_STATE_PREPARED,
                        parser_kind="docling",
                        preparation_generation=2,
                        index_state=SOURCE_INDEX_STATE_READY,
                        index_generation=4,
                        index_content_hash="c" * 64,
                        index_updated_at=utc_now(),
                    )
                    db.add(source)
                    db.flush()
                    block = SourceBlock(
                        source_document_id=source.id,
                        domain_id=domain.id,
                        source_order=1,
                        kind="text",
                        canonical_markdown="Current canonical content",
                    )
                    db.add(block)
                    db.flush()
                    source.index_content_hash = render_lightrag_input(db, source).content_hash
                    source.index_request_id = compute_index_request_id(
                        source.id,
                        source.index_generation,
                        source.index_content_hash,
                    )
                    db.commit()
                    marker = (
                        f"[CE_BLOCK schema=2 source_id={source.id} source_sha256={source.original_sha256} "
                        f"block_id={block.id} order=1]\nprivate candidate"
                    )
                    domain_id = domain.id
                    source_id = source.id

                retrieval_started = threading.Barrier(2)
                mutation_committed = threading.Barrier(2)
                results: list[dict[str, object]] = []
                failures: list[BaseException] = []

                def run_retrieval() -> None:
                    try:
                        with sessions() as retrieval_db:
                            results.append(
                                retrieve_scoped_evidence(
                                    retrieval_db,
                                    settings=settings,
                                    domain_id=domain_id,
                                    question="private question",
                                    client=_BarrierClient(
                                        retrieval_started=retrieval_started,
                                        mutation_committed=mutation_committed,
                                        candidate=marker,
                                    ),
                                    controller=_HealthyController(),  # type: ignore[arg-type]
                                )
                            )
                    except Exception as exc:  # noqa: BLE001  # pragma: no cover - surfaced on the test thread
                        failures.append(exc)

                retrieval_thread = threading.Thread(target=run_retrieval, daemon=True)
                retrieval_thread.start()
                retrieval_started.wait()
                with sessions() as other:
                    if fence == "stop_restart":
                        current_domain = other.get(Domain, domain_id)
                        assert current_domain is not None
                        current_domain.control_generation += 2
                        current_domain.runtime_instance_id = "runtime-after"
                        current_domain.state = DOMAIN_STATE_RUNNING
                    elif fence == "active_operation":
                        other.add(
                            DomainOperation(
                                domain_id=domain_id,
                                operation_type="stop",
                                status="queued",
                                control_generation_at_start=1,
                            )
                        )
                    elif fence == "reindex_ready":
                        current_source = other.get(SourceDocument, source_id)
                        assert current_source is not None
                        current_source.index_generation += 1
                        current_source.index_content_hash = "d" * 64
                        current_source.index_request_id = compute_index_request_id(
                            current_source.id,
                            current_source.index_generation,
                            current_source.index_content_hash,
                        )
                        current_source.index_state = SOURCE_INDEX_STATE_READY
                    elif fence == "delete":
                        current_source = other.get(SourceDocument, source_id)
                        assert current_source is not None
                        current_source.state = SOURCE_STATE_DELETING
                    else:
                        current_source = other.get(SourceDocument, source_id)
                        assert current_source is not None
                        current_source.preparation_generation += 1
                    other.commit()
                mutation_committed.wait()
                retrieval_thread.join(timeout=10)

                assert not retrieval_thread.is_alive()
                assert results == []
                assert len(failures) == 1
                assert isinstance(failures[0], EvidenceRetrievalError)
                expected_code = (
                    "domain_state_conflict"
                    if fence in {"stop_restart", "active_operation"}
                    else "domain_no_eligible_sources"
                )
                assert failures[0].code == expected_code
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p6_01_postgresql_success_schema_rollout_and_concurrent_isolation(tmp_path: Path) -> None:
    """C-01/C-02: current v2 rows map; v1/wrong-domain rows fail closed; calls stay isolated."""
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "mapping") as database_url:
            config = Config(str(APP_ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(APP_ROOT / "migrations"))
            config.set_main_option(
                "sqlalchemy.url",
                database_url.render_as_string(hide_password=False).replace("%", "%%"),
            )
            command.upgrade(config, "head")
            settings = Settings(
                database_url=database_url.render_as_string(hide_password=False),
                testing=True,
                domain_runtime_controller_kind="local",
                domain_runtime_root=str(tmp_path / "runtimes"),
            )
            engine = create_db_engine(settings)
            sessions = create_session_factory(engine)
            try:
                with sessions() as db:
                    seed_runtime_config(db)
                    domain = Domain(
                        id="domain-mapping",
                        display_name="Scoped Retrieval",
                        state=DOMAIN_STATE_RUNNING,
                        embedding_profile_id="openai-embedding-default",
                        runtime_instance_id="runtime-current",
                        control_generation=2,
                    )
                    db.add(domain)
                    db.flush()
                    source = SourceDocument(
                        domain_id=domain.id,
                        public_ref=f"docref-{uuid4().hex[:12]}",
                        original_filename="manual.pdf",
                        content_type="application/pdf",
                        original_sha256="b" * 64,
                        original_size_bytes=128,
                        original_object_key=f"obj/{uuid4().hex}",
                        state=SOURCE_STATE_PREPARED,
                        parser_kind="docling",
                        preparation_generation=2,
                        index_state=SOURCE_INDEX_STATE_READY,
                        index_generation=4,
                        index_updated_at=utc_now(),
                    )
                    db.add(source)
                    db.flush()
                    blocks = [
                        SourceBlock(
                            source_document_id=source.id,
                            domain_id=domain.id,
                            source_order=order,
                            kind="text",
                            canonical_markdown=f"Canonical content {order}",
                        )
                        for order in (1, 2)
                    ]
                    db.add_all(blocks)
                    db.flush()
                    v2_hash = render_lightrag_input(db, source).content_hash
                    source.index_content_hash = v2_hash
                    source.index_request_id = compute_index_request_id(
                        source.id,
                        source.index_generation,
                        v2_hash,
                    )
                    db.commit()
                    domain_id = domain.id
                    source_id = source.id
                    document_ref = source.public_ref
                    source_sha256 = source.original_sha256
                    block_ids = tuple(block.id for block in blocks)

                markers = tuple(
                    f"[CE_BLOCK schema=2 source_id={source_id} source_sha256={source_sha256} "
                    f"block_id={block_id} order={order}]\nprivate candidate {order}"
                    for order, block_id in enumerate(block_ids, start=1)
                )
                with sessions() as db:
                    found = retrieve_scoped_evidence(
                        db,
                        settings=settings,
                        domain_id=domain_id,
                        question="current",
                        client=_StaticClient(markers[0]),
                        controller=_HealthyController(),  # type: ignore[arg-type]
                    )
                assert found == {
                    "result": EVIDENCE_RESULT_FOUND,
                    "evidence": [
                        {
                            "citationLabel": "[1]",
                            "sourceLabel": "manual.pdf",
                            "excerpt": "Canonical content 1",
                            "kind": "text",
                            "documentRef": document_ref,
                            "documentLabel": "manual.pdf",
                            "anchor": None,
                        }
                    ],
                }

                wrong_domain = markers[0].replace(f"source_id={source_id}", "source_id=another-domain-source")
                with sessions() as db:
                    no_context = retrieve_scoped_evidence(
                        db,
                        settings=settings,
                        domain_id=domain_id,
                        question="wrong domain",
                        client=_StaticClient(wrong_domain),
                        controller=_HealthyController(),  # type: ignore[arg-type]
                    )
                assert no_context == {"result": EVIDENCE_RESULT_NO_CONTEXT, "evidence": []}

                legacy_text = (
                    f"[CE_SOURCE schema=1 source_id={source_id} sha256={source_sha256}]\n\n"
                    f"[CE_BLOCK id={block_ids[0]} order=1]\nCanonical content 1\n\n"
                    f"[CE_BLOCK id={block_ids[1]} order=2]\nCanonical content 2"
                )
                legacy_hash = hashlib.sha256(legacy_text.encode("utf-8")).hexdigest()
                with sessions() as db:
                    current_source = db.get(SourceDocument, source_id)
                    assert current_source is not None
                    current_source.index_content_hash = legacy_hash
                    current_source.index_request_id = compute_index_request_id(
                        current_source.id,
                        current_source.index_generation,
                        legacy_hash,
                    )
                    db.commit()
                legacy_client = _StaticClient(markers[0])
                with sessions() as db, pytest.raises(EvidenceRetrievalError) as legacy:
                    retrieve_scoped_evidence(
                        db,
                        settings=settings,
                        domain_id=domain_id,
                        question="legacy",
                        client=legacy_client,
                        controller=_HealthyController(),  # type: ignore[arg-type]
                    )
                assert legacy.value.code == "domain_no_eligible_sources"
                assert legacy_client.calls == 0

                with sessions() as db:
                    current_source = db.get(SourceDocument, source_id)
                    assert current_source is not None
                    current_source.index_content_hash = v2_hash
                    current_source.index_request_id = compute_index_request_id(
                        current_source.id,
                        current_source.index_generation,
                        v2_hash,
                    )
                    db.commit()

                barrier = threading.Barrier(2)
                results: dict[str, dict[str, object]] = {}
                failures: list[BaseException] = []

                def run_call(label: str, marker: str) -> None:
                    try:
                        with sessions() as db:
                            results[label] = retrieve_scoped_evidence(
                                db,
                                settings=settings,
                                domain_id=domain_id,
                                question=label,
                                client=_ConcurrentClient(barrier, marker),
                                controller=_HealthyController(),  # type: ignore[arg-type]
                            )
                    except BaseException as exc:  # noqa: BLE001  # pragma: no cover - surfaced after join
                        failures.append(exc)

                threads = [
                    threading.Thread(target=run_call, args=(f"call-{index}", marker), daemon=True)
                    for index, marker in enumerate(markers, start=1)
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)
                    assert not thread.is_alive()

                assert failures == []
                assert results["call-1"]["evidence"] == [
                    {
                        "citationLabel": "[1]",
                        "sourceLabel": "manual.pdf",
                        "excerpt": "Canonical content 1",
                        "kind": "text",
                        "documentRef": document_ref,
                        "documentLabel": "manual.pdf",
                        "anchor": None,
                    }
                ]
                assert results["call-2"]["evidence"] == [
                    {
                        "citationLabel": "[1]",
                        "sourceLabel": "manual.pdf",
                        "excerpt": "Canonical content 2",
                        "kind": "text",
                        "documentRef": document_ref,
                        "documentLabel": "manual.pdf",
                        "anchor": None,
                    }
                ]
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
