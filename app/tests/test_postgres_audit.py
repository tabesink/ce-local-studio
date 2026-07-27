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
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import DBAPIError

from context_engine.db import create_db_engine, create_session_factory
from context_engine.models import (
    AUDIT_EVENT_USER_DISABLED,
    AUDIT_OUTCOME_SUCCEEDED,
    AuditEvent,
    ROLE_ADMINISTRATOR,
    ROLE_MEMBER,
    User,
)
from context_engine.config import Settings
from context_engine.services.audit import (
    AuditContext,
    AuditError,
    AuditService,
    commit_protected_mutation,
)
from context_engine.services.auth import create_user


APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
HEAD_REVISION = "c7d91e5a2f04"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p106_[a-z_]+_[0-9a-f]{32}$")

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
    database_name = f"ce_p106_{label}_{uuid4().hex}"
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


def test_p1_06_append_only_and_protected_mutation_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "audit") as database_url:
            config = _alembic_config(database_url)
            script = ScriptDirectory.from_config(config)
            assert script.get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            settings = Settings(database_url=database_url.render_as_string(hide_password=False))
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with engine.connect() as connection:
                    triggers = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT tgname FROM pg_trigger "
                                "WHERE tgrelid = 'audit_events'::regclass AND NOT tgisinternal"
                            )
                        )
                    }
                    assert "trg_audit_events_forbid_update" in triggers
                    assert "trg_audit_events_forbid_delete" in triggers

                with session_factory() as session:
                    actor = create_user(
                        session,
                        f"admin_{uuid4().hex[:8]}@example.test",
                        "unused-password-value",
                        role=ROLE_ADMINISTRATOR,
                    )
                    target = create_user(
                        session,
                        f"member_{uuid4().hex[:8]}@example.test",
                        "unused-password-value",
                        role=ROLE_MEMBER,
                    )
                    actor_id = actor.id
                    target_id = target.id

                with session_factory() as session:
                    actor = session.get(User, actor_id)
                    target = session.get(User, target_id)
                    assert actor is not None and target is not None

                    def disable_target() -> User:
                        target.is_disabled = True
                        return target

                    result = commit_protected_mutation(
                        session,
                        disable_target,
                        event_name=AUDIT_EVENT_USER_DISABLED,
                        context=AuditContext(
                            actor_user=actor,
                            request_id="req-p106-success",
                            trace_id="trace-p106-success",
                        ),
                        target_kind="user",
                        target_id=target_id,
                    )
                    assert result.is_disabled is True

                with session_factory() as session:
                    persisted = session.get(User, target_id)
                    assert persisted is not None and persisted.is_disabled is True
                    event = session.scalar(
                        select(AuditEvent).where(
                            AuditEvent.event_name == AUDIT_EVENT_USER_DISABLED,
                            AuditEvent.target_id == target_id,
                        )
                    )
                    assert event is not None
                    assert event.outcome == AUDIT_OUTCOME_SUCCEEDED
                    assert event.actor_user_id == actor_id
                    assert event.request_id == "req-p106-success"
                    assert event.trace_id == "trace-p106-success"
                    event_id = event.id

                with session_factory() as session:
                    event = session.get(AuditEvent, event_id)
                    assert event is not None
                    event.outcome = "failed"
                    with pytest.raises((AuditError, DBAPIError)):
                        session.commit()
                    session.rollback()

                with engine.connect() as connection:
                    with pytest.raises(DBAPIError):
                        connection.execute(
                            text("UPDATE audit_events SET outcome = 'failed' WHERE id = :id"),
                            {"id": event_id},
                        )
                        connection.commit()
                    connection.rollback()
                    with pytest.raises(DBAPIError):
                        connection.execute(
                            text("DELETE FROM audit_events WHERE id = :id"),
                            {"id": event_id},
                        )
                        connection.commit()
                    connection.rollback()
                    remaining = connection.scalar(
                        text("SELECT count(*) FROM audit_events WHERE id = :id"),
                        {"id": event_id},
                    )
                    assert remaining == 1

                with session_factory() as session:
                    actor = session.get(User, actor_id)
                    target = session.get(User, target_id)
                    assert actor is not None and target is not None
                    target.is_disabled = False
                    session.commit()

                with session_factory() as session:
                    actor = session.get(User, actor_id)
                    target = session.get(User, target_id)
                    assert actor is not None and target is not None

                    def enable_then_bad_audit() -> User:
                        target.is_disabled = True
                        return target

                    with pytest.raises(AuditError) as exc_info:
                        commit_protected_mutation(
                            session,
                            enable_then_bad_audit,
                            event_name="not.an.allowed.event",
                            context=AuditContext(actor_user=actor, request_id="req-p106-fail"),
                            target_kind="user",
                            target_id=target_id,
                        )
                    assert exc_info.value.code == "audit_unavailable"

                with session_factory() as session:
                    persisted = session.get(User, target_id)
                    assert persisted is not None and persisted.is_disabled is False
                    leaked = session.scalar(
                        select(AuditEvent).where(AuditEvent.request_id == "req-p106-fail")
                    )
                    assert leaked is None

                with session_factory() as session:
                    AuditService(session).record(
                        AUDIT_EVENT_USER_DISABLED,
                        context=AuditContext(actor_kind="system", request_id="req-p106-insert"),
                        target_kind="user",
                        target_id=target_id,
                    )
                    session.commit()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
