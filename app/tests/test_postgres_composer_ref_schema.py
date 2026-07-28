from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
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
from sqlalchemy.exc import IntegrityError

from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p1101_[a-z0-9_]+$")
HEAD_REVISION = "f1a8c3d04e92"

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
    assert 160000 <= version_num < 170000, f"PostgreSQL 16 required, found {version_num}"


@contextmanager
def _disposable_database(admin_engine: Engine, admin_url: URL, label: str):
    database_name = f"ce_p1101_{label}_{uuid4().hex}"
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


def _seed_user_and_turn(connection, *, now: datetime) -> tuple[str, str]:
    user_id = str(uuid4())
    conversation_id = str(uuid4())
    turn_id = str(uuid4())
    connection.execute(
        text(
            "INSERT INTO users "
            "(id,username,password_hash,role,is_disabled,created_at,updated_at,password_changed_at) "
            "VALUES (:id,:username,:password_hash,'member',false,:now,:now,:now)"
        ),
        {
            "id": user_id,
            "username": f"mina-{user_id[:8]}@example.test",
            "password_hash": "synthetic-password-hash",
            "now": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO conversations "
            "(id,public_ref,owner_user_id,title,version,created_at,updated_at) "
            "VALUES (:id,:public_ref,:owner_user_id,:title,1,:now,:now)"
        ),
        {
            "id": conversation_id,
            "public_ref": f"conv_{uuid4().hex}",
            "owner_user_id": user_id,
            "title": "Composer schema",
            "now": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO conversation_turns "
            "(id,public_ref,conversation_id,client_request_id,trace_id,domain_id,route,status,"
            "stop_reason,user_message,assistant_answer,safe_error_code,safe_error_message,"
            "composer_ref_fingerprint,plan_step_count,retrieval_operation_count,"
            "repair_attempt_count,created_at,started_at,completed_at,updated_at) "
            "VALUES (:id,:public_ref,:conversation_id,:client_request_id,null,null,'direct_llm',"
            "'completed','direct_llm',:user_message,'Answer',null,null,:fingerprint,0,0,0,"
            ":now,:now,:now,:now)"
        ),
        {
            "id": turn_id,
            "public_ref": f"turn_{uuid4().hex}",
            "conversation_id": conversation_id,
            "client_request_id": f"req-{uuid4().hex[:12]}",
            "user_message": "Composer schema proof",
            "fingerprint": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "now": now,
        },
    )
    return user_id, turn_id


def test_p11_01_composer_ref_schema_constraints_on_postgresql_16() -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "composer") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")
            engine = create_engine(database_url)
            now = datetime(2026, 7, 17, 12, 0, 0)
            try:
                with engine.begin() as connection:
                    constraints = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT conname FROM pg_constraint "
                                "WHERE conrelid IN ("
                                " 'prompt_templates'::regclass,"
                                " 'composer_ref_tokens'::regclass,"
                                " 'conversation_turn_composer_refs'::regclass"
                                ")"
                            )
                        )
                    }
                    indexes = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT indexname FROM pg_indexes "
                                "WHERE tablename IN ("
                                " 'prompt_templates',"
                                " 'composer_ref_tokens',"
                                " 'conversation_turn_composer_refs'"
                                ")"
                            )
                        )
                    }
                    token_columns = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_name = 'composer_ref_tokens'"
                            )
                        )
                    }

                    assert {
                        "ck_prompt_templates_state",
                        "ck_prompt_templates_body_size",
                        "ck_composer_ref_tokens_kind",
                        "ck_composer_ref_tokens_hash_size",
                        "ck_conversation_turn_composer_refs_kind",
                        "ck_conversation_turn_composer_refs_redacted_fields",
                        "ck_conversation_turn_composer_refs_order_positive",
                        "ck_conversation_turn_composer_refs_kind_target",
                    } <= constraints
                    assert {
                        "uq_prompt_templates_name",
                        "uq_composer_ref_tokens_hash",
                        "ix_composer_ref_tokens_owner_expires",
                        "uq_conversation_turn_composer_refs_order",
                        "uq_conversation_turn_composer_refs_public_ref",
                    } <= indexes
                    assert "token" not in token_columns
                    assert "raw_token" not in token_columns
                    assert "used_at" not in token_columns
                    assert "consumed_at" in token_columns

                    user_id, turn_id = _seed_user_and_turn(connection, now=now)

                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(
                                text(
                                    "INSERT INTO composer_ref_tokens "
                                    "(id,token_hash,owner_user_id,ref_kind,target_id,"
                                    "expires_at,created_at) "
                                    "VALUES (:id,:token_hash,:owner_user_id,'wiki',"
                                    ":target_id,:expires_at,:created_at)"
                                ),
                                {
                                    "id": str(uuid4()),
                                    "token_hash": "a" * 64,
                                    "owner_user_id": user_id,
                                    "target_id": "target-wiki",
                                    "expires_at": now,
                                    "created_at": now,
                                },
                            )

                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(
                                text(
                                    "INSERT INTO composer_ref_tokens "
                                    "(id,token_hash,owner_user_id,ref_kind,target_id,"
                                    "expires_at,created_at) "
                                    "VALUES (:id,:token_hash,:owner_user_id,'source',"
                                    ":target_id,:expires_at,:created_at)"
                                ),
                                {
                                    "id": str(uuid4()),
                                    "token_hash": "short-hash",
                                    "owner_user_id": user_id,
                                    "target_id": "target-source",
                                    "expires_at": now,
                                    "created_at": now,
                                },
                            )

                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(
                                text(
                                    "INSERT INTO conversation_turn_composer_refs "
                                    "(id,public_ref,turn_id,ref_order,ref_kind,"
                                    "safe_label,safe_description,source_document_id,"
                                    "redacted_at,created_at) "
                                    "VALUES (:id,:public_ref,:turn_id,1,'source',"
                                    "'Label','Desc',:source_document_id,:redacted_at,:created_at)"
                                ),
                                {
                                    "id": str(uuid4()),
                                    "public_ref": f"accepted_{uuid4().hex}",
                                    "turn_id": turn_id,
                                    "source_document_id": str(uuid4()),
                                    "redacted_at": now,
                                    "created_at": now,
                                },
                            )

                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(
                                text(
                                    "INSERT INTO conversation_turn_composer_refs "
                                    "(id,public_ref,turn_id,ref_order,ref_kind,"
                                    "prompt_template_id,created_at) "
                                    "VALUES (:id,:public_ref,:turn_id,1,'wiki',"
                                    ":prompt_template_id,:created_at)"
                                ),
                                {
                                    "id": str(uuid4()),
                                    "public_ref": f"accepted_{uuid4().hex}",
                                    "turn_id": turn_id,
                                    "prompt_template_id": str(uuid4()),
                                    "created_at": now,
                                },
                            )
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
