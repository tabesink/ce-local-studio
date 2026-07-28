from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, inspect, select, text, update
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import context_engine.services.chat_turns as chat_turns_module
from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import TURN_ROUTE_DIRECT_LLM, AuthSession, Conversation, User
from context_engine.services.chat_turns import claim_turn
from context_engine.services.conversations import (
    ConversationError,
    delete_conversation,
    update_conversation_title,
)
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p701_[a-z0-9_]+$")
HEAD_REVISION = "c9e4b2d17a60"
PRIOR_REVISION = "b5c8e2d19f47"

pytestmark = pytest.mark.postgresql


def _required_admin_url() -> URL:
    if os.getenv(OPT_IN_ENV) != "1":
        pytest.skip(f"set {OPT_IN_ENV}=1 to allow disposable PostgreSQL database tests")
    raw_url = os.getenv(ADMIN_URL_ENV)
    if not raw_url:
        pytest.fail(f"{ADMIN_URL_ENV} is required when disposable database tests are enabled")
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
    database_name = f"ce_p701_conversations_{uuid4().hex}"
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


def test_p7_01_conversation_migration_upgrade_defaults_and_rollback_on_postgresql_16() -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, PRIOR_REVISION)
            engine = create_engine(database_url)
            payload = {
                "conversationId": "11111111-1111-4111-8111-111111111111",
                "clientRequestId": "legacy-request-001",
                "replay": False,
            }
            payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
            payload_digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            now = datetime(2026, 7, 26, 12, 0, 0)
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id,username,password_hash,role,is_disabled,created_at,updated_at,password_changed_at) "
                        "VALUES (:id,:username,:password_hash,'member',false,:now,:now,:now)"
                    ),
                    {
                        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                        "username": "migration-owner@example.test",
                        "password_hash": "synthetic-password-hash",
                        "now": now,
                    },
                )
                connection.execute(
                    text(
                        "INSERT INTO conversations (id,owner_user_id,title,created_at,updated_at) "
                        "VALUES (:id,:owner_id,'Legacy conversation',:now,:now)"
                    ),
                    {
                        "id": payload["conversationId"],
                        "owner_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                        "now": now,
                    },
                )
                connection.execute(
                    text(
                        "INSERT INTO conversation_turns "
                        "(id,conversation_id,client_request_id,trace_id,domain_id,route,status,"
                        "stop_reason,user_message,assistant_answer,safe_error_code,safe_error_message,"
                        "composer_ref_fingerprint,plan_step_count,retrieval_operation_count,"
                        "repair_attempt_count,created_at,started_at,completed_at,updated_at) "
                        "VALUES (:id,:conversation_id,'legacy-request-001',null,null,'direct_llm',"
                        "'completed','direct_llm','Legacy question','Legacy answer',null,null,"
                        ":fingerprint,0,0,0,:now,:now,:now,:now)"
                    ),
                    {
                        "id": "22222222-2222-4222-8222-222222222222",
                        "conversation_id": payload["conversationId"],
                        "fingerprint": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "now": now,
                    },
                )
                connection.execute(
                    text(
                        "INSERT INTO conversation_turn_events "
                        "(id,turn_id,sequence,schema_version,event_type,payload_json,payload_digest,occurred_at) "
                        "VALUES ('evt_legacy','22222222-2222-4222-8222-222222222222',1,'1.0',"
                        "'turn.accepted',:payload_json,:payload_digest,:now)"
                    ),
                    {"payload_json": payload_json, "payload_digest": payload_digest, "now": now},
                )

            command.upgrade(config, "head")
            with engine.begin() as connection:
                conversation = connection.execute(
                    text(
                        "SELECT public_ref,version FROM conversations "
                        "WHERE id = '11111111-1111-4111-8111-111111111111'"
                    )
                ).one()
                turn = connection.execute(
                    text(
                        "SELECT public_ref FROM conversation_turns "
                        "WHERE id = '22222222-2222-4222-8222-222222222222'"
                    )
                ).one()
                event = connection.execute(
                    text(
                        "SELECT payload_json,payload_digest FROM conversation_turn_events "
                        "WHERE id = 'evt_legacy'"
                    )
                ).one()
                assert re.fullmatch(r"conv_[0-9a-f]{32}", conversation.public_ref)
                assert re.fullmatch(r"turn_[0-9a-f]{32}", turn.public_ref)
                assert conversation.version == 1
                assert event == (payload_json, payload_digest)

                connection.execute(
                    text(
                        "INSERT INTO conversations (id,owner_user_id,title,created_at,updated_at) "
                        "VALUES ('33333333-3333-4333-8333-333333333333',"
                        "'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','Rollback compatible',:now,:now)"
                    ),
                    {"now": now},
                )
                connection.execute(
                    text(
                        "INSERT INTO conversation_turns "
                        "(id,conversation_id,client_request_id,trace_id,domain_id,route,status,"
                        "stop_reason,user_message,assistant_answer,safe_error_code,safe_error_message,"
                        "composer_ref_fingerprint,plan_step_count,retrieval_operation_count,"
                        "repair_attempt_count,created_at,started_at,completed_at,updated_at) "
                        "VALUES ('44444444-4444-4444-8444-444444444444',"
                        "'33333333-3333-4333-8333-333333333333','rollback-request',null,null,"
                        "'direct_llm','running',null,'Question',null,null,null,:fingerprint,0,0,0,"
                        ":now,:now,null,:now)"
                    ),
                    {
                        "fingerprint": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "now": now,
                    },
                )
                defaults = {
                    column["name"]: str(column["default"])
                    for column in inspect(connection).get_columns("conversations")
                }
                assert "gen_random_uuid" in defaults["public_ref"]
                turn_defaults = {
                    column["name"]: str(column["default"])
                    for column in inspect(connection).get_columns("conversation_turns")
                }
                assert "gen_random_uuid" in turn_defaults["public_ref"]
                indexes = {index["name"] for index in inspect(connection).get_indexes("conversations")}
                assert {
                    "uq_conversations_public_ref",
                    "ix_conversations_owner_created",
                    "ix_conversations_owner_updated",
                } <= indexes
                for offset, event_name in enumerate(
                    ("conversation.created", "conversation.renamed", "conversation.deleted"),
                    start=1,
                ):
                    connection.execute(
                        text(
                            "INSERT INTO audit_events "
                            "(id,event_name,actor_kind,actor_user_id,target_kind,target_id,"
                            "request_id,trace_id,outcome,safe_error_code,metadata_json,created_at) "
                            "VALUES (:id,:event_name,'member',"
                            "'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','conversation',"
                            "'conv_rollback_proof',null,null,'succeeded',null,null,:now)"
                        ),
                        {
                            "id": f"55555555-5555-4555-8555-55555555555{offset}",
                            "event_name": event_name,
                            "now": now,
                        },
                    )

            command.downgrade(config, PRIOR_REVISION)
            with engine.connect() as connection:
                assert "public_ref" not in {
                    column["name"] for column in inspect(connection).get_columns("conversations")
                }
                assert connection.scalar(
                    text("SELECT payload_digest FROM conversation_turn_events WHERE id = 'evt_legacy'")
                ) == payload_digest
                assert connection.scalar(
                    text(
                        "SELECT count(*) FROM audit_events "
                        "WHERE event_name IN "
                        "('conversation.created','conversation.renamed','conversation.deleted')"
                    )
                ) == 3
            engine.dispose()
    finally:
        admin_engine.dispose()


def test_p7_01_delete_and_turn_insert_serialize_without_orphan_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            engine = create_engine(database_url)
            now = datetime(2026, 7, 26, 13, 0, 0)
            owner_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            conversation_id = "11111111-1111-4111-8111-111111111111"
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id,username,password_hash,role,is_disabled,created_at,updated_at,password_changed_at) "
                        "VALUES (:id,'race-owner@example.test','synthetic-password-hash',"
                        "'member',false,:now,:now,:now)"
                    ),
                    {"id": owner_id, "now": now},
                )
                connection.execute(
                    text(
                        "INSERT INTO conversations (id,owner_user_id,title,created_at,updated_at) "
                        "VALUES (:id,:owner_id,'Race proof',:now,:now)"
                    ),
                    {"id": conversation_id, "owner_id": owner_id, "now": now},
                )

            contenders = Barrier(2)

            def delete_parent() -> None:
                with engine.begin() as connection:
                    connection.execute(
                        text("SELECT id FROM conversations WHERE id = :id FOR UPDATE"),
                        {"id": conversation_id},
                    ).one()
                    contenders.wait()
                    connection.execute(
                        text("DELETE FROM conversations WHERE id = :id"),
                        {"id": conversation_id},
                    )

            def insert_turn() -> str:
                contenders.wait()
                try:
                    with engine.begin() as connection:
                        connection.execute(
                            text(
                                "INSERT INTO conversation_turns "
                                "(id,conversation_id,client_request_id,trace_id,domain_id,route,status,"
                                "stop_reason,user_message,assistant_answer,safe_error_code,safe_error_message,"
                                "composer_ref_fingerprint,plan_step_count,retrieval_operation_count,"
                                "repair_attempt_count,created_at,started_at,completed_at,updated_at) "
                                "VALUES ('22222222-2222-4222-8222-222222222222',:conversation_id,"
                                "'race-request',null,null,'direct_llm','running',null,'Question',null,"
                                "null,null,:fingerprint,0,0,0,:now,:now,null,:now)"
                            ),
                            {
                                "conversation_id": conversation_id,
                                "fingerprint": (
                                    "e3b0c44298fc1c149afbf4c8996fb924"
                                    "27ae41e4649b934ca495991b7852b855"
                                ),
                                "now": now,
                            },
                        )
                except IntegrityError:
                    return "rejected"
                return "inserted"

            with ThreadPoolExecutor(max_workers=2) as executor:
                deleting = executor.submit(delete_parent)
                inserting = executor.submit(insert_turn)
                deleting.result(timeout=15)
                assert inserting.result(timeout=15) == "rejected"

            with engine.connect() as connection:
                assert connection.scalar(
                    text("SELECT count(*) FROM conversations WHERE id = :id"),
                    {"id": conversation_id},
                ) == 0
                assert connection.scalar(
                    text("SELECT count(*) FROM conversation_turns WHERE conversation_id = :id"),
                    {"id": conversation_id},
                ) == 0
            engine.dispose()
    finally:
        admin_engine.dispose()


def test_m08_service_rename_delete_races_and_stale_session_revalidation_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            engine = create_engine(database_url)
            now = utc_now()
            owner_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            auth_session_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
            rename_ref = f"conv_{'1' * 32}"
            delete_ref = f"conv_{'2' * 32}"
            revoked_ref = f"conv_{'3' * 32}"
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id,username,password_hash,role,is_disabled,created_at,updated_at,password_changed_at) "
                        "VALUES (:id,'service-race-owner@example.test','synthetic-password-hash',"
                        "'member',false,:now,:now,:now)"
                    ),
                    {"id": owner_id, "now": now},
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
                        "token_hash": "a" * 64,
                        "expires_at": now + timedelta(days=1),
                        "now": now,
                    },
                )
                for conversation_id, public_ref, title in (
                    ("11111111-1111-4111-8111-111111111111", rename_ref, "Rename race"),
                    ("22222222-2222-4222-8222-222222222222", delete_ref, "Delete race"),
                    ("33333333-3333-4333-8333-333333333333", revoked_ref, "Revoked"),
                ):
                    connection.execute(
                        text(
                            "INSERT INTO conversations "
                            "(id,public_ref,owner_user_id,title,version,created_at,updated_at) "
                            "VALUES (:id,:public_ref,:owner_id,:title,1,:now,:now)"
                        ),
                        {
                            "id": conversation_id,
                            "public_ref": public_ref,
                            "owner_id": owner_id,
                            "title": title,
                            "now": now,
                        },
                    )

            settings = Settings(testing=True)
            rename_barrier = Barrier(2)

            def rename_contender(title: str) -> str:
                with Session(engine) as db:
                    owner = db.get(User, owner_id)
                    auth_session = db.get(AuthSession, auth_session_id)
                    assert owner is not None and auth_session is not None
                    rename_barrier.wait()
                    try:
                        renamed = update_conversation_title(
                            db,
                            settings=settings,
                            owner=owner,
                            auth_session=auth_session,
                            conversation_id=rename_ref,
                            title=title,
                            expected_version=1,
                        )
                    except ConversationError as exc:
                        return exc.code
                    return f"renamed:{renamed.version}"

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(rename_contender, "First"),
                    executor.submit(rename_contender, "Second"),
                ]
                results = {future.result(timeout=15) for future in futures}
            assert results == {"renamed:2", "stale_revision"}

            delete_barrier = Barrier(2)

            def delete_contender() -> str:
                with Session(engine) as db:
                    owner = db.get(User, owner_id)
                    auth_session = db.get(AuthSession, auth_session_id)
                    assert owner is not None and auth_session is not None
                    delete_barrier.wait()
                    try:
                        delete_conversation(
                            db,
                            settings=settings,
                            owner=owner,
                            auth_session=auth_session,
                            conversation_id=delete_ref,
                            expected_version=1,
                        )
                    except ConversationError as exc:
                        return exc.code
                    return "deleted"

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(delete_contender) for _ in range(2)]
                delete_results = {future.result(timeout=15) for future in futures}
            assert delete_results == {"deleted", "not_found"}

            with Session(engine) as stale_db:
                stale_owner = stale_db.get(User, owner_id)
                stale_auth_session = stale_db.get(AuthSession, auth_session_id)
                assert stale_owner is not None and stale_auth_session is not None
                with Session(engine) as revoking_db:
                    revoking_db.execute(
                        update(AuthSession)
                        .where(AuthSession.id == auth_session_id)
                        .values(revoked_at=utc_now())
                    )
                    revoking_db.commit()

                with pytest.raises(ConversationError) as revoked:
                    update_conversation_title(
                        stale_db,
                        settings=settings,
                        owner=stale_owner,
                        auth_session=stale_auth_session,
                        conversation_id=revoked_ref,
                        title="Must not commit",
                        expected_version=1,
                    )
                assert (revoked.value.status_code, revoked.value.code) == (
                    401,
                    "unauthenticated",
                )
                stale_db.rollback()

            with engine.connect() as connection:
                assert connection.scalar(
                    select(Conversation.version).where(Conversation.public_ref == rename_ref)
                ) == 2
                assert connection.scalar(
                    select(Conversation.id).where(Conversation.public_ref == delete_ref)
                ) is None
                assert connection.scalar(
                    select(Conversation.title).where(Conversation.public_ref == revoked_ref)
                ) == "Revoked"
            engine.dispose()
    finally:
        admin_engine.dispose()


def test_m08_concurrent_identical_turn_claims_create_once_and_replay_on_postgresql_16(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            engine = create_engine(database_url)
            now = utc_now()
            owner_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            conversation_id = "11111111-1111-4111-8111-111111111111"
            conversation_ref = f"conv_{'4' * 32}"
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id,username,password_hash,role,is_disabled,created_at,updated_at,password_changed_at) "
                        "VALUES (:id,'claim-race-owner@example.test','synthetic-password-hash',"
                        "'member',false,:now,:now,:now)"
                    ),
                    {"id": owner_id, "now": now},
                )
                connection.execute(
                    text(
                        "INSERT INTO conversations "
                        "(id,public_ref,owner_user_id,title,version,created_at,updated_at) "
                        "VALUES (:id,:public_ref,:owner_id,'Claim race',1,:now,:now)"
                    ),
                    {
                        "id": conversation_id,
                        "public_ref": conversation_ref,
                        "owner_id": owner_id,
                        "now": now,
                    },
                )

            contenders = Barrier(2)
            original_lock = chat_turns_module._lock_conversation_for_turn_insert

            def synchronized_lock(*args, **kwargs):
                contenders.wait()
                return original_lock(*args, **kwargs)

            monkeypatch.setattr(
                chat_turns_module,
                "_lock_conversation_for_turn_insert",
                synchronized_lock,
            )

            def contender() -> tuple[str, bool]:
                with Session(engine) as db:
                    owner = db.get(User, owner_id)
                    assert owner is not None
                    result = claim_turn(
                        db,
                        owner=owner,
                        conversation_id=conversation_ref,
                        client_request_id="identical-claim-request",
                        message="Answer this once.",
                        route=TURN_ROUTE_DIRECT_LLM,
                        domain_id=None,
                    )
                    return result.turn.public_ref, result.replay

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(contender) for _ in range(2)]
                results = [future.result(timeout=15) for future in futures]

            assert {replay for _, replay in results} == {False, True}
            assert len({turn_ref for turn_ref, _ in results}) == 1
            with engine.connect() as connection:
                assert connection.scalar(
                    text(
                        "SELECT count(*) FROM conversation_turns "
                        "WHERE conversation_id = :conversation_id "
                        "AND client_request_id = 'identical-claim-request'"
                    ),
                    {"conversation_id": conversation_id},
                ) == 1
                assert connection.scalar(
                    select(Conversation.version).where(Conversation.id == conversation_id)
                ) == 2
            engine.dispose()
    finally:
        admin_engine.dispose()
