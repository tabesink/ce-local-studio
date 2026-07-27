"""P8-02 adversarial privacy scans over formatted JSON logs and metric dumps."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    DOMAIN_STATE_STOPPED,
    ROLE_ADMINISTRATOR,
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_COMPLETED,
    TURN_STATUS_RUNNING,
    TURN_STOP_REASON_DIRECT_LLM,
    AuthSession,
    ConversationTurn,
    Domain,
    User,
)
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_user
from context_engine.services.chat_turns import _complete_turn, _fail_turn
from context_engine.services.conversations import create_conversation, update_conversation_title
from context_engine.services.metrics import (
    METRIC_LABEL_KEYS,
    reset_metrics,
    safe_increment,
    snapshot_metrics,
)
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config
from context_engine.services.sources import upload_source_bytes
from context_engine.services.structured_logging import SAFE_LOG_FIELDS, JsonLogFormatter, safe_log

FORBIDDEN_SUBSTRINGS = (
    "SECRET_PROMPT_SENTINEL",
    "SECRET_ANSWER_SENTINEL",
    "SECRET_EXCERPT_SENTINEL",
    "SECRET_CREDENTIAL_SENTINEL",
    "SECRET_TITLE_SENTINEL",
    "SECRET_FILENAME_SENTINEL",
    "SECRET_BODY_SENTINEL",
    "https://runtime.example.invalid/path",
    "s3://bucket/object-key",
    "Traceback (most recent call last)",
    "composer_token_raw_",
    "PRIVATE-STACK-SENTINEL",
)

STRUCTURAL_LOG_KEYS = frozenset({"timestamp", "level", "logger"})


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    reset_metrics()
    yield
    reset_metrics()


def _logger_capture() -> tuple[logging.Logger, StringIO]:
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger(f"context_engine.test.privacy.{uuid4().hex}")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger, output


def _assert_log_blob_private(blob: str) -> None:
    for line in blob.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        assert set(payload).issubset(SAFE_LOG_FIELDS | STRUCTURAL_LOG_KEYS)
    for sentinel in FORBIDDEN_SUBSTRINGS:
        assert sentinel not in blob, f"{sentinel!r} leaked into logs"


def _assert_metrics_private() -> None:
    for sample in snapshot_metrics():
        assert sample.name in {"http_request", "chat_turn_terminal", "worker_operation"}
        assert set(sample.labels).issubset(METRIC_LABEL_KEYS)
        blob = json.dumps({"name": sample.name, "labels": sample.labels, "value": sample.value})
        for sentinel in FORBIDDEN_SUBSTRINGS:
            assert sentinel not in blob, f"{sentinel!r} leaked into metrics"


def _auth_session(db: Session, owner: User) -> AuthSession:
    now = utc_now()
    auth_session = AuthSession(
        user_id=owner.id,
        token_hash=uuid4().hex * 2,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        last_used_at=now,
    )
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    return auth_session


def test_safe_log_drops_planted_forbidden_kwargs() -> None:
    logger, output = _logger_capture()
    safe_log(
        logger,
        "http_request",
        request_id="req-privacy-1",
        actor_kind="member",
        http_method="POST",
        http_route="/api/v1/auth/login",
        http_status=401,
        outcome="failed",
        safe_error_code="invalid_credentials",
        password="SECRET_CREDENTIAL_SENTINEL",
        username="SECRET_TITLE_SENTINEL",
        request_body="SECRET_BODY_SENTINEL",
        exception="Traceback (most recent call last)",
        prompt="SECRET_PROMPT_SENTINEL",
    )
    _assert_log_blob_private(output.getvalue())
    _assert_metrics_private()


def test_http_request_logs_and_metrics_omit_planted_sentinels(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'privacy-http.db'}",
        testing=True,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)

    root = logging.getLogger()
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonLogFormatter())
    previous_handlers = list(root.handlers)
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "SECRET_TITLE_SENTINEL", "password": "SECRET_CREDENTIAL_SENTINEL"},
            )
    finally:
        root.handlers = previous_handlers

    assert response.status_code in {401, 403, 422}
    assert "X-Request-ID" in response.headers
    _assert_log_blob_private(output.getvalue())
    assert any(sample.name == "http_request" for sample in snapshot_metrics())
    _assert_metrics_private()


def test_mutation_fixtures_do_not_leak_sentinels_into_log_metric_sinks(db: Session, tmp_path: Path) -> None:
    logger, output = _logger_capture()
    settings = Settings(
        testing=True,
        source_storage_root=str(tmp_path / "source-storage"),
        domain_runtime_root=str(tmp_path / "domain-runtimes"),
        domain_runtime_controller_kind="local",
    )
    seed_runtime_config(db)
    admin = create_user(db, "admin-privacy@example.test", "Password123!", role=ROLE_ADMINISTRATOR)
    member = create_user(db, "member-privacy@example.test", "Password123!")
    auth_session = _auth_session(db, member)
    admin_audit = AuditContext(actor_user=admin, request_id="req-privacy-admin")
    member_audit = AuditContext(actor_user=member, request_id="req-privacy-member")

    rotate_provider_credential(
        db,
        "openai",
        "SECRET_CREDENTIAL_SENTINEL",
        SecretCrypto.from_settings(settings),
        expected_version=1,
        audit_context=admin_audit,
    )
    conversation = create_conversation(
        db,
        settings=settings,
        owner=member,
        title="SECRET_TITLE_SENTINEL",
        auth_session=auth_session,
        audit_context=member_audit,
    )
    update_conversation_title(
        db,
        settings=settings,
        owner=member,
        conversation_id=conversation.public_ref,
        title="SECRET_TITLE_SENTINEL renamed",
        expected_version=conversation.version,
        auth_session=auth_session,
        audit_context=member_audit,
    )
    domain = Domain(
        id="domain-privacy-logs",
        display_name="Privacy Logs",
        state=DOMAIN_STATE_STOPPED,
        embedding_profile_id="openai-embedding-default",
    )
    db.add(domain)
    db.commit()
    upload_source_bytes(
        db,
        settings=settings,
        domain_id=domain.id,
        filename="SECRET_FILENAME_SENTINEL.pdf",
        content_type="application/pdf",
        data=b"%PDF-1.4 SECRET_BODY_SENTINEL privacy-scan",
        requested_by_user=admin,
        audit_context=admin_audit,
    )

    safe_log(
        logger,
        "http_request",
        request_id="req-after",
        actor_kind="administrator",
        http_method="POST",
        http_route="/api/v1/admin/sources",
        http_status=201,
        outcome="succeeded",
        filename="SECRET_FILENAME_SENTINEL.pdf",
        title="SECRET_TITLE_SENTINEL",
        body="SECRET_BODY_SENTINEL",
        credential="SECRET_CREDENTIAL_SENTINEL",
        path="https://runtime.example.invalid/path",
        object_key="s3://bucket/object-key",
        prompt="SECRET_PROMPT_SENTINEL",
        excerpt="SECRET_EXCERPT_SENTINEL",
    )
    _assert_log_blob_private(output.getvalue())
    _assert_metrics_private()


def test_chat_terminal_logs_join_on_trace_id_and_omit_content(db: Session) -> None:
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonLogFormatter())
    chat_logger = logging.getLogger("context_engine.services.chat_turns")
    previous = list(chat_logger.handlers)
    chat_logger.handlers = [handler]
    chat_logger.propagate = False
    chat_logger.setLevel(logging.INFO)

    settings = Settings(testing=True)
    member = create_user(db, "member-chat-privacy@example.test", "Password123!")
    auth_session = _auth_session(db, member)
    conversation = create_conversation(
        db,
        settings=settings,
        owner=member,
        title="chat",
        auth_session=auth_session,
        audit_context=AuditContext(actor_user=member, request_id="req-create"),
    )
    now = utc_now()
    turn = ConversationTurn(
        conversation_id=conversation.id,
        public_ref=f"turn_{uuid4().hex}",
        route=TURN_ROUTE_DIRECT_LLM,
        status=TURN_STATUS_RUNNING,
        user_message="SECRET_PROMPT_SENTINEL",
        client_request_id=f"client-{uuid4().hex}",
        trace_id=f"trace-{uuid4().hex}",
        execution_generation=1,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)

    try:
        completed = _complete_turn(
            db,
            turn=turn,
            stop_reason=TURN_STOP_REASON_DIRECT_LLM,
            assistant_answer="SECRET_ANSWER_SENTINEL",
            request_id="req-chat-1",
        )
        assert completed.status == TURN_STATUS_COMPLETED

        failed_turn = ConversationTurn(
            conversation_id=conversation.id,
            public_ref=f"turn_{uuid4().hex}",
            route=TURN_ROUTE_DIRECT_LLM,
            status=TURN_STATUS_RUNNING,
            user_message="SECRET_PROMPT_SENTINEL",
            client_request_id=f"client-{uuid4().hex}",
            trace_id=f"trace-{uuid4().hex}",
            execution_generation=1,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(failed_turn)
        db.commit()
        db.refresh(failed_turn)
        _fail_turn(
            db,
            turn=failed_turn,
            code="provider_failure",
            message="safe",
            stop_reason="provider_failure",
            request_id="req-chat-2",
        )
    finally:
        chat_logger.handlers = previous

    blob = output.getvalue()
    _assert_log_blob_private(blob)
    payloads = [json.loads(line) for line in blob.splitlines() if line.strip()]
    persisted = [p for p in payloads if p.get("event") == "chat.turn_persisted"]
    failed = [p for p in payloads if p.get("event") == "chat.turn_failed"]
    assert persisted and persisted[0]["trace_id"] == completed.trace_id
    assert persisted[0]["request_id"] == "req-chat-1"
    assert failed and failed[0]["request_id"] == "req-chat-2"
    assert any(sample.name == "chat_turn_terminal" for sample in snapshot_metrics())
    _assert_metrics_private()


def test_metrics_reject_identity_values_and_unknown_labels() -> None:
    safe_increment(
        "http_request",
        http_method="GET",
        http_route="/api/v1/conversations/conv_deadbeef01/turns",
        outcome="succeeded",
        actor_kind="member",
        status_class="2xx",
    )
    safe_increment(
        "worker_operation",
        operation_type="source_preparation",
        outcome="succeeded",
        domain_id="dom_secret",
    )
    assert snapshot_metrics() == []
