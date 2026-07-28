"""P7-04 U6: PostgreSQL attach/cancel/lease races for sealed turn execution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import os
from pathlib import Path
import re
from threading import Barrier, Event
from typing import Any, Iterable
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    TURN_EVENT_ANSWER_DELTA,
    TURN_EVENT_CANCELLED,
    TURN_EVENT_COMPLETED,
    TURN_STATUS_CANCELLED,
    TURN_STATUS_COMPLETED,
    TURN_STATUS_RUNNING,
    AuthSession,
    ConversationTurn,
    ConversationTurnEvent,
    User,
)
from context_engine.services.audit import AuditContext
from context_engine.services.chat_turns import (
    ConversationTurnWorker,
    SynthesisStreamAdapter,
    cancel_turn,
    start_or_replay_turn,
)
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p704_[a-z0-9_]+$")
HEAD_REVISION = "d4e7a1b92c80"

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
    database_name = f"ce_p704_turn_leases_{uuid4().hex}"
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
        turn_lease_seconds=120,
        synthesis_timeout_seconds=30,
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
                "VALUES (:id,'p704-owner@example.test','synthetic-password-hash',"
                "'member',false,:now,:now,:now)"
            ),
            {"id": owner_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO conversations "
                "(id,public_ref,owner_user_id,title,version,created_at,updated_at) "
                "VALUES (:id,:public_ref,:owner_id,'P7-04 race',1,:now,:now)"
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
    """Workers still resolve TrustedRuntimeResolver even with injected adapters."""
    seed_runtime_config(db)
    rotate_provider_credential(
        db,
        "openai",
        "sk-test-openai-p704",
        SecretCrypto.from_settings(settings),
        expected_version=1,
        audit_context=AuditContext(actor_user=owner, request_id="req-p704-runtime"),
    )


def test_p7_04_supported_alembic_head_includes_turn_leases() -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD


def test_m10_concurrent_identical_start_attaches_once_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            engine = create_engine(database_url)
            owner_id, conversation_ref, auth_session_id = _seed_owner_conversation(engine)
            settings = _settings(database_url)
            contenders = Barrier(2)

            def contender() -> tuple[str, bool]:
                with Session(engine) as db:
                    contenders.wait()
                    owner = db.get(User, owner_id)
                    auth_session = db.get(AuthSession, auth_session_id)
                    assert owner is not None and auth_session is not None
                    result = start_or_replay_turn(
                        db,
                        settings=settings,
                        owner=owner,
                        auth_session=auth_session,
                        conversation_id=conversation_ref,
                        client_request_id="identical-attach-request",
                        message="Answer this once.",
                        domain_id=None,
                    )
                    return result.turn.public_ref, result.replay

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = [future.result(timeout=20) for future in [executor.submit(contender) for _ in range(2)]]

            assert len({turn_ref for turn_ref, _ in results}) == 1
            assert {replay for _, replay in results} == {False, True}
            with engine.connect() as connection:
                assert connection.scalar(
                    text(
                        "SELECT count(*) FROM conversation_turns "
                        "WHERE client_request_id = 'identical-attach-request'"
                    )
                ) == 1
            engine.dispose()
    finally:
        admin_engine.dispose()


def test_m10_fingerprint_conflict_rejects_second_start_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            engine = create_engine(database_url)
            owner_id, conversation_ref, auth_session_id = _seed_owner_conversation(engine)
            settings = _settings(database_url)
            with Session(engine) as db:
                owner = db.get(User, owner_id)
                auth_session = db.get(AuthSession, auth_session_id)
                assert owner is not None and auth_session is not None
                first = start_or_replay_turn(
                    db,
                    settings=settings,
                    owner=owner,
                    auth_session=auth_session,
                    conversation_id=conversation_ref,
                    client_request_id="conflict-request",
                    message="First message.",
                    domain_id=None,
                )
                assert first.replay is False
                with pytest.raises(Exception) as conflict:
                    start_or_replay_turn(
                        db,
                        settings=settings,
                        owner=owner,
                        auth_session=auth_session,
                        conversation_id=conversation_ref,
                        client_request_id="conflict-request",
                        message="Changed message.",
                        domain_id=None,
                    )
                assert conflict.value.status_code == 409
                assert conflict.value.code == "client_request_conflict"
            engine.dispose()
    finally:
        admin_engine.dispose()


def test_c01_cancel_vs_worker_keeps_single_terminal_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            engine = create_engine(database_url)
            owner_id, conversation_ref, auth_session_id = _seed_owner_conversation(engine)
            settings = _settings(database_url)
            with Session(engine) as db:
                owner = db.get(User, owner_id)
                auth_session = db.get(AuthSession, auth_session_id)
                assert owner is not None and auth_session is not None
                _seed_synthesis_runtime(db, settings, owner)
                start = start_or_replay_turn(
                    db,
                    settings=settings,
                    owner=owner,
                    auth_session=auth_session,
                    conversation_id=conversation_ref,
                    client_request_id="cancel-race-request",
                    message="Cancel during synthesis.",
                    domain_id=None,
                )
                turn_id = start.turn.id
                turn_public_ref = start.turn.public_ref

            first_delta_ready = Event()
            cancel_committed = Event()

            class GatedSynthesis(SynthesisStreamAdapter):
                def stream_direct(self, **_kwargs: Any) -> Iterable[str]:
                    yield "Hello "
                    first_delta_ready.set()
                    assert cancel_committed.wait(timeout=15)
                    # Resume after cancel sealed; fence must stop further deltas.
                    yield "world"

                def stream_grounded(self, **_kwargs: Any) -> Iterable[str]:
                    raise AssertionError("direct turn must not call grounded synthesis")

            def run_worker() -> None:
                with Session(engine) as db:
                    ConversationTurnWorker(
                        settings,
                        synthesis_adapter=GatedSynthesis(),
                    ).run_once(db)

            def run_cancel() -> None:
                assert first_delta_ready.wait(timeout=15)
                with Session(engine) as db:
                    owner = db.get(User, owner_id)
                    auth_session = db.get(AuthSession, auth_session_id)
                    assert owner is not None and auth_session is not None
                    cancel_turn(
                        db,
                        settings=settings,
                        owner=owner,
                        auth_session=auth_session,
                        conversation_id=conversation_ref,
                        turn_id=turn_public_ref,
                    )
                cancel_committed.set()

            with ThreadPoolExecutor(max_workers=2) as executor:
                worker_future = executor.submit(run_worker)
                cancel_future = executor.submit(run_cancel)
                worker_exc = worker_future.exception(timeout=20)
                cancel_exc = cancel_future.exception(timeout=20)
                if worker_exc is not None:
                    raise worker_exc
                if cancel_exc is not None:
                    raise cancel_exc

            with Session(engine) as db:
                turn = db.get(ConversationTurn, turn_id)
                assert turn is not None
                assert turn.status == TURN_STATUS_CANCELLED
                types = list(
                    db.scalars(
                        select(ConversationTurnEvent.event_type)
                        .where(ConversationTurnEvent.turn_id == turn.id)
                        .order_by(ConversationTurnEvent.sequence)
                    )
                )
                assert types.count(TURN_EVENT_CANCELLED) == 1
                assert TURN_EVENT_COMPLETED not in types
                assert types.count(TURN_EVENT_ANSWER_DELTA) <= 1
            engine.dispose()
    finally:
        admin_engine.dispose()


def test_ae1_expired_lease_reclaim_fails_closed_after_answer_delta_on_postgresql_16() -> None:
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
                start = start_or_replay_turn(
                    db,
                    settings=settings_a,
                    owner=owner,
                    auth_session=auth_session,
                    conversation_id=conversation_ref,
                    client_request_id="reclaim-request",
                    message="Reclaim after partial answer.",
                    domain_id=None,
                )
                turn = start.turn
                turn.lease_owner = "turn-worker-a"
                turn.lease_expires_at = utc_now() - timedelta(seconds=1)
                turn.execution_generation = 1
                db.commit()
                from context_engine.services.chat_turns import _persist_event

                _persist_event(
                    db,
                    turn=turn,
                    event_type=TURN_EVENT_ANSWER_DELTA,
                    payload={"text": "Partial."},
                    execution_generation=1,
                )

            with Session(engine) as db:
                claimed = ConversationTurnWorker(settings_b).run_once(db)
                assert claimed is True
                turn = db.scalar(
                    select(ConversationTurn).where(
                        ConversationTurn.client_request_id == "reclaim-request"
                    )
                )
                assert turn is not None
                db.refresh(turn)
                types = list(
                    db.scalars(
                        select(ConversationTurnEvent.event_type)
                        .where(ConversationTurnEvent.turn_id == turn.id)
                        .order_by(ConversationTurnEvent.sequence)
                    )
                )
                assert TURN_EVENT_ANSWER_DELTA in types
                assert "turn.failed" in types
                assert turn.status == "failed"
                assert turn.safe_error_code == "provider_failure"
                assert turn.assistant_answer is None
            engine.dispose()
    finally:
        admin_engine.dispose()


def test_c01_disconnect_without_cancel_allows_completion_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            engine = create_engine(database_url)
            owner_id, conversation_ref, auth_session_id = _seed_owner_conversation(engine)
            settings = _settings(database_url)

            class ImmediateSynthesis(SynthesisStreamAdapter):
                def stream_direct(self, **_kwargs: Any) -> Iterable[str]:
                    yield "Survived disconnect."

                def stream_grounded(self, **_kwargs: Any) -> Iterable[str]:
                    raise AssertionError("direct turn must not call grounded synthesis")

            with Session(engine) as db:
                owner = db.get(User, owner_id)
                auth_session = db.get(AuthSession, auth_session_id)
                assert owner is not None and auth_session is not None
                _seed_synthesis_runtime(db, settings, owner)
                start = start_or_replay_turn(
                    db,
                    settings=settings,
                    owner=owner,
                    auth_session=auth_session,
                    conversation_id=conversation_ref,
                    client_request_id="disconnect-survives",
                    message="Keep working after disconnect.",
                    domain_id=None,
                )
                turn_id = start.turn.id
                # Disconnect path must not call cancel.
                assert db.get(ConversationTurn, turn_id).status == TURN_STATUS_RUNNING

            with Session(engine) as db:
                assert ConversationTurnWorker(
                    settings,
                    synthesis_adapter=ImmediateSynthesis(),
                ).run_once(db)
                turn = db.get(ConversationTurn, turn_id)
                assert turn is not None
                assert turn.status == TURN_STATUS_COMPLETED
                assert turn.assistant_answer == "Survived disconnect."
                assert turn.stop_reason == "direct_llm"
            engine.dispose()
    finally:
        admin_engine.dispose()
