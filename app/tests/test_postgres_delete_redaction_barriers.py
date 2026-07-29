"""P7-05 U4: PostgreSQL delete-driven redaction and late-worker fences."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import re
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
    DOMAIN_STATE_DELETING,
    ROLE_ADMINISTRATOR,
    TURN_ROUTE_DIRECT_LLM,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_STATUS_COMPLETED,
    TURN_STATUS_REDACTED,
    TURN_STATUS_RUNNING,
    TURN_STOP_REASON_DIRECT_LLM,
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    SourceDocument,
)
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_user
from context_engine.services.chat_turns import _complete_turn, safe_turn_dto
from context_engine.services.domains import create_domain, enqueue_delete_domain
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config
from context_engine.services.sources import enqueue_delete_source

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p705_[a-z0-9_]+$")
HEAD_REVISION = "e5b8c1d94f20"

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
    database_name = f"ce_p705_redact_{uuid4().hex}"
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


def _settings(database_url: URL) -> Settings:
    return Settings(
        database_url=database_url.render_as_string(hide_password=False),
        testing=True,
        domain_runtime_controller_kind="local",
        domain_runtime_root=str(APP_ROOT / ".data" / f"runtime-{uuid4().hex}"),
    )


def test_postgres_source_and_domain_delete_redact_at_enqueue_and_block_late_complete() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url) as database_url:
            command.upgrade(_alembic_config(database_url), "head")
            settings = _settings(database_url)
            engine = create_engine(settings.database_url)
            assert SUPPORTED_ALEMBIC_HEAD == HEAD_REVISION
            db = Session(engine)
            try:
                seed_runtime_config(db)
                admin = create_user(db, f"admin-{uuid4().hex}@example.test", "Password123!", role=ROLE_ADMINISTRATOR)
                member = create_user(db, f"member-{uuid4().hex}@example.test", "Password123!")
                audit = AuditContext(actor_user=admin, request_id=f"req_{uuid4().hex}", actor_kind="administrator")
                rotate_provider_credential(
                    db,
                    "openai",
                    "sk-test-openai-p705",
                    SecretCrypto.from_settings(settings),
                    expected_version=1,
                    audit_context=audit,
                )
                domain = create_domain(
                    db,
                    settings=settings,
                    domain_id=f"domain-{uuid4().hex[:8]}",
                    display_name="Redact Domain",
                    embedding_profile_id="openai-embedding-default",
                    graph_extraction_profile_id="openai-synthesis-default",
                    requested_by_user=admin,
                    audit_context=audit,
                )
                source = SourceDocument(
                    id=str(uuid4()),
                    public_ref=f"document_{uuid4().hex}",
                    domain_id=domain.id,
                    original_filename="manual.pdf",
                    content_type="application/pdf",
                    original_sha256="e" * 64,
                    original_size_bytes=64,
                    original_object_key=f"source/{uuid4().hex}",
                    state="prepared",
                    parser_kind="docling",
                    created_by_user_id=admin.id,
                )
                db.add(source)
                conversation = Conversation(owner_user_id=member.id, title="Redaction barrier")
                db.add(conversation)
                db.flush()
                now = utc_now()
                completed = ConversationTurn(
                    conversation_id=conversation.id,
                    client_request_id=f"completed-{uuid4().hex}",
                    route=TURN_ROUTE_DIRECT_LLM,
                    status=TURN_STATUS_COMPLETED,
                    user_message="Completed question.",
                    assistant_answer="SENTINEL_COMPLETED_ANSWER",
                    started_at=now,
                    completed_at=now,
                    created_at=now,
                    updated_at=now,
                )
                running = ConversationTurn(
                    conversation_id=conversation.id,
                    client_request_id=f"running-{uuid4().hex}",
                    route=TURN_ROUTE_DOMAIN_RAG,
                    domain_id=domain.id,
                    status=TURN_STATUS_RUNNING,
                    user_message="Running question.",
                    started_at=now,
                    created_at=now,
                    updated_at=now,
                    execution_generation=1,
                )
                db.add_all([completed, running])
                db.flush()
                db.add(
                    ConversationTurnEvidenceRef(
                        turn_id=completed.id,
                        evidence_order=1,
                        citation_label="E1",
                        source_label="manual.pdf",
                        excerpt="SENTINEL_EXCERPT",
                        source_document_id=source.id,
                        source_block_id=str(uuid4()),
                    )
                )
                db.commit()

                enqueue_delete_source(
                    db,
                    domain_id=domain.id,
                    source_id=source.id,
                    expected_version=source.version,
                    requested_by_user=admin,
                    audit_context=audit,
                )
                db.refresh(completed)
                assert completed.status == TURN_STATUS_REDACTED
                assert completed.assistant_answer is None
                dto = safe_turn_dto(db, settings, completed)
                assert dto["assistantAnswer"] is None
                assert dto["evidence"] == []
                assert "SENTINEL" not in str(dto)

                domain2 = create_domain(
                    db,
                    settings=settings,
                    domain_id=f"domain-{uuid4().hex[:8]}",
                    display_name="Domain Two",
                    embedding_profile_id="openai-embedding-default",
                    graph_extraction_profile_id="openai-synthesis-default",
                    requested_by_user=admin,
                    audit_context=audit,
                )
                running.domain_id = domain2.id
                db.commit()
                enqueue_delete_domain(
                    db,
                    domain_id=domain2.id,
                    requested_by_user=admin,
                    expected_version=domain2.version,
                    audit_context=audit,
                )
                db.refresh(running)
                db.refresh(domain2)
                assert domain2.state == DOMAIN_STATE_DELETING
                assert running.status == TURN_STATUS_REDACTED
                late = _complete_turn(
                    db,
                    turn=running,
                    stop_reason=TURN_STOP_REASON_DIRECT_LLM,
                    assistant_answer="LATE_UNREDACT",
                    execution_generation=1,
                )
                assert late.status == TURN_STATUS_REDACTED
                assert late.assistant_answer is None
            finally:
                db.close()
                engine.dispose()
    finally:
        admin_engine.dispose()
