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
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url

from context_engine.app import create_app
from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory, utc_now
from context_engine.models import (
    DOMAIN_STATE_RUNNING,
    PARSER_DOCLING,
    ROLE_ADMINISTRATOR,
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_CANCELLED,
    SOURCE_INDEX_STATE_QUEUED,
    SOURCE_INDEX_STATE_READY,
    SOURCE_STATE_PREPARED,
    SourceBlock,
    SourceDocument,
)
from context_engine.security import hash_session_token
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.csrf import issue_csrf_token
from context_engine.services.domains import create_domain, start_domain
from context_engine.services.indexing import (
    LocalLightRAGIndexClient,
    SourceIndexWorker,
    compute_index_request_id,
    retry_source_index,
    source_is_query_eligible,
)
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config
from context_engine.adapters.domain_runtime_controller import LocalDomainRuntimeController

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p503_[a-z0-9_]+$")
HEAD_REVISION = "e5b8c1d94f20"

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
    database_name = f"ce_p503_{label}_{uuid4().hex}"
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


def _settings(database_url_text: str, tmp_path: Path, *, worker_id: str = "index-worker") -> Settings:
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
        source_index_poll_backoff_seconds=5,
        lightrag_client_kind="local",
    )


def _prepared_source(db, *, domain_id: str, admin_id: str, label: str) -> SourceDocument:
    content_hash = "b" * 64
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
        index_request_id="pending",
        index_updated_at=utc_now(),
        created_by_user_id=admin_id,
    )
    db.add(source)
    db.flush()
    # Content hash must match rendered handoff for worker submit.
    from context_engine.services.indexing import render_blocks_to_lightrag_handoff

    block = SourceBlock(
        source_document_id=source.id,
        domain_id=domain_id,
        source_order=1,
        kind="text",
        canonical_markdown=f"Index eligibility fixture {label}",
    )
    db.add(block)
    db.flush()
    rendered = render_blocks_to_lightrag_handoff(
        source_id=source.id,
        original_sha256=source.original_sha256,
        blocks=[block],
    )
    source.index_content_hash = rendered.content_hash
    source.index_request_id = compute_index_request_id(source.id, source.index_generation, rendered.content_hash)
    db.commit()
    db.refresh(source)
    return source


def _auth_client(db, settings: Settings, admin) -> tuple[TestClient, dict[str, str]]:
    token, _session = create_auth_session(db, admin, settings)
    csrf = issue_csrf_token(settings, binding=hash_session_token(token))
    app = create_app(settings)
    client = TestClient(app)
    client.cookies.set(settings.session_cookie_name, token, path="/")
    client.cookies.set(settings.csrf_cookie_name, csrf, path="/")
    headers = {
        "Origin": "http://ce.example.test",
        CSRF_HEADER: csrf,
        PUBLIC_HOST_HEADER: "ce.example.test",
        PUBLIC_PROTO_HEADER: "http",
        CLIENT_BUCKET_HEADER: "p503-bucket",
    }
    return client, headers


def test_p5_03_index_submit_poll_retry_cancel_eligibility_on_postgresql_16(tmp_path: Path) -> None:
    """A-08 submit/poll/retry/cancel + query eligibility (P5-03)."""
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "elig") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            database_url_text = database_url.render_as_string(hide_password=False)
            settings = _settings(database_url_text, tmp_path)
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                db = session_factory()
                try:
                    seed_runtime_config(db)
                    admin = create_user(db, username="p503-admin", password="Password123!", role=ROLE_ADMINISTRATOR)
                    audit = AuditContext(actor_user=admin, request_id="req-p503", actor_kind="administrator")
                    rotate_provider_credential(
                        db,
                        "openai",
                        "sk-test-openai-p503",
                        SecretCrypto.from_settings(settings),
                        expected_version=1,
                        audit_context=audit,
                    )
                    domain = create_domain(
                        db,
                        settings=settings,
                        domain_id="domain-index-elig",
                        display_name="Index Eligibility",
                        embedding_profile_id="openai-embedding-default",
                        graph_extraction_profile_id="openai-synthesis-default",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    start_domain(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    db.refresh(domain)
                    assert domain.state == DOMAIN_STATE_RUNNING

                    source = _prepared_source(db, domain_id=domain.id, admin_id=admin.id, label="primary")
                    controller = LocalDomainRuntimeController(settings)
                    assert source_is_query_eligible(db, source, domain, settings=settings, controller=controller) is False

                    client = LocalLightRAGIndexClient(settings, controller)
                    worker = SourceIndexWorker(settings, client=client)

                    # Submit tick: queued → submitting → accepted (local ready immediately after submit).
                    assert worker.run_once(db) is True
                    db.refresh(source)
                    assert source.index_state == SOURCE_INDEX_STATE_ACCEPTED
                    assert source.index_remote_document_id is not None
                    assert source_is_query_eligible(db, source, domain, settings=settings, controller=controller) is False

                    # Poll tick → ready + eligible.
                    assert worker.run_once(db) is True
                    db.refresh(source)
                    assert source.index_state == SOURCE_INDEX_STATE_READY
                    assert source_is_query_eligible(db, source, domain, settings=settings, controller=controller) is True

                    # DRIFT-28: not-ready accepted rows get lease-expiry backoff and are skipped.
                    peer = _prepared_source(db, domain_id=domain.id, admin_id=admin.id, label="peer")
                    peer.index_state = SOURCE_INDEX_STATE_ACCEPTED
                    peer.index_remote_document_id = "remote-peer"
                    peer.index_lease_owner = None
                    peer.index_lease_expires_at = utc_now() + timedelta(seconds=60)
                    peer.index_accepted_at = utc_now()
                    peer.index_updated_at = utc_now()
                    # Keep primary ready so claim would otherwise prefer older accepted peer if claimable.
                    db.commit()
                    assert worker._claim_next_source(db) is None

                    peer.index_lease_expires_at = utc_now() - timedelta(seconds=1)
                    db.commit()

                    class _NotReadyClient(LocalLightRAGIndexClient):
                        def readiness(self, domain, *, request_id: str):  # noqa: ANN001
                            from context_engine.services.indexing import IndexReadiness

                            return IndexReadiness(ready=False)

                    not_ready_worker = SourceIndexWorker(settings, client=_NotReadyClient(settings, controller))
                    assert not_ready_worker.run_once(db) is True
                    db.refresh(peer)
                    assert peer.index_state == SOURCE_INDEX_STATE_ACCEPTED
                    assert peer.index_lease_owner is None
                    assert peer.index_lease_expires_at is not None
                    assert peer.index_lease_expires_at > utc_now()
                    assert worker._claim_next_source(db) is None

                    # HTTP retry/cancel envelopes + conflict mapping.
                    http, headers = _auth_client(db, settings, admin)

                    retry_response = http.post(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain.id}/sources/{source.id}/index/retry",
                        headers=headers,
                    )
                    # Source is ready — retry is allowed and re-queues.
                    assert retry_response.status_code == 202, retry_response.text
                    body = retry_response.json()
                    assert set(body.keys()) == {"source"}
                    assert body["source"]["indexState"] == "queued"
                    assert {row["action"] for row in body["source"]["allowedActions"]} >= {
                        "retry",
                        "cancel",
                        "delete",
                        "indexRetry",
                        "indexCancel",
                    }
                    index_retry = next(row for row in body["source"]["allowedActions"] if row["action"] == "indexRetry")
                    assert index_retry["enabled"] is False

                    db.refresh(source)
                    in_progress = http.post(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain.id}/sources/{source.id}/index/retry",
                        headers=headers,
                    )
                    assert in_progress.status_code == 409
                    assert in_progress.json()["error"]["code"] == "operation_conflict"

                    # Capture request id before cancel clears it.
                    prior_request_id = source.index_request_id
                    cancel = http.post(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain.id}/sources/{source.id}/index/cancel",
                        headers=headers,
                    )
                    assert cancel.status_code == 200, cancel.text
                    assert cancel.json()["source"]["indexState"] == "cancelled"
                    db.refresh(source)
                    assert source.index_state == SOURCE_INDEX_STATE_CANCELLED
                    assert source_is_query_eligible(db, source, domain, settings=settings, controller=controller) is False
                    if prior_request_id:
                        assert client.is_absent(domain, request_id=prior_request_id)

                    # Service-level retry after cancel re-queues with new generation.
                    retried = retry_source_index(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        source_id=source.id,
                        client=client,
                        audit_context=audit,
                    )
                    assert retried.index_state == SOURCE_INDEX_STATE_QUEUED
                    assert retried.index_generation >= 2
                finally:
                    db.close()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
