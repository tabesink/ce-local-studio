from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
import os
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url

from context_engine.api.contract_app import CANONICAL_API_PREFIX, CANONICAL_REQUEST_ID_HEADER
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory, utc_now
from context_engine.models import AuthSession, LoginThrottleBucket
from context_engine.security import hash_session_token
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.csrf import (
    CSRF_PREAUTH_BINDING,
    TEST_CSRF_SIGNING_KEY,
    issue_csrf_token,
)
from context_engine.services.login_throttle import throttle_key
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)


APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
HEAD_REVISION = "b5c8e2d19f47"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p105_[a-z_]+_[0-9a-f]{32}$")
PUBLIC_ORIGIN = "http://ce.example.test"
CLIENT_BUCKET = "ingress-bucket-a"

pytestmark = pytest.mark.postgresql


def _required_admin_url() -> URL:
    if os.getenv(OPT_IN_ENV) != "1":
        pytest.skip(f"set {OPT_IN_ENV}=1 to allow disposable PostgreSQL database tests")

    raw_url = os.getenv(ADMIN_URL_ENV)
    if not raw_url:
        pytest.fail(f"{ADMIN_URL_ENV} is required when disposable database tests are enabled")

    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.fail(f"{ADMIN_URL_ENV} must use PostgreSQL, not {url.get_backend_name()}")
    if not url.database:
        pytest.fail(f"{ADMIN_URL_ENV} must name an administrative database")
    return url


def _assert_postgresql_16(admin_engine: Engine) -> None:
    with admin_engine.connect() as connection:
        version_num = int(connection.scalar(text("SHOW server_version_num")))
    assert 160000 <= version_num < 170000, f"PostgreSQL 16 required, found {version_num}"


@contextmanager
def _disposable_database(admin_engine: Engine, admin_url: URL, label: str):
    database_name = f"ce_p105_{label}_{uuid4().hex}"
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
    rendered_url = database_url.render_as_string(hide_password=False).replace("%", "%%")
    config.set_main_option("sqlalchemy.url", rendered_url)
    return config


def _ingress_settings(database_url: URL, **overrides: object) -> Settings:
    values = {
        "database_url": database_url.render_as_string(hide_password=False),
        "testing": True,
        "session_cookie_secure": False,
        "session_cookie_samesite": "lax",
        "public_origin": PUBLIC_ORIGIN,
        "internal_hosts": "testserver",
        "trusted_bff_peers": "testclient,10.0.0.0/8",
        "csrf_signing_key": TEST_CSRF_SIGNING_KEY,
        "login_throttle_window_seconds": 300,
        "login_throttle_max_failures": 3,
        "login_throttle_block_seconds": 120,
        "session_idle_ttl_seconds": 120,
        "session_touch_interval_seconds": 30,
        "session_ttl_seconds": 3600,
    }
    values.update(overrides)
    return Settings(**values)


def _trusted_headers(*, origin: str | None = PUBLIC_ORIGIN, bucket: str = CLIENT_BUCKET) -> dict[str, str]:
    headers = {
        PUBLIC_HOST_HEADER: "ce.example.test",
        PUBLIC_PROTO_HEADER: "http",
        CLIENT_BUCKET_HEADER: bucket,
    }
    if origin is not None:
        headers["Origin"] = origin
    return headers


def _stable_error(response) -> tuple[int, str, str, dict[str, str]]:
    body = response.json()["error"]
    assert body["requestId"] == response.headers[CANONICAL_REQUEST_ID_HEADER]
    return response.status_code, body["code"], body["message"], body["fields"]


def test_p1_05_csrf_origin_peer_rotation_logout_and_throttle_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "ingress") as database_url:
            config = _alembic_config(database_url)
            script = ScriptDirectory.from_config(config)
            assert script.get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            settings = _ingress_settings(database_url)
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with session_factory() as session:
                    member = create_user(session, "ingress-member@example.test", "member-password")
                    member_id = member.id

                app = create_app(settings)
                with TestClient(app, client=("203.0.113.9", 50000)) as hostile:
                    untrusted = hostile.get(
                        f"{CANONICAL_API_PREFIX}/auth/csrf",
                        headers=_trusted_headers(origin=None),
                    )
                    assert _stable_error(untrusted) == (403, "forbidden", "Forbidden.", {})

                with TestClient(app) as client:
                    csrf = client.get(
                        f"{CANONICAL_API_PREFIX}/auth/csrf",
                        headers=_trusted_headers(origin=None),
                    )
                    assert csrf.status_code == 200
                    assert csrf.headers["cache-control"] == "private, no-store, no-transform"
                    preauth = csrf.json()["csrfToken"]
                    assert client.cookies.get(settings.csrf_cookie_name) == preauth
                    assert "httponly" not in csrf.headers.get("set-cookie", "").lower()

                    wrong_origin = client.post(
                        f"{CANONICAL_API_PREFIX}/auth/login",
                        headers={
                            **_trusted_headers(origin="http://evil.example.test"),
                            CSRF_HEADER: preauth,
                        },
                        json={
                            "username": "ingress-member@example.test",
                            "password": "member-password",
                        },
                    )
                    assert _stable_error(wrong_origin) == (
                        403,
                        "csrf_invalid",
                        "CSRF validation failed.",
                        {},
                    )

                    with session_factory() as session:
                        from context_engine.models import User as UserModel

                        member_row = session.get(UserModel, member_id)
                        assert member_row is not None
                        presented_token, presented_session = create_auth_session(
                            session, member_row, settings
                        )
                        presented_session_id = presented_session.id

                    client.cookies.set(settings.session_cookie_name, presented_token, path="/")
                    login = client.post(
                        f"{CANONICAL_API_PREFIX}/auth/login",
                        headers={**_trusted_headers(), CSRF_HEADER: preauth},
                        json={
                            "username": "ingress-member@example.test",
                            "password": "member-password",
                        },
                    )
                    assert login.status_code == 200
                    assert login.json()["user"]["id"] == member_id
                    session_token = login.cookies.get(settings.session_cookie_name)
                    session_csrf = login.cookies.get(settings.csrf_cookie_name)
                    assert session_token and session_token != presented_token
                    assert session_csrf and session_csrf != preauth
                    client.cookies.set(settings.session_cookie_name, session_token, path="/")
                    client.cookies.set(settings.csrf_cookie_name, session_csrf, path="/")
                    with session_factory() as session:
                        old = session.get(AuthSession, presented_session_id)
                        assert old is not None and old.revoked_at is not None

                    me = client.get(
                        f"{CANONICAL_API_PREFIX}/auth/me",
                        headers=_trusted_headers(origin=None),
                    )
                    assert me.status_code == 200

                    stale_preauth_logout = client.post(
                        f"{CANONICAL_API_PREFIX}/auth/logout",
                        headers={**_trusted_headers(), CSRF_HEADER: preauth},
                    )
                    assert _stable_error(stale_preauth_logout) == (
                        403,
                        "csrf_invalid",
                        "CSRF validation failed.",
                        {},
                    )

                    logout = client.post(
                        f"{CANONICAL_API_PREFIX}/auth/logout",
                        headers={**_trusted_headers(), CSRF_HEADER: session_csrf},
                    )
                    assert logout.status_code == 204
                    assert logout.content == b""
                    assert logout.headers["cache-control"] == "private, no-store, no-transform"

                with session_factory() as session:
                    revoked = session.scalar(
                        select(AuthSession).where(
                            AuthSession.token_hash == hash_session_token(session_token)
                        )
                    )
                    assert revoked is not None and revoked.revoked_at is not None

                with TestClient(app) as throttle_client:
                    csrf = throttle_client.get(
                        f"{CANONICAL_API_PREFIX}/auth/csrf",
                        headers=_trusted_headers(origin=None),
                    )
                    token = csrf.json()["csrfToken"]
                    throttle_client.cookies.set(settings.csrf_cookie_name, token, path="/")
                    for _ in range(3):
                        denied = throttle_client.post(
                            f"{CANONICAL_API_PREFIX}/auth/login",
                            headers={**_trusted_headers(), CSRF_HEADER: token},
                            json={
                                "username": "ingress-member@example.test",
                                "password": "wrong-password",
                            },
                        )
                        assert _stable_error(denied) == (
                            401,
                            "invalid_credentials",
                            "Invalid username or password.",
                            {},
                        )
                        token = issue_csrf_token(settings, binding=CSRF_PREAUTH_BINDING)
                        throttle_client.cookies.set(settings.csrf_cookie_name, token, path="/")

                    blocked = throttle_client.post(
                        f"{CANONICAL_API_PREFIX}/auth/login",
                        headers={**_trusted_headers(), CSRF_HEADER: token},
                        json={
                            "username": "ingress-member@example.test",
                            "password": "member-password",
                        },
                    )
                    assert _stable_error(blocked) == (
                        429,
                        "rate_limited",
                        "Login temporarily unavailable.",
                        {},
                    )
                    assert blocked.headers["retry-after"].isdigit()
                    assert int(blocked.headers["retry-after"]) >= 1

                with session_factory() as session:
                    client_hash, username_hash = throttle_key(
                        CLIENT_BUCKET,
                        "ingress-member@example.test",
                    )
                    row = session.scalar(
                        select(LoginThrottleBucket).where(
                            LoginThrottleBucket.client_bucket_hash == client_hash,
                            LoginThrottleBucket.username_hash == username_hash,
                        )
                    )
                    assert row is not None
                    assert row.failure_count == 3
                    assert row.blocked_until is not None
                    assert row.client_bucket_hash not in CLIENT_BUCKET
                    assert "ingress-member" not in row.username_hash
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p1_05_idle_expiry_and_bounded_touch_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "idle") as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            settings = _ingress_settings(
                database_url,
                session_idle_ttl_seconds=60,
                session_touch_interval_seconds=20,
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with session_factory() as session:
                    member = create_user(session, "idle-member@example.test", "member-password")
                    token, auth_session = create_auth_session(session, member, settings)
                    auth_session_id = auth_session.id
                    auth_session.last_used_at = utc_now() - timedelta(seconds=30)
                    session.commit()

                app = create_app(settings)
                with TestClient(app) as client:
                    client.cookies.set(settings.session_cookie_name, token, path="/")
                    touched = client.get(
                        f"{CANONICAL_API_PREFIX}/auth/me",
                        headers=_trusted_headers(origin=None),
                    )
                    assert touched.status_code == 200

                with session_factory() as session:
                    current = session.get(AuthSession, auth_session_id)
                    assert current is not None
                    assert current.last_used_at is not None
                    assert current.last_used_at > utc_now() - timedelta(seconds=5)
                    current.last_used_at = utc_now() - timedelta(seconds=61)
                    session.commit()

                with TestClient(app) as client:
                    client.cookies.set(settings.session_cookie_name, token, path="/")
                    expired = client.get(
                        f"{CANONICAL_API_PREFIX}/auth/me",
                        headers=_trusted_headers(origin=None),
                    )
                    assert _stable_error(expired) == (
                        401,
                        "unauthenticated",
                        "Authentication required.",
                        {},
                    )
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
