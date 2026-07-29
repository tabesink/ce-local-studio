from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base
from context_engine.models import ROLE_ADMINISTRATOR
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
    database_path = Path(f".data/ce-admin-pagination-{uuid4().hex}.db").resolve()
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
        admin = create_user(db, "admin-pagination@example.test", "Password123!", role=ROLE_ADMINISTRATOR)
        admin_token, _ = create_auth_session(db, admin, settings)
        audit = AuditContext(actor_user=admin, request_id="req-pagination-setup")
        rotate_provider_credential(
            db,
            "openai",
            "sk-test-openai-pagination",
            SecretCrypto.from_settings(settings),
            expected_version=1,
            audit_context=audit,
        )
        for member_index in range(2):
            create_user(db, f"member-pagination-{member_index}@example.test", "Password123!")
        for domain_index in range(2):
            create_domain(
                db,
                settings=settings,
                domain_id=f"domain-pagination-{domain_index}",
                display_name=f"Pagination Domain {domain_index}",
                embedding_profile_id="openai-embedding-default",
                graph_extraction_profile_id="openai-synthesis-default",
                requested_by_user=admin,
                audit_context=audit,
            )
    finally:
        db.close()
    return app, settings, admin_token


@pytest.fixture
def admin_pagination_context(tmp_path):
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


def test_admin_users_pagination_happy_path_two_pages(admin_pagination_context) -> None:
    app, settings, admin_token = admin_pagination_context
    headers, cookies = _security(settings, admin_token, "users-pagination-bucket")

    with TestClient(app) as client:
        first_page = client.get(
            f"{CANONICAL_API_PREFIX}/admin/users",
            params={"limit": 1},
            headers=headers,
            cookies=cookies,
        )
        assert first_page.status_code == 200
        first_body = first_page.json()
        assert len(first_body["users"]) == 1
        assert first_body["nextCursor"] is not None

        second_page = client.get(
            f"{CANONICAL_API_PREFIX}/admin/users",
            params={"limit": 1, "cursor": first_body["nextCursor"]},
            headers=headers,
            cookies=cookies,
        )
        assert second_page.status_code == 200
        second_body = second_page.json()
        assert len(second_body["users"]) == 1

    first_user_id = first_body["users"][0]["id"]
    second_user_id = second_body["users"][0]["id"]
    assert first_user_id != second_user_id

    # Walk the full cursor chain and confirm every admin/member row is returned exactly once.
    all_ids: list[str] = [first_user_id, second_user_id]
    cursor = second_body["nextCursor"]
    with TestClient(app) as client:
        while cursor is not None:
            page = client.get(
                f"{CANONICAL_API_PREFIX}/admin/users",
                params={"limit": 1, "cursor": cursor},
                headers=headers,
                cookies=cookies,
            )
            assert page.status_code == 200
            body = page.json()
            assert len(body["users"]) == 1
            all_ids.append(body["users"][0]["id"])
            cursor = body["nextCursor"]

    assert len(all_ids) == len(set(all_ids))
    assert len(all_ids) == 3  # 1 admin + 2 seeded members


def test_admin_users_pagination_malformed_cursor_returns_cursor_expired(admin_pagination_context) -> None:
    app, settings, admin_token = admin_pagination_context
    headers, cookies = _security(settings, admin_token, "users-pagination-malformed-bucket")

    with TestClient(app) as client:
        response = client.get(
            f"{CANONICAL_API_PREFIX}/admin/users",
            params={"cursor": "not-a-valid-cursor"},
            headers=headers,
            cookies=cookies,
        )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "cursor_expired"


def test_admin_users_pagination_limit_clamp_rejected(admin_pagination_context) -> None:
    app, settings, admin_token = admin_pagination_context
    headers, cookies = _security(settings, admin_token, "users-pagination-limit-bucket")

    with TestClient(app) as client:
        too_large = client.get(
            f"{CANONICAL_API_PREFIX}/admin/users",
            params={"limit": 101},
            headers=headers,
            cookies=cookies,
        )
        too_small = client.get(
            f"{CANONICAL_API_PREFIX}/admin/users",
            params={"limit": 0},
            headers=headers,
            cookies=cookies,
        )

    assert too_large.status_code == 422
    assert too_small.status_code == 422


def test_admin_domains_pagination_happy_path_two_pages(admin_pagination_context) -> None:
    app, settings, admin_token = admin_pagination_context
    headers, cookies = _security(settings, admin_token, "domains-pagination-bucket")

    with TestClient(app) as client:
        first_page = client.get(
            f"{CANONICAL_API_PREFIX}/admin/domains",
            params={"limit": 1},
            headers=headers,
            cookies=cookies,
        )
        assert first_page.status_code == 200
        first_body = first_page.json()
        assert len(first_body["domains"]) == 1
        assert first_body["nextCursor"] is not None

        second_page = client.get(
            f"{CANONICAL_API_PREFIX}/admin/domains",
            params={"limit": 1, "cursor": first_body["nextCursor"]},
            headers=headers,
            cookies=cookies,
        )
        assert second_page.status_code == 200
        second_body = second_page.json()
        assert len(second_body["domains"]) == 1
        assert second_body["nextCursor"] is None

    first_domain_id = first_body["domains"][0]["id"]
    second_domain_id = second_body["domains"][0]["id"]
    assert first_domain_id != second_domain_id
    assert {first_domain_id, second_domain_id} == {"domain-pagination-0", "domain-pagination-1"}


def test_admin_domain_operations_pagination_malformed_cursor_returns_cursor_expired(
    admin_pagination_context,
) -> None:
    app, settings, admin_token = admin_pagination_context
    headers, cookies = _security(settings, admin_token, "domain-operations-malformed-bucket")

    with TestClient(app) as client:
        response = client.get(
            f"{CANONICAL_API_PREFIX}/admin/domains/domain-pagination-0/operations",
            params={"cursor": "definitely-not-base64-json"},
            headers=headers,
            cookies=cookies,
        )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "cursor_expired"
