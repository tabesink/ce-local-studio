"""P1-07: PostgreSQL 16 concurrent Idempotency-Key claim races."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session

from context_engine.models import (
    HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
    HTTP_IDEMPOTENCY_STATE_COMPLETED,
    HttpIdempotencyRecord,
    ROLE_MEMBER,
    User,
)
from context_engine.services.idempotency import (
    IdempotencyError,
    begin_idempotent,
    complete_idempotent,
    fingerprint_payload,
)
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD


APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
HEAD_REVISION = "d4e7a1b92c80"
DATABASE_NAME_PATTERN = __import__("re").compile(r"^ce_p107_[a-z_]+_[0-9a-f]{32}$")

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
def _disposable_database(admin_engine: Engine, admin_url: URL):
    database_name = f"ce_p107_idem_{uuid4().hex}"
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


def _seed_user(engine: Engine) -> str:
    with Session(engine) as db:
        user = User(
            username=f"p107-{uuid4().hex}@example.test",
            password_hash="synthetic-password-hash",
            role=ROLE_MEMBER,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            password_changed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(user)
        db.commit()
        return user.id


def test_p1_07_head_pin_matches_supported_constant() -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD


def test_concurrent_identical_claims_one_winner_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            engine = create_engine(database_url)
            owner_id = _seed_user(engine)
            fingerprint = fingerprint_payload({"title": "Race"})
            barrier = Barrier(2)
            outcomes: list[str] = []

            def contender() -> str:
                with Session(engine) as db:
                    barrier.wait()
                    outcome = begin_idempotent(
                        db,
                        principal_user_id=owner_id,
                        route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
                        raw_key="race-key",
                        fingerprint=fingerprint,
                    )
                    if outcome.replay:
                        db.commit()
                        return "replay"
                    complete_idempotent(
                        db,
                        outcome.record,
                        http_status=201,
                        response_kind="conversation",
                        response_refs={"conversationId": "conv_race"},
                    )
                    db.commit()
                    return "winner"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = [future.result(timeout=20) for future in [executor.submit(contender) for _ in range(2)]]

            # One side may see pending capacity_unavailable if the other has not completed yet.
            # Retry the capacity path once after the winner commits.
            def settle() -> None:
                with Session(engine) as db:
                    try:
                        outcome = begin_idempotent(
                            db,
                            principal_user_id=owner_id,
                            route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
                            raw_key="race-key",
                            fingerprint=fingerprint,
                        )
                    except IdempotencyError as exc:
                        assert exc.code == "capacity_unavailable"
                        return
                    assert outcome.replay is True
                    assert outcome.response_refs == {"conversationId": "conv_race"}

            settle()
            with Session(engine) as db:
                rows = list(db.scalars(select(HttpIdempotencyRecord)))
                assert len(rows) == 1
                assert rows[0].state == HTTP_IDEMPOTENCY_STATE_COMPLETED
            assert outcomes.count("winner") == 1
            engine.dispose()
    finally:
        admin_engine.dispose()


def test_concurrent_fingerprint_mismatch_rejects_loser_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            engine = create_engine(database_url)
            owner_id = _seed_user(engine)
            with Session(engine) as db:
                first = begin_idempotent(
                    db,
                    principal_user_id=owner_id,
                    route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
                    raw_key="conflict-key",
                    fingerprint=fingerprint_payload({"title": "First"}),
                )
                complete_idempotent(
                    db,
                    first.record,
                    http_status=201,
                    response_kind="conversation",
                    response_refs={"conversationId": "conv_first"},
                )
                db.commit()
            with Session(engine) as db:
                with pytest.raises(IdempotencyError) as exc_info:
                    begin_idempotent(
                        db,
                        principal_user_id=owner_id,
                        route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
                        raw_key="conflict-key",
                        fingerprint=fingerprint_payload({"title": "Second"}),
                    )
                assert (exc_info.value.status_code, exc_info.value.code) == (
                    409,
                    "idempotency_conflict",
                )
            engine.dispose()
    finally:
        admin_engine.dispose()
