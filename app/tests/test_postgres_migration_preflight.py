"""P12-01 Path 1: PostgreSQL 16 fresh-install, populated-current-target, and refusal matrix."""

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
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL, make_url

from context_engine.app import create_app
from context_engine.bootstrap_admin import bootstrap_initial_admin
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.migrate_release import MigrateReleaseError, run_migrate_release
from context_engine.services.readiness import (
    SUPPORTED_ALEMBIC_HEAD,
    ReadinessError,
    check_readiness,
)
from context_engine.services.schema_compatibility import (
    REASON_AHEAD,
    REASON_BEHIND,
    REASON_CURRENT_TARGET_OK,
    REASON_EMPTY_OK,
    REASON_EXTENSION,
    REASON_LEGACY,
    REASON_PARTIAL,
    REASON_RENAMED,
    REASON_UNKNOWN_HISTORY,
    REASON_UNKNOWN_OBJECT,
    collect_inventory_from_engine,
)


APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
BASELINE_REVISION = "724564649a13"
HEAD_REVISION = "c9e4b2d17a60"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p1201_[a-z_]+_[0-9a-f]{32}$")

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
    database_name = f"ce_p1201_{label}_{uuid4().hex}"
    assert DATABASE_NAME_PATTERN.fullmatch(database_name)
    database_url = admin_url.set(database=database_name)
    with admin_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}" TEMPLATE template0')
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


def _url_str(database_url: URL) -> str:
    return database_url.render_as_string(hide_password=False)


def _mutation_probe(engine: Engine) -> tuple[str | None, str]:
    inventory = collect_inventory_from_engine(engine)
    return inventory.alembic_revision, inventory.fingerprint()


def test_head_pin_matches_supported_constant() -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD


def test_p12_01_empty_fresh_install_through_migrate_release(tmp_path: Path) -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "fresh") as database_url:
            create_app(
                Settings(
                    database_url=_url_str(database_url),
                    testing=True,
                    source_storage_root=str(tmp_path / "source-storage"),
                )
            )
            probe = create_engine(database_url)
            try:
                assert inspect(probe).get_table_names() == []
            finally:
                probe.dispose()

            reason = run_migrate_release(database_url=_url_str(database_url))
            assert reason == REASON_EMPTY_OK

            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.check(config)

            settings = Settings(
                database_url=_url_str(database_url),
                testing=True,
                admin_username="p1201-admin@example.test",
                admin_password="Password123!",
                source_storage_root=str(tmp_path / "source-storage"),
            )
            bootstrap_initial_admin(settings)
            engine = create_db_engine(settings)
            try:
                session_factory = create_session_factory(engine)
                with session_factory() as db:
                    check_readiness(db, settings)
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p12_01_populated_current_target_accepts_noop_migrate(tmp_path: Path) -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "current") as database_url:
            assert run_migrate_release(database_url=_url_str(database_url)) == REASON_EMPTY_OK
            settings = Settings(
                database_url=_url_str(database_url),
                testing=True,
                admin_username="p1201-current@example.test",
                admin_password="Password123!",
                source_storage_root=str(tmp_path / "source-storage"),
            )
            bootstrap_initial_admin(settings)
            reason = run_migrate_release(database_url=_url_str(database_url))
            assert reason == REASON_CURRENT_TARGET_OK
            engine = create_db_engine(settings)
            try:
                with create_session_factory(engine)() as db:
                    check_readiness(db, settings)
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p12_01_legacy_wiki_table_refuses_without_mutation(tmp_path: Path) -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "legacy") as database_url:
            assert run_migrate_release(database_url=_url_str(database_url)) == REASON_EMPTY_OK
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(text("CREATE TABLE wiki_pages (id uuid PRIMARY KEY)"))
                before = _mutation_probe(engine)
            finally:
                engine.dispose()

            with pytest.raises(MigrateReleaseError) as exc:
                run_migrate_release(database_url=_url_str(database_url))
            assert exc.value.reason == REASON_LEGACY

            engine = create_engine(database_url)
            try:
                assert _mutation_probe(engine) == before
                with pytest.raises(ReadinessError) as ready_exc:
                    with create_session_factory(engine)() as db:
                        check_readiness(
                            db,
                            Settings(
                                database_url=_url_str(database_url),
                                testing=True,
                                source_storage_root=str(tmp_path / "source-storage"),
                            ),
                        )
                assert ready_exc.value.reason == "schema_incompatible"
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p12_01_behind_head_refuses_without_mutation() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "behind") as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, BASELINE_REVISION)
            engine = create_engine(database_url)
            try:
                before = _mutation_probe(engine)
            finally:
                engine.dispose()

            with pytest.raises(MigrateReleaseError) as exc:
                run_migrate_release(database_url=_url_str(database_url))
            assert exc.value.reason == REASON_BEHIND

            engine = create_engine(database_url)
            try:
                assert _mutation_probe(engine) == before
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p12_01_ahead_and_unknown_history_refuse_without_mutation() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "ahead") as database_url:
            assert run_migrate_release(database_url=_url_str(database_url)) == REASON_EMPTY_OK
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text("UPDATE alembic_version SET version_num = :version"),
                        {"version": "zzzzfuture0001"},
                    )
                before = _mutation_probe(engine)
            finally:
                engine.dispose()

            with pytest.raises(MigrateReleaseError) as exc:
                run_migrate_release(database_url=_url_str(database_url))
            assert exc.value.reason in {REASON_AHEAD, REASON_UNKNOWN_HISTORY}

            engine = create_engine(database_url)
            try:
                assert _mutation_probe(engine) == before
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p12_01_unknown_extra_table_and_rename_refuse() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "extra") as database_url:
            assert run_migrate_release(database_url=_url_str(database_url)) == REASON_EMPTY_OK
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(text("CREATE TABLE mystery_extra (id int PRIMARY KEY)"))
                before = _mutation_probe(engine)
            finally:
                engine.dispose()
            with pytest.raises(MigrateReleaseError) as exc:
                run_migrate_release(database_url=_url_str(database_url))
            assert exc.value.reason == REASON_UNKNOWN_OBJECT
            engine = create_engine(database_url)
            try:
                assert _mutation_probe(engine) == before
                with engine.begin() as connection:
                    connection.execute(text("DROP TABLE mystery_extra"))
                    connection.execute(text("ALTER TABLE users RENAME TO users_renamed"))
                before_rename = _mutation_probe(engine)
            finally:
                engine.dispose()
            with pytest.raises(MigrateReleaseError) as exc:
                run_migrate_release(database_url=_url_str(database_url))
            assert exc.value.reason in {REASON_RENAMED, REASON_PARTIAL, REASON_UNKNOWN_OBJECT}
            engine = create_engine(database_url)
            try:
                assert _mutation_probe(engine) == before_rename
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p12_01_missing_table_is_partial() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "partial") as database_url:
            assert run_migrate_release(database_url=_url_str(database_url)) == REASON_EMPTY_OK
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(text("DROP TABLE prompt_templates CASCADE"))
                before = _mutation_probe(engine)
            finally:
                engine.dispose()
            with pytest.raises(MigrateReleaseError) as exc:
                run_migrate_release(database_url=_url_str(database_url))
            assert exc.value.reason == REASON_PARTIAL
            engine = create_engine(database_url)
            try:
                assert _mutation_probe(engine) == before
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p12_01_forbidden_extension_refuses_empty_like_db() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "ext") as database_url:
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    try:
                        connection.execute(text("CREATE EXTENSION pgcrypto"))
                    except Exception as exc:  # pragma: no cover - environment-specific
                        pytest.skip(f"pgcrypto unavailable: {exc}")
                before = _mutation_probe(engine)
            finally:
                engine.dispose()
            with pytest.raises(MigrateReleaseError) as exc:
                run_migrate_release(database_url=_url_str(database_url))
            assert exc.value.reason == REASON_EXTENSION
            engine = create_engine(database_url)
            try:
                assert _mutation_probe(engine) == before
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
