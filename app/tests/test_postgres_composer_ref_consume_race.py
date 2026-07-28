"""P11-02 / AE5: PostgreSQL concurrent one-use consume race for composer refs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import os
from pathlib import Path
import re
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session

from context_engine.db import utc_now
from context_engine.dev.seed_prompt_templates import (
    TEMPLATE_SAFETY_SUMMARY_ID,
    seed_prompt_template_fixtures,
)
from context_engine.models import COMPOSER_REF_KIND_TEMPLATE, ComposerRefToken, User
from context_engine.services.composer_refs import (
    ComposerRefError,
    _token_hash,
    consume_composer_ref_tokens,
)
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p1102_[a-z0-9_]+$")
HEAD_REVISION = "c9e4b2d17a60"

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


def _assert_postgresql_16(admin_engine: Engine) -> None:
    with admin_engine.connect() as connection:
        version_num = int(connection.scalar(text("SHOW server_version_num")))
    assert 160000 <= version_num < 170000


@contextmanager
def _disposable_database(admin_engine: Engine, admin_url: URL):
    database_name = f"ce_p1102_composer_consume_{uuid4().hex}"
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
    config.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return config


def test_p11_02_supported_alembic_head_includes_consumed_at() -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD


def test_ae5_concurrent_consume_serializes_one_winner_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            engine = create_engine(database_url)
            now = utc_now()
            owner_id = str(uuid4())
            raw_token = f"ce-p11-02-race-{uuid4().hex}"
            token_hash = _token_hash(raw_token)
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id,username,password_hash,role,is_disabled,created_at,updated_at,password_changed_at) "
                        "VALUES (:id,'p1102-owner@example.test','synthetic-password-hash',"
                        "'member',false,:now,:now,:now)"
                    ),
                    {"id": owner_id, "now": now},
                )
            with Session(engine) as db:
                seed_prompt_template_fixtures(
                    db,
                    environment="test",
                    allow_test_seed="true",
                )
                db.add(
                    ComposerRefToken(
                        id=str(uuid4()),
                        token_hash=token_hash,
                        owner_user_id=owner_id,
                        ref_kind=COMPOSER_REF_KIND_TEMPLATE,
                        target_id=TEMPLATE_SAFETY_SUMMARY_ID,
                        domain_id=None,
                        safe_label="Race template",
                        safe_description=None,
                        expires_at=now + timedelta(hours=1),
                        created_at=now,
                    )
                )
                db.commit()

            contenders = Barrier(2)

            def contender() -> str:
                with Session(engine) as db:
                    owner = db.get(User, owner_id)
                    assert owner is not None
                    contenders.wait()
                    try:
                        consume_composer_ref_tokens(db, owner=owner, tokens=(raw_token,))
                        db.commit()
                        return "consumed"
                    except ComposerRefError as exc:
                        db.rollback()
                        assert exc.code == "composer_ref_unavailable"
                        return "denied"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = [
                    future.result(timeout=20)
                    for future in [executor.submit(contender) for _ in range(2)]
                ]

            assert sorted(outcomes) == ["consumed", "denied"]
            with Session(engine) as db:
                row = db.scalar(select(ComposerRefToken).where(ComposerRefToken.token_hash == token_hash))
                assert row is not None
                assert row.consumed_at is not None
            engine.dispose()
    finally:
        admin_engine.dispose()
