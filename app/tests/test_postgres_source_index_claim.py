from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
import os
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url

from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory, utc_now
from context_engine.models import (
    PARSER_DOCLING,
    ROLE_ADMINISTRATOR,
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_QUEUED,
    SOURCE_INDEX_STATE_READY,
    SOURCE_INDEX_STATE_SUBMITTING,
    SOURCE_STATE_PREPARED,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_user
from context_engine.services.domains import create_domain
from context_engine.services.indexing import (
    SourceIndexWorker,
    compute_index_request_id,
    mark_index_accepted_if_current,
    mark_index_ready_if_current,
)
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p501_[a-z0-9_]+$")
HEAD_REVISION = "c7d91e5a2f04"

pytestmark = pytest.mark.postgresql


def _required_admin_url() -> URL:
    if os.getenv(OPT_IN_ENV) != "1":
        pytest.skip(f"set {OPT_IN_ENV}=1 to allow disposable PostgreSQL database tests")
    raw_url = os.getenv(ADMIN_URL_ENV)
    if not raw_url:
        pytest.fail(f"{ADMIN_URL_ENV} is required when disposable PostgreSQL database tests are enabled")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.fail(f"{ADMIN_URL_ENV} must use PostgreSQL, not {url.get_backend_name()}")
    if not url.database:
        pytest.fail(f"{ADMIN_URL_ENV} must name an administrative database")
    return url


def _assert_postgresql_16(admin_engine: Engine) -> None:
    with admin_engine.connect() as connection:
        version_num = int(connection.scalar(text("SHOW server_version_num")))
    assert 160000 <= version_num < 170000, f"PostgreSQL 16 required, found {version_num}"


@contextmanager
def _disposable_database(admin_engine: Engine, admin_url: URL, label: str):
    database_name = f"ce_p501_{label}_{uuid4().hex}"
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


def _alembic_config(database_url: URL) -> Config:
    config = Config(str(APP_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(APP_ROOT / "migrations"))
    rendered_url = database_url.render_as_string(hide_password=False).replace("%", "%%")
    config.set_main_option("sqlalchemy.url", rendered_url)
    return config


def _settings(database_url_text: str, tmp_path: Path, *, worker_id: str) -> Settings:
    return Settings(
        database_url=database_url_text,
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        session_cookie_secure=False,
        domain_runtime_controller_kind="local",
        domain_runtime_root=str(tmp_path / "domain-runtimes"),
        source_storage_root=str(tmp_path / "source-storage"),
        source_index_worker_id=worker_id,
        source_index_lease_seconds=30,
        source_index_timeout_seconds=10,
        lightrag_client_kind="local",
    )


def _prepared_source(db, *, domain_id: str, admin_id: str, label: str) -> SourceDocument:
    content_hash = "a" * 64
    source = SourceDocument(
        domain_id=domain_id,
        public_ref=f"docref-{label}-{uuid4().hex[:12]}",
        original_filename=f"{label}.pdf",
        content_type="application/pdf",
        original_sha256=f"{label}-sha256".ljust(64, "0")[:64],
        original_size_bytes=128,
        original_object_key=f"obj/{label}/{uuid4().hex}",
        state=SOURCE_STATE_PREPARED,
        parser_kind=PARSER_DOCLING,
        preparation_generation=1,
        index_state=SOURCE_INDEX_STATE_QUEUED,
        index_generation=1,
        index_content_hash=content_hash,
        index_request_id=compute_index_request_id("pending", 1, content_hash),
        index_updated_at=utc_now(),
        created_by_user_id=admin_id,
    )
    db.add(source)
    db.flush()
    source.index_request_id = compute_index_request_id(source.id, source.index_generation, content_hash)
    db.add(
        SourceBlock(
            source_document_id=source.id,
            domain_id=domain_id,
            source_order=1,
            kind="text",
            canonical_markdown="Index claim fixture body",
        )
    )
    db.commit()
    db.refresh(source)
    return source


def test_p5_01_index_schema_and_claim_loop_on_postgresql_16(tmp_path: Path) -> None:
    """A-08 lease/generation fence for index worker claim (P5-01)."""
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "claim") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            database_url_text = database_url.render_as_string(hide_password=False)
            settings_a = _settings(database_url_text, tmp_path, worker_id="index-worker-a")
            engine = create_db_engine(settings_a)
            session_factory = create_session_factory(engine)
            try:
                with engine.connect() as connection:
                    columns = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_name = 'source_documents'"
                            )
                        )
                    }
                    constraints = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT conname FROM pg_constraint "
                                "WHERE conrelid = 'source_documents'::regclass"
                            )
                        )
                    }
                    indexes = {
                        row[0]
                        for row in connection.execute(
                            text("SELECT indexname FROM pg_indexes WHERE tablename = 'source_documents'")
                        )
                    }
                for required in (
                    "index_state",
                    "index_generation",
                    "index_request_id",
                    "index_content_hash",
                    "index_remote_document_id",
                    "index_lease_owner",
                    "index_lease_expires_at",
                    "index_accepted_at",
                    "index_ready_at",
                    "index_updated_at",
                ):
                    assert required in columns
                assert "ck_source_documents_index_state" in constraints
                assert "ck_source_documents_index_generation_nonnegative" in constraints
                assert "ix_source_documents_domain_index_state" in indexes

                db = session_factory()
                try:
                    seed_runtime_config(db)
                    admin = create_user(db, username="p501-admin", password="Password123!", role=ROLE_ADMINISTRATOR)
                    audit = AuditContext(actor_user=admin, request_id="req-p501", actor_kind="administrator")
                    rotate_provider_credential(
                        db,
                        "openai",
                        "sk-test-openai-p501",
                        SecretCrypto.from_settings(settings_a),
                        expected_version=1,
                        audit_context=audit,
                    )
                    domain = create_domain(
                        db,
                        settings=settings_a,
                        domain_id="domain-index-claim",
                        display_name="Index Claim",
                        embedding_profile_id="openai-embedding-default",
                        requested_by_user=admin,
                        audit_context=audit,
                    )

                    queued = _prepared_source(db, domain_id=domain.id, admin_id=admin.id, label="queued")
                    worker_a = SourceIndexWorker(settings_a)
                    claimed = worker_a._claim_next_source(db)
                    assert claimed is not None
                    assert claimed.id == queued.id
                    assert claimed.index_state == SOURCE_INDEX_STATE_SUBMITTING
                    assert claimed.index_lease_owner == "index-worker-a"
                    assert claimed.index_lease_expires_at is not None
                    assert claimed.index_lease_expires_at > utc_now()

                    # Active submitting lease is not double-claimed.
                    settings_b = _settings(database_url_text, tmp_path, worker_id="index-worker-b")
                    worker_b = SourceIndexWorker(settings_b)
                    assert worker_b._claim_next_source(db) is None

                    # Expired submitting lease is reclaimable with owner reassignment.
                    claimed.index_lease_expires_at = utc_now() - timedelta(seconds=1)
                    db.commit()
                    reclaimed = worker_b._claim_next_source(db)
                    assert reclaimed is not None
                    assert reclaimed.id == queued.id
                    assert reclaimed.index_state == SOURCE_INDEX_STATE_SUBMITTING
                    assert reclaimed.index_lease_owner == "index-worker-b"
                    assert reclaimed.index_lease_expires_at is not None
                    assert reclaimed.index_lease_expires_at > utc_now()

                    # Accepted readiness work takes a lease and skips unexpired peers.
                    accepted = _prepared_source(db, domain_id=domain.id, admin_id=admin.id, label="accepted")
                    accepted.index_state = SOURCE_INDEX_STATE_ACCEPTED
                    accepted.index_remote_document_id = "remote-accepted"
                    accepted.index_lease_owner = None
                    accepted.index_lease_expires_at = None
                    accepted.index_accepted_at = utc_now()
                    accepted.index_updated_at = utc_now()
                    # Keep submitting row leased so claim selects accepted next.
                    reclaimed.index_lease_expires_at = utc_now() + timedelta(seconds=60)
                    reclaimed.index_lease_owner = "index-worker-b"
                    db.commit()

                    accepted_claim = worker_a._claim_next_source(db)
                    assert accepted_claim is not None
                    assert accepted_claim.id == accepted.id
                    assert accepted_claim.index_state == SOURCE_INDEX_STATE_ACCEPTED
                    assert accepted_claim.index_lease_owner == "index-worker-a"
                    assert accepted_claim.index_lease_expires_at is not None
                    assert accepted_claim.index_lease_expires_at > utc_now()
                    assert worker_b._claim_next_source(db) is None

                    accepted_claim.index_lease_expires_at = utc_now() - timedelta(seconds=1)
                    db.commit()
                    accepted_reclaim = worker_b._claim_next_source(db)
                    assert accepted_reclaim is not None
                    assert accepted_reclaim.id == accepted.id
                    assert accepted_reclaim.index_lease_owner == "index-worker-b"

                    # Generation/request fence rejects stale completions (A-08).
                    generation = accepted.index_generation
                    request_id = accepted.index_request_id
                    assert request_id is not None
                    accepted.index_state = SOURCE_INDEX_STATE_SUBMITTING
                    accepted.index_lease_owner = "index-worker-a"
                    accepted.index_lease_expires_at = utc_now() + timedelta(seconds=30)
                    db.commit()

                    assert (
                        mark_index_accepted_if_current(
                            db,
                            source_id=accepted.id,
                            generation=generation + 1,
                            request_id=request_id,
                            remote_document_id="stale-remote",
                        )
                        is False
                    )
                    db.refresh(accepted)
                    assert accepted.index_state == SOURCE_INDEX_STATE_SUBMITTING
                    assert accepted.index_remote_document_id != "stale-remote"

                    assert (
                        mark_index_accepted_if_current(
                            db,
                            source_id=accepted.id,
                            generation=generation,
                            request_id=request_id,
                            remote_document_id="current-remote",
                        )
                        is True
                    )
                    db.refresh(accepted)
                    assert accepted.index_state == SOURCE_INDEX_STATE_ACCEPTED
                    assert accepted.index_remote_document_id == "current-remote"
                    assert accepted.index_lease_owner is None

                    assert (
                        mark_index_ready_if_current(
                            db,
                            source_id=accepted.id,
                            generation=generation,
                            request_id="mismatched-request-id",
                        )
                        is False
                    )
                    db.refresh(accepted)
                    assert accepted.index_state == SOURCE_INDEX_STATE_ACCEPTED

                    assert (
                        mark_index_ready_if_current(
                            db,
                            source_id=accepted.id,
                            generation=generation,
                            request_id=request_id,
                        )
                        is True
                    )
                    db.refresh(accepted)
                    assert accepted.index_state == SOURCE_INDEX_STATE_READY
                finally:
                    db.close()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
