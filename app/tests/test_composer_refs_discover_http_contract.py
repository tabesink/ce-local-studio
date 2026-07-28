"""P11-02 / M-09 — discover HTTP contract for ComposerRefDto and closed errors."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.api.routes import _composer_ref_api_error
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base
from context_engine.dev.seed_composer_refs import seed_composer_ref_fixtures
from context_engine.models import ComposerRefToken, PROMPT_TEMPLATE_STATE_APPROVED, PromptTemplate
from context_engine.security import hash_session_token
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.composer_refs import ComposerRefError, MAX_COMPOSER_REFS, MAX_DISCOVERY_LIMIT
from context_engine.services.csrf import TEST_CSRF_SIGNING_KEY, issue_csrf_token
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)


def _context():
    database_path = Path(f".data/ce-composer-discover-http-{uuid4().hex}.db").resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key=TEST_CSRF_SIGNING_KEY,
        session_cookie_secure=False,
    )
    app = create_app(settings)
    app.state.test_database_path = database_path
    Base.metadata.create_all(app.state.engine)
    db = app.state.session_factory()
    try:
        owner = create_user(db, "mina-discover@example.test", "Password123!")
        owner_token, _ = create_auth_session(db, owner, settings)
        seed_composer_ref_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
        )
        # Ensure at least one approved template is discoverable for this owner world.
        if db.get(PromptTemplate, "c0ffee01-0001-4001-8001-000000000001") is None:
            db.add(
                PromptTemplate(
                    id="c0ffee01-0001-4001-8001-000000000001",
                    name="Safety summary",
                    description="Approved template",
                    body="Summarize the safety controls.",
                    state=PROMPT_TEMPLATE_STATE_APPROVED,
                )
            )
            db.commit()
    finally:
        db.close()
    return app, settings, owner_token


@pytest.fixture
def discover_http_context():
    context = _context()
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


def test_discover_returns_catalog_token_and_expires_at_hash_only(discover_http_context) -> None:
    app, settings, owner_token = discover_http_context
    headers, cookies = _security(settings, owner_token, "discover-bucket")

    with TestClient(app) as client:
        response = client.post(
            f"{CANONICAL_API_PREFIX}/composer-refs:discover",
            json={"kinds": ["template"], "limit": 5},
            headers=headers,
            cookies=cookies,
        )
    assert response.status_code == 200
    body = response.json()
    assert "refs" in body
    assert body["refs"], "expected at least one template ref"
    ref = body["refs"][0]
    assert set(ref) == {"token", "kind", "label", "description", "expiresAt"}
    assert "refToken" not in ref
    assert ref["kind"] == "template"
    assert isinstance(ref["token"], str) and len(ref["token"]) >= 16
    assert ref["expiresAt"].endswith("Z")

    db = app.state.session_factory()
    try:
        hashes = {row.token_hash for row in db.scalars(select(ComposerRefToken))}
        assert all(len(item) == 64 for item in hashes)
        assert ref["token"] not in hashes
    finally:
        db.close()


def test_discover_limit_26_is_validation_error(discover_http_context) -> None:
    app, settings, owner_token = discover_http_context
    headers, cookies = _security(settings, owner_token, "discover-limit")

    with TestClient(app) as client:
        response = client.post(
            f"{CANONICAL_API_PREFIX}/composer-refs:discover",
            json={"limit": 26},
            headers=headers,
            cookies=cookies,
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert MAX_COMPOSER_REFS == 25
    assert MAX_DISCOVERY_LIMIT == 25


def test_composer_ref_api_error_allowlist_fail_closed() -> None:
    unavailable = _composer_ref_api_error(
        ComposerRefError(409, "composer_ref_unavailable", "Composer reference is unavailable.")
    )
    assert unavailable.status_code == 409
    assert unavailable.code == "operation_conflict"

    leaked = _composer_ref_api_error(ComposerRefError(418, "private_debug_code", "nope"))
    assert leaked.status_code == 503
    assert leaked.code == "dependency_unavailable"
