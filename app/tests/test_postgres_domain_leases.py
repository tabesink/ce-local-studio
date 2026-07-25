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
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url

from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory, utc_now
from context_engine.models import (
    DOMAIN_OPERATION_STATUS_CANCELLED,
    DOMAIN_OPERATION_STATUS_QUEUED,
    DOMAIN_OPERATION_STATUS_RUNNING,
    DOMAIN_OPERATION_STATUS_SUCCEEDED,
    DOMAIN_OPERATION_STOP,
    DOMAIN_STATE_DELETING,
    DOMAIN_STATE_RUNNING,
    DOMAIN_STATE_STOPPED,
    Domain,
    DomainOperation,
    ROLE_ADMINISTRATOR,
)
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_user
from context_engine.adapters.domain_runtime_controller import (
    CONTROLLER_OUTCOME_UNCERTAIN,
    LocalDomainRuntimeController,
    RuntimeControllerResult,
)
from context_engine.services.domains import (
    DomainDeleteWorker,
    DomainError,
    create_domain,
    domain_available,
    enqueue_delete_domain,
    member_domain_list,
    reconcile_uncertain_lifecycle_operations,
    start_domain,
    stop_domain,
    update_domain_state_if_current,
)
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p303_[a-z0-9_]+$")
HEAD_REVISION = "b5c8e2d19f47"

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
    database_name = f"ce_p303_{label}_{uuid4().hex}"
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


class GenerationBumpController(LocalDomainRuntimeController):
    def __init__(self, settings: Settings, db_factory) -> None:
        super().__init__(settings)
        self._db_factory = db_factory

    def start(self, domain, *, operation_key: str, control_generation: int) -> RuntimeControllerResult:
        result = super().start(domain, operation_key=operation_key, control_generation=control_generation)
        db = self._db_factory()
        try:
            row = db.get(Domain, domain.id)
            assert row is not None
            row.control_generation += 1
            row.version += 1
            db.commit()
        finally:
            db.close()
        return result


class UncertainStopController(LocalDomainRuntimeController):
    def stop(self, domain, *, operation_key: str, control_generation: int) -> RuntimeControllerResult:
        return RuntimeControllerResult(
            outcome=CONTROLLER_OUTCOME_UNCERTAIN,
            message="Runtime outcome uncertain; reconciliation required.",
        )


def test_p3_03_leases_fences_supersede_and_delete_worker_on_postgresql_16(tmp_path: Path) -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "leases") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            runtime_root = tmp_path / "domain-runtimes"
            settings = Settings(
                database_url=database_url.render_as_string(hide_password=False),
                testing=True,
                domain_runtime_controller_kind="local",
                domain_runtime_root=str(runtime_root),
                domain_delete_lease_seconds=30,
                domain_lifecycle_lease_seconds=30,
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                db = session_factory()
                try:
                    seed_runtime_config(db)
                    admin = create_user(db, username="p303-admin", password="Password123!", role=ROLE_ADMINISTRATOR)
                    audit = AuditContext(actor_user=admin, request_id="req-p303", actor_kind="administrator")
                    rotate_provider_credential(
                        db,
                        "openai",
                        "sk-test-openai-p303",
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

                    # A-03 stale generation no-op: controller succeeds but generation advances underneath.
                    bumping = GenerationBumpController(settings, session_factory)
                    stale_op = start_domain(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        controller=bumping,
                        audit_context=audit,
                    )
                    assert stale_op.status == DOMAIN_OPERATION_STATUS_CANCELLED
                    db.refresh(domain)
                    assert domain.state == DOMAIN_STATE_STOPPED
                    assert domain.control_generation >= 3

                    start_op = start_domain(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    assert start_op.status == DOMAIN_OPERATION_STATUS_SUCCEEDED
                    db.refresh(domain)
                    assert domain.state == DOMAIN_STATE_RUNNING
                    assert domain_available(db, domain, LocalDomainRuntimeController(settings)) is True
                    assert member_domain_list(db, settings)

                    # A-04 stop fence: active stop op makes domain ineligible before controller returns.
                    uncertain = UncertainStopController(settings)
                    with pytest.raises(DomainError) as uncertain_exc:
                        stop_domain(
                            db,
                            settings=settings,
                            domain_id=domain.id,
                            requested_by_user=admin,
                            controller=uncertain,
                            audit_context=audit,
                        )
                    assert uncertain_exc.value.code == "dependency_unavailable"
                    db.refresh(domain)
                    assert domain.state == DOMAIN_STATE_RUNNING
                    active = db.scalar(
                        select(DomainOperation).where(
                            DomainOperation.domain_id == domain.id,
                            DomainOperation.status == DOMAIN_OPERATION_STATUS_RUNNING,
                        )
                    )
                    assert active is not None
                    assert "uncertain" in (active.message or "").lower()
                    assert domain_available(db, domain, LocalDomainRuntimeController(settings)) is False
                    assert member_domain_list(db, settings) == []

                    # Reconcile clears uncertain stop once runtime is unhealthy.
                    LocalDomainRuntimeController(settings).stop(
                        domain,
                        operation_key=active.id,
                        control_generation=active.control_generation_at_start,
                    )
                    resolved = reconcile_uncertain_lifecycle_operations(db, settings)
                    assert resolved >= 1
                    db.refresh(active)
                    db.refresh(domain)
                    assert active.status == DOMAIN_OPERATION_STATUS_SUCCEEDED
                    assert domain.state == DOMAIN_STATE_STOPPED

                    start_domain(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    db.refresh(domain)
                    stop_domain(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    db.refresh(domain)
                    assert domain.state == DOMAIN_STATE_STOPPED

                    # A-05 supersede: active stop op cancelled by delete.
                    start_domain(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    db.refresh(domain)
                    now = utc_now()
                    blocking = DomainOperation(
                        id=str(uuid4()),
                        domain_id=domain.id,
                        operation_type=DOMAIN_OPERATION_STOP,
                        status=DOMAIN_OPERATION_STATUS_RUNNING,
                        control_generation_at_start=domain.control_generation,
                        message="Stopping domain.",
                        started_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                    domain.control_generation += 1
                    domain.version += 1
                    db.add(blocking)
                    db.commit()
                    assert domain_available(db, domain, LocalDomainRuntimeController(settings)) is False

                    delete_op = enqueue_delete_domain(
                        db,
                        domain_id=domain.id,
                        requested_by_user=admin,
                        expected_version=domain.version,
                        audit_context=audit,
                    )
                    assert delete_op.status == DOMAIN_OPERATION_STATUS_QUEUED
                    db.refresh(blocking)
                    db.refresh(domain)
                    assert blocking.status == DOMAIN_OPERATION_STATUS_CANCELLED
                    assert domain.state == DOMAIN_STATE_DELETING
                    assert member_domain_list(db, settings) == []

                    # A-10 delete worker happy path.
                    worker = DomainDeleteWorker(settings)
                    assert worker.run_once(db) is True
                    assert db.get(Domain, "domain-manuals") is None

                    # Fresh domain for lease reclaim / stale delete completion.
                    domain2 = create_domain(
                        db,
                        settings=settings,
                        domain_id="domain-policies",
                        display_name="Policies",
                        embedding_profile_id="openai-embedding-default",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    delete2 = enqueue_delete_domain(
                        db,
                        domain_id=domain2.id,
                        requested_by_user=admin,
                        expected_version=domain2.version,
                        audit_context=audit,
                    )
                    first = DomainDeleteWorker(
                        Settings(
                            database_url=settings.database_url,
                            testing=True,
                            domain_runtime_controller_kind="local",
                            domain_runtime_root=str(runtime_root),
                            domain_delete_worker_id="worker-a",
                            domain_delete_lease_seconds=30,
                        )
                    )
                    claimed = first._claim_next_operation(db)
                    assert claimed is not None
                    assert claimed.id == delete2.id
                    claimed.lease_expires_at = utc_now() - timedelta(seconds=1)
                    db.commit()

                    second = DomainDeleteWorker(
                        Settings(
                            database_url=settings.database_url,
                            testing=True,
                            domain_runtime_controller_kind="local",
                            domain_runtime_root=str(runtime_root),
                            domain_delete_worker_id="worker-b",
                            domain_delete_lease_seconds=30,
                        )
                    )
                    reclaimed = second._claim_next_operation(db)
                    assert reclaimed is not None
                    assert reclaimed.lease_owner == "worker-b"

                    # Stale generation no-op for delete completion after reclaim.
                    domain_row = db.get(Domain, domain2.id)
                    assert domain_row is not None
                    domain_row.control_generation += 1
                    reclaimed.lease_expires_at = utc_now() - timedelta(seconds=1)
                    db.commit()
                    assert second.run_once(db) is True
                    remaining = db.get(Domain, domain2.id)
                    assert remaining is not None
                    op_after = db.get(DomainOperation, delete2.id)
                    assert op_after is not None
                    assert op_after.status == DOMAIN_OPERATION_STATUS_CANCELLED

                    # Conditional state helper still fences by generation.
                    assert (
                        update_domain_state_if_current(
                            db,
                            domain_id=domain2.id,
                            runtime_instance_id=remaining.runtime_instance_id,
                            control_generation=remaining.control_generation - 1,
                            state=DOMAIN_STATE_STOPPED,
                        )
                        == 0
                    )
                finally:
                    db.close()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
