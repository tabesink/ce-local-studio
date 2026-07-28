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
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.models import (
    DOMAIN_OPERATION_STATUS_SUCCEEDED,
    DOMAIN_STATE_RUNNING,
    DOMAIN_STATE_STOPPED,
    ROLE_ADMINISTRATOR,
    User,
)
from context_engine.security import hash_session_token
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.csrf import issue_csrf_token
from context_engine.services.domains import (
    DomainError,
    create_domain,
    enqueue_delete_domain,
    member_domain_list,
    start_domain,
    stop_domain,
)
from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)
from context_engine.services.runtime_config import (
    SecretCrypto,
    rotate_provider_credential,
    seed_runtime_config,
)

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p301_[a-z0-9_]+$")
HEAD_REVISION = "a2c7e9f14b80"

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
    database_name = f"ce_p301_{label}_{uuid4().hex}"
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


def test_p3_01_domains_schema_lifecycle_and_http_on_postgresql_16(tmp_path: Path) -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "domains") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            database_url_text = database_url.render_as_string(hide_password=False)
            runtime_root = tmp_path / "domain-runtimes"
            settings = Settings(
                database_url=database_url_text,
                testing=True,
                public_origin="http://ce.example.test",
                internal_hosts="testserver",
                trusted_bff_peers="testclient",
                csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
                session_cookie_secure=False,
                domain_runtime_controller_kind="local",
                domain_runtime_root=str(runtime_root),
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with engine.connect() as connection:
                    version_checks = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT conname FROM pg_constraint "
                                "WHERE conrelid IN ("
                                " 'domains'::regclass,"
                                " 'domain_operations'::regclass"
                                ") AND conname LIKE '%version%'"
                            )
                        )
                    }
                assert "ck_domains_version_positive" in version_checks
                assert "ck_domain_operations_version_positive" in version_checks

                db = session_factory()
                try:
                    seed_runtime_config(db)
                    admin = create_user(db, username="p301-admin", password="Password123!", role=ROLE_ADMINISTRATOR)
                    audit = AuditContext(actor_user=admin, request_id="req-p301", actor_kind="administrator")
                    rotate_provider_credential(
                        db,
                        "openai",
                        "sk-test-openai-p301",
                        SecretCrypto.from_settings(settings),
                        expected_version=1,
                        audit_context=audit,
                    )

                    domain = create_domain(
                        db,
                        settings=settings,
                        domain_id="domain-manuals",
                        display_name="Equipment Manuals",
                        embedding_profile_id="openai-embedding-default",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    assert domain.state == DOMAIN_STATE_STOPPED
                    assert domain.control_generation == 1
                    assert domain.version == 1

                    start_op = start_domain(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    assert start_op.operation_type == "start"
                    assert start_op.status == DOMAIN_OPERATION_STATUS_SUCCEEDED
                    assert start_op.control_generation_at_start == 2
                    db.refresh(domain)
                    assert domain.state == DOMAIN_STATE_RUNNING
                    assert domain.control_generation == 2
                    assert domain.version >= 3

                    with pytest.raises(DomainError) as conflict:
                        start_domain(
                            db,
                            settings=settings,
                            domain_id=domain.id,
                            requested_by_user=admin,
                            audit_context=audit,
                        )
                    assert conflict.value.code == "domain_state_conflict"

                    stop_op = stop_domain(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    assert stop_op.status == DOMAIN_OPERATION_STATUS_SUCCEEDED
                    db.refresh(domain)
                    assert domain.state == DOMAIN_STATE_STOPPED

                    start_domain(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    assert member_domain_list(db, settings)[0]["queryEligible"] is True
                    assert "available" not in member_domain_list(db, settings)[0]

                    with pytest.raises(DomainError) as stale:
                        enqueue_delete_domain(
                            db,
                            domain_id=domain.id,
                            requested_by_user=admin,
                            expected_version=domain.version - 1,
                            audit_context=audit,
                        )
                    assert stale.value.code == "stale_revision"
                finally:
                    db.close()

                app = create_app(settings)
                with session_factory() as session:
                    admin_row = session.scalar(select(User).where(User.username == "p301-admin"))
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
                        CLIENT_BUCKET_HEADER: "p301-bucket",
                    }

                    created = client.post(
                        f"{CANONICAL_API_PREFIX}/admin/domains",
                        headers=headers,
                        json={
                            "id": "domain-policies",
                            "displayName": "Policies",
                            "embeddingProfileId": "openai-embedding-default",
                        },
                    )
                    assert created.status_code == 201
                    body = created.json()["domain"]
                    assert body["state"] == DOMAIN_STATE_STOPPED
                    assert body["queryEligible"] is False
                    assert body["embeddingProfile"]["vectorDimensions"] == 1536
                    assert "storageSummary" not in body
                    assert "available" not in body
                    etag = created.headers.get("etag") or created.headers.get("ETag")
                    assert etag == f'"{body["version"]}"'

                    detail = client.get(
                        f"{CANONICAL_API_PREFIX}/admin/domains/domain-policies",
                        headers=headers,
                    )
                    assert detail.status_code == 200
                    assert (detail.headers.get("etag") or detail.headers.get("ETag")) == f'"{body["version"]}"'

                    started = client.post(
                        f"{CANONICAL_API_PREFIX}/admin/domains/domain-policies/start",
                        headers=headers,
                    )
                    assert started.status_code == 202
                    operation = started.json()["operation"]
                    assert operation["targetKind"] == "domain"
                    assert operation["operationType"] == "start"
                    assert operation["status"] == "succeeded"
                    assert "domain" not in started.json()

                    conflict = client.post(
                        f"{CANONICAL_API_PREFIX}/admin/domains/domain-policies/start",
                        headers=headers,
                    )
                    assert conflict.status_code == 409
                    assert conflict.json()["error"]["code"] == "domain_state_conflict"

                    missing_match = client.delete(
                        f"{CANONICAL_API_PREFIX}/admin/domains/domain-policies",
                        headers=headers,
                    )
                    assert missing_match.status_code == 428

                    current = client.get(
                        f"{CANONICAL_API_PREFIX}/admin/domains/domain-policies",
                        headers=headers,
                    )
                    version = current.json()["domain"]["version"]
                    deleted = client.delete(
                        f"{CANONICAL_API_PREFIX}/admin/domains/domain-policies",
                        headers={**headers, "If-Match": f'"{version}"'},
                    )
                    assert deleted.status_code == 202
                    assert deleted.json()["operation"]["operationType"] == "delete"
                    assert deleted.json()["operation"]["status"] == "queued"
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
