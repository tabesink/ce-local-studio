"""P7-06 U3: PostgreSQL turn lease heartbeat reclaim barriers — Covers AE3/AE4."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import os
from pathlib import Path
import re
from threading import Event
import time
from typing import Any, Iterable
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    TURN_STATUS_COMPLETED,
    TURN_STATUS_RUNNING,
    AuthSession,
    ConversationTurn,
    User,
)
from context_engine.services.audit import AuditContext
from context_engine.services.chat_turns import (
    ConversationTurnWorker,
    SynthesisStreamAdapter,
    start_or_replay_turn,
)
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p706_[a-z0-9_]+$")

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
    database_name = f"ce_p706_turn_hb_{uuid4().hex}"
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


def _settings(database_url: URL, *, worker_id: str = "turn-worker-a") -> Settings:
    return Settings(
        database_url=database_url.render_as_string(hide_password=False),
        testing=True,
        turn_worker_id=worker_id,
        turn_lease_seconds=9,
        synthesis_timeout_seconds=3,
    )


def _seed_owner_conversation(engine: Engine) -> tuple[str, str, str]:
    now = utc_now()
    owner_id = str(uuid4())
    conversation_id = str(uuid4())
    conversation_ref = f"conv_{uuid4().hex}"
    auth_session_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users "
                "(id,username,password_hash,role,is_disabled,created_at,updated_at,password_changed_at) "
                "VALUES (:id,:username,'synthetic-password-hash','member',false,:now,:now,:now)"
            ),
            {"id": owner_id, "username": f"p706-owner-{uuid4().hex[:8]}@example.test", "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO conversations "
                "(id,public_ref,owner_user_id,title,version,created_at,updated_at) "
                "VALUES (:id,:public_ref,:owner_id,'P7-06 heartbeat',1,:now,:now)"
            ),
            {
                "id": conversation_id,
                "public_ref": conversation_ref,
                "owner_id": owner_id,
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO auth_sessions "
                "(id,user_id,token_hash,expires_at,revoked_at,created_at,last_used_at) "
                "VALUES (:id,:user_id,:token_hash,:expires_at,null,:now,:now)"
            ),
            {
                "id": auth_session_id,
                "user_id": owner_id,
                "token_hash": "b" * 64,
                "expires_at": now + timedelta(hours=1),
                "now": now,
            },
        )
    return owner_id, conversation_ref, auth_session_id


def _seed_synthesis_runtime(db: Session, settings: Settings, owner: User) -> None:
    seed_runtime_config(db)
    rotate_provider_credential(
        db,
        "openai",
        "sk-test-openai-p706",
        SecretCrypto.from_settings(settings),
        expected_version=1,
        audit_context=AuditContext(actor_user=owner, request_id="req-p706-runtime"),
    )


def test_ae3_live_heartbeat_blocks_second_worker_claim_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            engine = create_engine(database_url)
            owner_id, conversation_ref, auth_session_id = _seed_owner_conversation(engine)
            settings_a = _settings(database_url, worker_id="turn-worker-a")
            settings_b = _settings(database_url, worker_id="turn-worker-b")
            with Session(engine) as db:
                owner = db.get(User, owner_id)
                auth_session = db.get(AuthSession, auth_session_id)
                assert owner is not None and auth_session is not None
                _seed_synthesis_runtime(db, settings_a, owner)
                start = start_or_replay_turn(
                    db,
                    settings=settings_a,
                    owner=owner,
                    auth_session=auth_session,
                    conversation_id=conversation_ref,
                    client_request_id="hb-ae3-request",
                    message="Hold lease with heartbeat.",
                    domain_id=None,
                )
                turn_id = start.turn.id

            first_delta_ready = Event()
            release_synthesis = Event()
            transport_calls = {"count": 0}

            class GatedSynthesis(SynthesisStreamAdapter):
                def stream_direct(self, **_kwargs: Any) -> Iterable[str]:
                    transport_calls["count"] += 1
                    yield "Hello "
                    first_delta_ready.set()
                    assert release_synthesis.wait(timeout=20)
                    yield "world"

                def stream_grounded(self, **_kwargs: Any) -> Iterable[str]:
                    raise AssertionError("direct turn must not call grounded synthesis")

            def run_worker_a() -> None:
                with Session(engine) as db:
                    ConversationTurnWorker(
                        settings_a,
                        synthesis_adapter=GatedSynthesis(),
                    ).run_once(db)

            with ThreadPoolExecutor(max_workers=1) as executor:
                worker_future = executor.submit(run_worker_a)
                assert first_delta_ready.wait(timeout=15)

                with Session(engine) as db:
                    turn = db.get(ConversationTurn, turn_id)
                    assert turn is not None
                    generation_a = turn.execution_generation
                    expires_a = turn.lease_expires_at
                    assert turn.lease_owner == "turn-worker-a"
                    assert expires_a is not None

                # Allow at least one heartbeat cadence (lease/3 == 3s).
                time.sleep(3.5)
                with Session(engine) as db:
                    turn = db.get(ConversationTurn, turn_id)
                    assert turn is not None
                    assert turn.lease_owner == "turn-worker-a"
                    assert turn.execution_generation == generation_a
                    assert turn.lease_expires_at is not None
                    assert turn.lease_expires_at > expires_a

                with Session(engine) as db:
                    claimed = ConversationTurnWorker(
                        settings_b,
                        synthesis_adapter=GatedSynthesis(),
                    ).run_once(db)
                    assert claimed is False

                with Session(engine) as db:
                    turn = db.get(ConversationTurn, turn_id)
                    assert turn is not None
                    assert turn.lease_owner == "turn-worker-a"
                    assert turn.execution_generation == generation_a
                    assert turn.status == TURN_STATUS_RUNNING

                release_synthesis.set()
                worker_exc = worker_future.exception(timeout=20)
                if worker_exc is not None:
                    raise worker_exc

            with Session(engine) as db:
                turn = db.get(ConversationTurn, turn_id)
                assert turn is not None
                assert turn.status == TURN_STATUS_COMPLETED
            assert transport_calls["count"] == 1
            engine.dispose()
    finally:
        admin_engine.dispose()


def test_ae4_expired_lease_without_heartbeat_allows_reclaim_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            engine = create_engine(database_url)
            owner_id, conversation_ref, auth_session_id = _seed_owner_conversation(engine)
            settings_a = _settings(database_url, worker_id="turn-worker-a")
            settings_b = _settings(database_url, worker_id="turn-worker-b")
            with Session(engine) as db:
                owner = db.get(User, owner_id)
                auth_session = db.get(AuthSession, auth_session_id)
                assert owner is not None and auth_session is not None
                _seed_synthesis_runtime(db, settings_a, owner)
                start = start_or_replay_turn(
                    db,
                    settings=settings_a,
                    owner=owner,
                    auth_session=auth_session,
                    conversation_id=conversation_ref,
                    client_request_id="hb-ae4-request",
                    message="Expire then reclaim.",
                    domain_id=None,
                )
                turn = start.turn
                generation_before = 1
                turn.lease_owner = "turn-worker-a"
                turn.lease_expires_at = utc_now() - timedelta(seconds=1)
                turn.execution_generation = generation_before
                turn.claimable_at = utc_now() - timedelta(seconds=1)
                turn.status = TURN_STATUS_RUNNING
                db.commit()
                turn_id = turn.id

            class FastSynthesis(SynthesisStreamAdapter):
                def stream_direct(self, **_kwargs: Any) -> Iterable[str]:
                    yield "reclaimed"

                def stream_grounded(self, **_kwargs: Any) -> Iterable[str]:
                    raise AssertionError("direct only")

            with Session(engine) as db:
                claimed_b = ConversationTurnWorker(
                    settings_b,
                    synthesis_adapter=FastSynthesis(),
                ).run_once(db)
                assert claimed_b is True
                turn = db.get(ConversationTurn, turn_id)
                assert turn is not None
                assert turn.execution_generation > generation_before
                assert turn.status == TURN_STATUS_COMPLETED
                assert turn.assistant_answer == "reclaimed"
            engine.dispose()
    finally:
        admin_engine.dispose()
