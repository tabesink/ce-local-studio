"""P8-03 combined adversarial privacy scan across audit, logs, metrics, and health."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from context_engine.api.contract_app import CANONICAL_REQUEST_ID_HEADER
from context_engine.api.dependencies import get_db
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    DOMAIN_STATE_STOPPED,
    ROLE_ADMINISTRATOR,
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_COMPLETED,
    TURN_STOP_REASON_DIRECT_LLM,
    AuditEvent,
    AuthSession,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    Domain,
)
from context_engine.services.audit import ALLOWED_AUDIT_METADATA_KEYS, AuditContext
from context_engine.services.auth import create_user
from context_engine.services.chat_turns import redact_turns_for_domain
from context_engine.services.conversations import create_conversation, update_conversation_title
from context_engine.services.metrics import METRIC_LABEL_KEYS, reset_metrics, safe_increment, snapshot_metrics
from context_engine.services import readiness as readiness_module
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
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


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    reset_metrics()
    yield
    reset_metrics()


@pytest.fixture(autouse=True)
def _bypass_catalog_compatibility_for_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite create_all DBs are not Path 1 catalog targets.

    Live PG catalog refusal belongs to test_postgres_migration_preflight / foundation.
    """

    monkeypatch.setattr(readiness_module, "check_catalog_compatibility", lambda _db: None)


def _serialize_audit_row(event: AuditEvent) -> str:
    payload = {
        "event_name": event.event_name,
        "actor_kind": event.actor_kind,
        "actor_user_id": event.actor_user_id,
        "target_kind": event.target_kind,
        "target_id": event.target_id,
        "request_id": event.request_id,
        "trace_id": event.trace_id,
        "outcome": event.outcome,
        "safe_error_code": event.safe_error_code,
        "metadata_json": event.metadata_json,
    }
    return json.dumps(payload, sort_keys=True)


def _assert_no_forbidden(blob: str, *, sink: str) -> None:
    for sentinel in FORBIDDEN_SUBSTRINGS:
        assert sentinel not in blob, f"{sentinel!r} leaked into {sink}"


def _assert_audit_rows_private(events: list[AuditEvent]) -> None:
    for event in events:
        blob = _serialize_audit_row(event)
        _assert_no_forbidden(blob, sink=f"audit event {event.event_name}")
        if event.metadata_json:
            metadata = json.loads(event.metadata_json)
            assert isinstance(metadata, dict)
            assert set(metadata).issubset(ALLOWED_AUDIT_METADATA_KEYS)


def _assert_log_blob_private(blob: str) -> None:
    for line in blob.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        assert set(payload).issubset(SAFE_LOG_FIELDS | STRUCTURAL_LOG_KEYS)
    _assert_no_forbidden(blob, sink="logs")


def _assert_metrics_private() -> None:
    for sample in snapshot_metrics():
        assert sample.name in {"http_request", "chat_turn_terminal", "worker_operation"}
        assert set(sample.labels).issubset(METRIC_LABEL_KEYS)
        blob = json.dumps({"name": sample.name, "labels": sample.labels, "value": sample.value})
        _assert_no_forbidden(blob, sink="metrics")


def _assert_health_projection_private(response) -> None:
    body_text = response.text
    _assert_no_forbidden(body_text, sink="health response body")
    headers_blob = json.dumps(dict(response.headers), sort_keys=True)
    _assert_no_forbidden(headers_blob, sink="health response headers")
    if response.status_code == 200:
        assert response.json() in ({"status": "live"}, {"status": "ready"})
        assert set(response.json()) == {"status"}
    else:
        assert response.status_code == 503
        payload = response.json()
        assert payload["error"]["code"] == "dependency_unavailable"
        assert payload["error"]["fields"] == {}
        assert payload["error"]["requestId"] == response.headers[CANONICAL_REQUEST_ID_HEADER]


def _auth_session(db: Session, owner) -> AuthSession:
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


class UnhealthyDatabase:
    def execute(self, _statement: object) -> None:
        raise RuntimeError("PRIVATE-STACK-SENTINEL database failure")


def test_cross_sink_privacy_scan_after_planted_mutations(tmp_path: Path) -> None:
    database_path = tmp_path / "cross-sink.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        source_storage_root=str(tmp_path / "source-storage"),
        domain_runtime_root=str(tmp_path / "domain-runtimes"),
        domain_runtime_controller_kind="local",
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
        with Session(app.state.engine) as db:
            db.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
            db.execute(text("DELETE FROM alembic_version"))
            db.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                {"version": SUPPORTED_ALEMBIC_HEAD},
            )
            seed_runtime_config(db)
            admin = create_user(db, "admin-cross-sink@example.test", "Password123!", role=ROLE_ADMINISTRATOR)
            member = create_user(db, "member-cross-sink@example.test", "Password123!")
            auth_session = _auth_session(db, member)
            admin_audit = AuditContext(actor_user=admin, request_id="req-cross-admin")
            member_audit = AuditContext(actor_user=member, request_id="req-cross-member")

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
                id="domain-cross-sink",
                display_name="Cross Sink",
                state=DOMAIN_STATE_STOPPED,
                embedding_profile_id="openai-embedding-default",
            )
            db.add(domain)
            db.commit()
            source, _operation = upload_source_bytes(
                db,
                settings=settings,
                domain_id=domain.id,
                filename="SECRET_FILENAME_SENTINEL.pdf",
                content_type="application/pdf",
                data=b"%PDF-1.4 SECRET_BODY_SENTINEL privacy-scan",
                requested_by_user=admin,
                audit_context=admin_audit,
            )
            now = utc_now()
            turn = ConversationTurn(
                conversation_id=conversation.id,
                client_request_id="cross-sink-turn",
                route=TURN_ROUTE_DIRECT_LLM,
                status=TURN_STATUS_COMPLETED,
                stop_reason=TURN_STOP_REASON_DIRECT_LLM,
                user_message="SECRET_PROMPT_SENTINEL",
                assistant_answer="SECRET_ANSWER_SENTINEL",
                started_at=now,
                completed_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(turn)
            db.flush()
            db.add(
                ConversationTurnEvidenceRef(
                    turn_id=turn.id,
                    evidence_order=1,
                    citation_label="E1",
                    source_label="SECRET_FILENAME_SENTINEL.pdf",
                    excerpt="SECRET_EXCERPT_SENTINEL",
                    source_document_id=source.id,
                    source_block_id="block-cross-sink",
                )
            )
            db.commit()
            redact_turns_for_domain(db, domain.id, audit_context=admin_audit)

            safe_log(
                logging.getLogger("context_engine.services.sources"),
                "source_preparation_worker.failed",
                request_id="req-cross-fail",
                domain_id=domain.id,
                source_id="src_cross_sink",
                operation_id="op_cross_sink",
                safe_error_code="parser_failure",
                outcome="failed",
                filename="SECRET_FILENAME_SENTINEL.pdf",
                title="SECRET_TITLE_SENTINEL",
                body="SECRET_BODY_SENTINEL",
                credential="SECRET_CREDENTIAL_SENTINEL",
                path="https://runtime.example.invalid/path",
                object_key="s3://bucket/object-key",
                prompt="SECRET_PROMPT_SENTINEL",
                excerpt="SECRET_EXCERPT_SENTINEL",
                exception="Traceback (most recent call last): PRIVATE-STACK-SENTINEL",
            )
            safe_increment(
                "worker_operation",
                operation_type="source_preparation",
                outcome="failed",
                safe_error_code="parser_failure",
                filename="SECRET_FILENAME_SENTINEL.pdf",
            )
            safe_increment(
                "worker_operation",
                operation_type="source_preparation",
                outcome="failed",
                safe_error_code="parser_failure",
            )

            audit_events = list(db.scalars(select(AuditEvent)))
            assert audit_events
            _assert_audit_rows_private(audit_events)

        with TestClient(app) as client:
            live_ok = client.get("/health/live")
            ready_ok = client.get("/health/ready")
            _assert_health_projection_private(live_ok)
            _assert_health_projection_private(ready_ok)
            assert live_ok.status_code == 200
            assert ready_ok.status_code == 200

        app.dependency_overrides[get_db] = lambda: UnhealthyDatabase()
        try:
            with TestClient(app) as client:
                ready_fail = client.get("/health/ready")
                live_during_fail = client.get("/health/live")
                _assert_health_projection_private(ready_fail)
                _assert_health_projection_private(live_during_fail)
                assert ready_fail.status_code == 503
                assert live_during_fail.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)
    finally:
        root.handlers = previous_handlers

    log_blob = output.getvalue()
    assert log_blob.strip(), "expected real logger capture during mutation window"
    _assert_log_blob_private(log_blob)
    assert any(sample.name == "worker_operation" for sample in snapshot_metrics()), (
        "expected planted worker_operation metric sample before privacy assert"
    )
    _assert_metrics_private()
