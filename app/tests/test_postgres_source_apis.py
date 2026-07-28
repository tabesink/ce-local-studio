from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url

from context_engine.app import create_app
from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.models import (
    ROLE_ADMINISTRATOR,
    SOURCE_BLOCK_KIND_TEXT,
    SOURCE_PREP_OPERATION_DELETE,
    SOURCE_PREP_STATUS_QUEUED,
    SOURCE_STATE_DELETING,
    SourceBlock,
    SourceDocument,
    SourcePreparationOperation,
    User,
)
from context_engine.security import hash_session_token
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.csrf import issue_csrf_token
from context_engine.services.domains import create_domain
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config
from context_engine.services.sources import SourceDeleteWorker, upload_source_bytes

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p404_[a-z0-9_]+$")
HEAD_REVISION = "c9e4b2d17a60"

pytestmark = pytest.mark.postgresql


def _required_admin_url() -> URL:
    if os.getenv(OPT_IN_ENV) != "1":
        pytest.skip(f"set {OPT_IN_ENV}=1 to allow disposable PostgreSQL database tests")

    raw_url = os.getenv(ADMIN_URL_ENV)
    if not raw_url:
        pytest.fail(f"{ADMIN_URL_ENV} is required when disposable database tests are enabled")

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
    database_name = f"ce_p404_{label}_{uuid4().hex}"
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


def _settings(database_url_text: str, tmp_path: Path) -> Settings:
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
        source_delete_worker_id="source-delete-worker-a",
        source_delete_lease_seconds=30,
    )


def test_p4_04_outline_cancel_delete_apis_on_postgresql_16(tmp_path: Path) -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "apis") as database_url:
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
                    admin = create_user(
                        db, username="p404-admin", password="Password123!", role=ROLE_ADMINISTRATOR
                    )
                    audit = AuditContext(actor_user=admin, request_id="req-p404", actor_kind="administrator")
                    rotate_provider_credential(
                        db,
                        "openai",
                        "sk-test-openai-p404",
                        SecretCrypto.from_settings(settings),
                        expected_version=1,
                        audit_context=audit,
                    )
                    domain = create_domain(
                        db,
                        settings=settings,
                        domain_id="domain-manuals",
                        display_name="Manuals",
                        embedding_profile_id="openai-embedding-default",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    source, _prep = upload_source_bytes(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        filename="pump.pdf",
                        content_type="application/pdf",
                        data=b"%PDF-1.4 p404-outline-delete",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    db.add(
                        SourceBlock(
                            id=str(uuid4()),
                            source_document_id=source.id,
                            domain_id=domain.id,
                            source_order=1,
                            kind=SOURCE_BLOCK_KIND_TEXT,
                            canonical_markdown="# Safety\nDo not expose this body.",
                            heading_level=1,
                            page_start=1,
                            page_end=1,
                            section_path='["Safety"]',
                        )
                    )
                    db.commit()
                    source_id = source.id
                    domain_id = domain.id
                finally:
                    db.close()

                app = create_app(settings)
                with session_factory() as session:
                    admin_row = session.scalar(select(User).where(User.username == "p404-admin"))
                    assert admin_row is not None
                    token, _auth_session = create_auth_session(session, admin_row, settings)
                    csrf = issue_csrf_token(settings, binding=hash_session_token(token))

                with TestClient(app) as client:
                    client.cookies.set(settings.session_cookie_name, token, path="/")
                    client.cookies.set(settings.csrf_cookie_name, csrf, path="/")
                    headers = {
                        "Origin": "http://ce.example.test",
                        CSRF_HEADER: csrf,
                        PUBLIC_HOST_HEADER: "ce.example.test",
                        PUBLIC_PROTO_HEADER: "http",
                        CLIENT_BUCKET_HEADER: "p404-bucket",
                    }

                    outline = client.get(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/sources/{source_id}/outline",
                        headers=headers,
                    )
                    assert outline.status_code == 200
                    assert outline.json()["items"] == [
                        {"kind": "heading", "label": "Safety", "level": 1, "pageNumber": 1}
                    ]
                    assert "Do not expose" not in outline.text

                    ops = client.get(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/sources/{source_id}/operations",
                        headers=headers,
                    )
                    assert ops.status_code == 200
                    assert ops.json()["nextCursor"] is None
                    assert ops.json()["operations"][0]["targetKind"] == "source"

                    detail = client.get(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/sources/{source_id}",
                        headers=headers,
                    )
                    version = detail.json()["source"]["version"]
                    missing = client.post(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/sources/{source_id}/cancel",
                        headers=headers,
                    )
                    assert missing.status_code == 428

                    cancelled = client.post(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/sources/{source_id}/cancel",
                        headers={**headers, "If-Match": f'"{version}"'},
                    )
                    assert cancelled.status_code == 200
                    assert cancelled.json()["operation"]["status"] == "cancelled"
                    assert cancelled.json()["operation"]["targetKind"] == "source"

                    detail = client.get(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/sources/{source_id}",
                        headers=headers,
                    )
                    version = detail.json()["source"]["version"]
                    deleted = client.delete(
                        f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/sources/{source_id}",
                        headers={**headers, "If-Match": f'"{version}"'},
                    )
                    assert deleted.status_code == 202
                    body = deleted.json()["operation"]
                    assert body["operationType"] == "delete"
                    assert body["status"] == "queued"
                    assert body["targetKind"] == "source"

                db = session_factory()
                try:
                    source_row = db.get(SourceDocument, source_id)
                    assert source_row is not None
                    assert source_row.state == SOURCE_STATE_DELETING
                    delete_op = db.scalar(
                        select(SourcePreparationOperation).where(
                            SourcePreparationOperation.source_document_id == source_id,
                            SourcePreparationOperation.operation_type == SOURCE_PREP_OPERATION_DELETE,
                            SourcePreparationOperation.status == SOURCE_PREP_STATUS_QUEUED,
                        )
                    )
                    assert delete_op is not None
                    worker = SourceDeleteWorker(settings)
                    assert worker.run_once(db) is True
                    assert db.get(SourceDocument, source_id) is None
                finally:
                    db.close()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
