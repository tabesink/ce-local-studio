from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    DOMAIN_OPERATION_STATUS_SUCCEEDED,
    ROLE_ADMINISTRATOR,
    SOURCE_STATE_PENDING,
    DomainOperation,
    SourceDocument,
    SourcePreparationOperation,
)
from context_engine.security import hash_session_token
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.csrf import TEST_CSRF_SIGNING_KEY, issue_csrf_token
from context_engine.services.domains import create_domain
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config


def _context(tmp_path: Path):
    database_path = Path(f".data/ce-operation-idempotency-{uuid4().hex}.db").resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key=TEST_CSRF_SIGNING_KEY,
        session_cookie_secure=False,
        domain_runtime_controller_kind="local",
        domain_runtime_root=str(tmp_path / "runtimes"),
        source_storage_root=str(tmp_path / "storage"),
    )
    app = create_app(settings)
    app.state.test_database_path = database_path
    Base.metadata.create_all(app.state.engine)
    db = app.state.session_factory()
    try:
        seed_runtime_config(db)
        admin = create_user(db, "admin-idem@example.test", "Password123!", role=ROLE_ADMINISTRATOR)
        admin_token, _ = create_auth_session(db, admin, settings)
        audit = AuditContext(actor_user=admin, request_id="req-idempotency-setup")
        rotate_provider_credential(
            db,
            "openai",
            "sk-test-openai-idem",
            SecretCrypto.from_settings(settings),
            expected_version=1,
            audit_context=audit,
        )
        domain = create_domain(
            db,
            settings=settings,
            domain_id="domain-idem",
            display_name="Idempotency Domain",
            embedding_profile_id="openai-embedding-default",
            graph_extraction_profile_id="openai-synthesis-default",
            requested_by_user=admin,
            audit_context=audit,
        )
        source = SourceDocument(
            id=str(uuid4()),
            public_ref=f"doc_{uuid4().hex}",
            domain_id=domain.id,
            original_filename="manual.pdf",
            content_type="application/pdf",
            original_sha256=uuid4().hex + uuid4().hex[:32],
            original_size_bytes=1024,
            original_object_key=f"obj/{uuid4().hex}",
            state=SOURCE_STATE_PENDING,
            parser_kind="docling",
            preparation_generation=1,
            version=1,
            created_by_user_id=admin.id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(source)
        db.commit()
        source_id = source.id
    finally:
        db.close()
    return app, settings, admin_token, domain.id, source_id


@pytest.fixture
def idempotency_context(tmp_path):
    context = _context(tmp_path)
    try:
        yield context
    finally:
        app = context[0]
        app.state.engine.dispose()
        app.state.test_database_path.unlink(missing_ok=True)


def _security(settings: Settings, token: str, bucket: str) -> tuple[dict[str, str], dict[str, str]]:
    csrf = issue_csrf_token(settings, binding=hash_session_token(token))
    headers = {
        "Origin": "http://ce.example.test",
        PUBLIC_HOST_HEADER: "ce.example.test",
        PUBLIC_PROTO_HEADER: "http",
        CLIENT_BUCKET_HEADER: bucket,
        CSRF_HEADER: csrf,
    }
    cookies = {
        settings.session_cookie_name: token,
        settings.csrf_cookie_name: csrf,
    }
    return headers, cookies


def test_domain_start_idempotency_key_replay_is_durable(idempotency_context) -> None:
    app, settings, admin_token, domain_id, _source_id = idempotency_context
    headers, cookies = _security(settings, admin_token, "domain-start-replay-bucket")
    headers = {**headers, "Idempotency-Key": "domain-start-key-1"}

    with TestClient(app) as client:
        first = client.post(
            f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/start",
            headers=headers,
            cookies=cookies,
        )
        second = client.post(
            f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/start",
            headers=headers,
            cookies=cookies,
        )

    assert first.status_code == second.status_code == 202
    first_operation = first.json()["operation"]
    second_operation = second.json()["operation"]
    assert first_operation == second_operation
    assert first_operation["operationType"] == "start"
    assert first_operation["status"] == DOMAIN_OPERATION_STATUS_SUCCEEDED

    db = app.state.session_factory()
    try:
        start_ops = list(
            db.scalars(
                select(DomainOperation).where(
                    DomainOperation.domain_id == domain_id,
                    DomainOperation.operation_type == "start",
                )
            )
        )
    finally:
        db.close()
    assert len(start_ops) == 1


def test_domain_start_idempotency_key_fingerprint_conflict(idempotency_context) -> None:
    app, settings, admin_token, domain_id, _source_id = idempotency_context
    headers, cookies = _security(settings, admin_token, "domain-start-conflict-bucket")
    headers = {**headers, "Idempotency-Key": "domain-start-key-2"}

    with TestClient(app) as client:
        started = client.post(
            f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/start",
            headers=headers,
            cookies=cookies,
        )
        conflict = client.post(
            f"{CANONICAL_API_PREFIX}/admin/domains/other-domain-idem/start",
            headers=headers,
            cookies=cookies,
        )

    assert started.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


def test_source_retry_idempotency_key_replay_is_durable(idempotency_context) -> None:
    app, settings, admin_token, domain_id, source_id = idempotency_context
    headers, cookies = _security(settings, admin_token, "source-retry-replay-bucket")
    headers = {**headers, "Idempotency-Key": "source-retry-key-1"}

    with TestClient(app) as client:
        first = client.post(
            f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/sources/{source_id}/retry",
            headers=headers,
            cookies=cookies,
        )
        second = client.post(
            f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/sources/{source_id}/retry",
            headers=headers,
            cookies=cookies,
        )

    assert first.status_code == second.status_code == 202
    assert first.json()["operation"] == second.json()["operation"]

    db = app.state.session_factory()
    try:
        operations = list(
            db.scalars(
                select(SourcePreparationOperation).where(
                    SourcePreparationOperation.source_document_id == source_id
                )
            )
        )
    finally:
        db.close()
    assert len(operations) == 1


def test_admin_delete_domain_idempotency_key_replay_is_durable(idempotency_context) -> None:
    app, settings, admin_token, domain_id, _source_id = idempotency_context
    headers, cookies = _security(settings, admin_token, "domain-delete-replay-bucket")
    headers = {**headers, "Idempotency-Key": "domain-delete-key-1", "If-Match": '"1"'}

    with TestClient(app) as client:
        first = client.delete(
            f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}",
            headers=headers,
            cookies=cookies,
        )
        second = client.delete(
            f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}",
            headers=headers,
            cookies=cookies,
        )

    assert first.status_code == second.status_code == 202
    assert first.json()["operation"] == second.json()["operation"]

    db = app.state.session_factory()
    try:
        delete_ops = list(
            db.scalars(
                select(DomainOperation).where(
                    DomainOperation.domain_id == domain_id,
                    DomainOperation.operation_type == "delete",
                )
            )
        )
    finally:
        db.close()
    assert len(delete_ops) == 1
