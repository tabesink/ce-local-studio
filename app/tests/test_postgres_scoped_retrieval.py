from __future__ import annotations

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
    SourceBlock,
    SourceDocument,
)
from context_engine.services.evidence import (
    EVIDENCE_RESULT_NO_CONTEXT,
    ScopedRetrievalCandidate,
    ScopedRetrievalResult,
    retrieve_scoped_evidence,
)
from context_engine.services.indexing import compute_index_request_id
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


@pytest.mark.parametrize("fence", ["stop_restart", "reindex_ready", "delete", "replace"])
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
                    source.index_request_id = compute_index_request_id(
                        source.id,
                        source.index_generation,
                        source.index_content_hash or "",
                    )
                    block = SourceBlock(
                        source_document_id=source.id,
                        domain_id=domain.id,
                        source_order=1,
                        kind="text",
                        canonical_markdown="Current canonical content",
                    )
                    db.add(block)
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
                assert failures == []
                assert results == [{"result": EVIDENCE_RESULT_NO_CONTEXT, "evidence": []}]
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
