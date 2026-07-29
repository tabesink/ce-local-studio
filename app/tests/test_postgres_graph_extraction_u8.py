"""P12-07 U8 PostgreSQL proofs: extraction binding, latch, one-time assignment."""

from __future__ import annotations

from contextlib import contextmanager
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
from context_engine.db import create_db_engine, create_session_factory
from context_engine.models import (
    DOMAIN_STATE_STOPPED,
    ROLE_ADMINISTRATOR,
    Domain,
)
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_user
from context_engine.services.domains import (
    DomainError,
    assign_graph_extraction_profile,
    create_domain,
)
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.runtime_config import (
    DEFAULT_GRAPH_EXTRACTION_PROFILE_ID,
    SecretCrypto,
    rotate_provider_credential,
    seed_runtime_config,
)

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p1207u8_[a-z0-9_]+$")
HEAD_REVISION = "e5b8c1d94f20"

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
    database_name = f"ce_p1207u8_{label}_{uuid4().hex}"
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


def test_u8_domain_extraction_binding_latch_and_assignment_on_postgresql_16(tmp_path: Path) -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "graph") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            settings = Settings(
                testing=True,
                database_url=database_url.render_as_string(hide_password=False),
                domain_runtime_root=str(tmp_path / "runtimes"),
                lightrag_client_kind="local",
            )
            engine = create_db_engine(settings)
            SessionLocal = create_session_factory(engine)
            try:
                with SessionLocal() as db:
                    seed_runtime_config(db)
                    rotate_provider_credential(
                        db,
                        "openai",
                        "sk-test-openai-u8",
                        SecretCrypto.from_settings(settings),
                        expected_version=1,
                    )
                    admin = create_user(
                        db,
                        username=f"admin-{uuid4().hex[:8]}",
                        password="password-password",
                        role=ROLE_ADMINISTRATOR,
                    )
                    audit = AuditContext(actor_kind="administrator", actor_user_id=admin.id)

                    domain = create_domain(
                        db,
                        settings=settings,
                        domain_id="domain-equipment",
                        display_name="Equipment Manuals",
                        embedding_profile_id="openai-embedding-default",
                        graph_extraction_profile_id=DEFAULT_GRAPH_EXTRACTION_PROFILE_ID,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    assert domain.graph_extraction_profile_id == DEFAULT_GRAPH_EXTRACTION_PROFILE_ID
                    assert domain.indexing_ever_started is False
                    assert domain.graph_desired_generation == 0
                    assert domain.graph_applied_generation == 0

                    with pytest.raises(DomainError) as unsupported:
                        create_domain(
                            db,
                            settings=settings,
                            domain_id="domain-bad-extraction",
                            display_name="Bad",
                            embedding_profile_id="openai-embedding-default",
                            graph_extraction_profile_id="openai-gpt-4-1-nano",
                            requested_by_user=admin,
                            audit_context=audit,
                        )
                    assert unsupported.value.code == "graph_extraction_profile_unsupported"

                    # Legacy stopped never-indexed domain accepts one-time assignment.
                    legacy = Domain(
                        id="legacy-stopped",
                        display_name="Legacy",
                        state=DOMAIN_STATE_STOPPED,
                        embedding_profile_id="openai-embedding-default",
                        graph_extraction_profile_id=None,
                        indexing_ever_started=False,
                        graph_desired_generation=0,
                        graph_applied_generation=0,
                        runtime_instance_id=str(uuid4()),
                        control_generation=1,
                        version=1,
                    )
                    db.add(legacy)
                    db.commit()

                    assigned = assign_graph_extraction_profile(
                        db,
                        settings=settings,
                        domain_id=legacy.id,
                        graph_extraction_profile_id=DEFAULT_GRAPH_EXTRACTION_PROFILE_ID,
                        expected_version=1,
                        audit_context=audit,
                    )
                    assert assigned.graph_extraction_profile_id == DEFAULT_GRAPH_EXTRACTION_PROFILE_ID
                    assert assigned.version == 2

                    with pytest.raises(DomainError) as reassign:
                        assign_graph_extraction_profile(
                            db,
                            settings=settings,
                            domain_id=legacy.id,
                            graph_extraction_profile_id="openai-gpt-4o",
                            expected_version=2,
                            audit_context=audit,
                        )
                    assert reassign.value.code == "graph_extraction_assignment_ineligible"

                    # Cancelled / delete-all histories keep the latch true and reject assignment.
                    latched = Domain(
                        id="legacy-cancelled",
                        display_name="Cancelled History",
                        state=DOMAIN_STATE_STOPPED,
                        embedding_profile_id="openai-embedding-default",
                        graph_extraction_profile_id=None,
                        indexing_ever_started=True,
                        runtime_instance_id=str(uuid4()),
                        control_generation=1,
                        version=1,
                    )
                    db.add(latched)
                    db.commit()

                    with pytest.raises(DomainError) as cancelled:
                        assign_graph_extraction_profile(
                            db,
                            settings=settings,
                            domain_id=latched.id,
                            graph_extraction_profile_id=DEFAULT_GRAPH_EXTRACTION_PROFILE_ID,
                            expected_version=1,
                            audit_context=audit,
                        )
                    assert cancelled.value.code == "graph_extraction_assignment_ineligible"

                    # Service latch helper never clears.
                    from context_engine.services.indexing import mark_domain_indexing_ever_started

                    domain = db.get(Domain, "domain-equipment")
                    assert domain is not None
                    mark_domain_indexing_ever_started(db, domain)
                    db.commit()
                    db.refresh(domain)
                    assert domain.indexing_ever_started is True
                    mark_domain_indexing_ever_started(db, domain)
                    db.commit()
                    db.refresh(domain)
                    assert domain.indexing_ever_started is True
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
