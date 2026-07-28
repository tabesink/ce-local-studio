from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import os
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine, URL, make_url

from context_engine.api.contract_app import CANONICAL_API_PREFIX, CANONICAL_REQUEST_ID_HEADER
from context_engine.api.dependencies import require_admin
from context_engine.api.routes import api_router
from context_engine.app import create_app
from context_engine.bootstrap_admin import bootstrap_initial_admin
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.models import (
    AUDIT_EVENT_SECURITY_ADMIN_ROUTE_DENIED,
    AuditEvent,
    AuthSession,
    ROLE_ADMINISTRATOR,
    ROLE_MEMBER,
    User,
)
from context_engine.security import hash_password, hash_session_token, verify_password
from context_engine.services.auth import (
    authenticate_user,
    create_auth_session,
    create_user,
    revoke_session_token,
    safe_user,
    seed_admin,
)
from context_engine.services.conversations import create_conversation


APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
BASELINE_REVISION = "724564649a13"
HEAD_REVISION = "d4e7a1b92c80"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p101_[a-z_]+_[0-9a-f]{32}$")

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
    database_name = f"ce_p101_{label}_{uuid4().hex}"
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


def _current_revision(engine: Engine) -> str:
    with engine.connect() as connection:
        return str(connection.scalar(text("SELECT version_num FROM alembic_version")))


def _assert_single_head(config: Config) -> None:
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [HEAD_REVISION]


def test_p1_01_fresh_install_and_canonical_session_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "fresh") as database_url:
            probe_engine = create_engine(database_url)
            try:
                assert inspect(probe_engine).get_table_names() == []

                create_app(
                    Settings(
                        database_url=database_url.render_as_string(hide_password=False),
                        testing=True,
                    )
                )
                assert inspect(probe_engine).get_table_names() == []
            finally:
                probe_engine.dispose()

            config = _alembic_config(database_url)
            _assert_single_head(config)
            command.upgrade(config, "head")

            engine = create_db_engine(
                Settings(database_url=database_url.render_as_string(hide_password=False))
            )
            try:
                assert _current_revision(engine) == HEAD_REVISION
                assert "users" in inspect(engine).get_table_names()

                session_factory = create_session_factory(engine)
                with session_factory() as session:
                    assert session.scalar(text("SELECT 1")) == 1
                    session.commit()

                command.check(config)
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p1_01_baseline_upgrade_retains_data_and_recent_revisions_roll_back() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "upgrade") as database_url:
            config = _alembic_config(database_url)
            _assert_single_head(config)
            command.upgrade(config, BASELINE_REVISION)

            engine = create_engine(database_url)
            try:
                now = datetime.now(UTC).replace(tzinfo=None)
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO users "
                            "(id, username, password_hash, role, is_disabled, created_at, "
                            "updated_at, password_changed_at) VALUES "
                            "(:id, :username, :password_hash, :role, :is_disabled, :created_at, "
                            ":updated_at, :password_changed_at)"
                        ),
                        {
                            "id": "00000000-0000-0000-0000-000000000101",
                            "username": "p1-01-retained@example.test",
                            "password_hash": "synthetic-not-a-password-hash",
                            "role": "member",
                            "is_disabled": False,
                            "created_at": now,
                            "updated_at": now,
                            "password_changed_at": now,
                        },
                    )
            finally:
                engine.dispose()

            command.upgrade(config, "head")
            engine = create_engine(database_url)
            try:
                assert _current_revision(engine) == HEAD_REVISION
                with engine.connect() as connection:
                    assert connection.scalar(
                        text("SELECT username FROM users WHERE id = :id"),
                        {"id": "00000000-0000-0000-0000-000000000101"},
                    ) == "p1-01-retained@example.test"
                assert "conversation_turn_events" in inspect(engine).get_table_names()
            finally:
                engine.dispose()

            command.downgrade(config, BASELINE_REVISION)
            engine = create_engine(database_url)
            try:
                assert _current_revision(engine) == BASELINE_REVISION
                assert "conversation_turn_events" not in inspect(engine).get_table_names()
                with engine.connect() as connection:
                    assert connection.scalar(
                        text("SELECT count(*) FROM users WHERE id = :id"),
                        {"id": "00000000-0000-0000-0000-000000000101"},
                    ) == 1
            finally:
                engine.dispose()

            command.upgrade(config, "head")
            engine = create_engine(database_url)
            try:
                assert _current_revision(engine) == HEAD_REVISION
                command.check(config)
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p1_02_auth_bootstrap_and_session_replacement_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "auth") as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            database_url_text = database_url.render_as_string(hide_password=False)
            settings = Settings(
                database_url=database_url_text,
                testing=True,
                admin_username="bootstrap-admin@example.test",
                admin_password="initial-bootstrap-password",
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with session_factory() as session:
                    seeded = seed_admin(session, settings)
                    assert seeded is not None
                    seeded_id = seeded.id
                    seeded_hash = seeded.password_hash
                    assert seeded.password_hash != settings.admin_password
                    assert verify_password(seeded.password_hash, settings.admin_password)

                    seeded.role = ROLE_MEMBER
                    seeded.is_disabled = True
                    session.commit()

                changed_bootstrap = Settings(
                    database_url=database_url_text,
                    testing=True,
                    admin_username="bootstrap-admin@example.test",
                    admin_password="changed-bootstrap-password",
                )
                with session_factory() as session:
                    existing = seed_admin(session, changed_bootstrap)
                    assert existing is not None
                    assert existing.id == seeded_id
                    assert existing.password_hash == seeded_hash
                    assert existing.role == ROLE_MEMBER
                    assert existing.is_disabled is True
                    assert not verify_password(existing.password_hash, changed_bootstrap.admin_password)

                with session_factory() as session:
                    member = create_user(
                        session,
                        "session-member@example.test",
                        "member-password",
                    )
                    member_id = member.id
                    second_hash = hash_password("member-password")
                    assert member.password_hash != second_hash
                    assert verify_password(member.password_hash, "member-password")
                    assert verify_password(second_hash, "member-password")
                    assert authenticate_user(session, member.username, "wrong-password") is None
                    assert authenticate_user(session, "unknown@example.test", "member-password") is None

                    old_token, old_session = create_auth_session(session, member, settings)
                    replacement_token, replacement_session = create_auth_session(
                        session,
                        member,
                        settings,
                        presented_token=old_token,
                    )
                    assert old_token != replacement_token
                    assert old_session.id != replacement_session.id
                    assert old_session.revoked_at is not None
                    assert replacement_session.revoked_at is None
                    assert old_session.token_hash == hash_session_token(old_token)
                    assert replacement_session.token_hash == hash_session_token(replacement_token)
                    assert old_token not in {old_session.token_hash, replacement_session.token_hash}
                    assert replacement_token not in {old_session.token_hash, replacement_session.token_hash}
                    assert safe_user(member) == {
                        "id": member.id,
                        "displayName": "session-member@example.test",
                        "role": "member",
                        "disabled": False,
                    }

                    assert revoke_session_token(session, replacement_token) is True
                    assert revoke_session_token(session, replacement_token) is False
                    session.delete(member)
                    session.commit()
                    assert session.scalar(
                        select(AuthSession).where(AuthSession.user_id == member_id)
                    ) is None
                    assert session.get(User, member_id) is None
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p1_02_login_cookie_replacement_and_generic_denial_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "auth_http") as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            settings = Settings(
                database_url=database_url.render_as_string(hide_password=False),
                testing=True,
                session_cookie_secure=False,
                session_cookie_samesite="lax",
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with session_factory() as session:
                    member = create_user(
                        session,
                        "http-member@example.test",
                        "member-password",
                    )
                    member_id = member.id
                    old_token, old_session = create_auth_session(session, member, settings)
                    old_session_id = old_session.id
                    create_user(
                        session,
                        "disabled-member@example.test",
                        "member-password",
                        is_disabled=True,
                    )

                app = create_app(settings)
                with TestClient(app) as first_client:
                    first_client.cookies.set(
                        settings.session_cookie_name,
                        old_token,
                        domain="testserver.local",
                        path="/",
                    )
                    response = first_client.post(
                        f"{CANONICAL_API_PREFIX}/auth/login",
                        json={
                            "username": "http-member@example.test",
                            "password": "member-password",
                        },
                    )
                    assert response.status_code == 200
                    assert response.json() == {
                        "user": {
                            "id": member_id,
                            "displayName": "http-member@example.test",
                            "role": "member",
                            "disabled": False,
                        }
                    }
                    first_token = first_client.cookies.get(settings.session_cookie_name)
                    assert first_token and first_token != old_token
                    assert first_token not in response.text
                    set_cookie = response.headers["set-cookie"].lower()
                    assert "httponly" in set_cookie
                    assert "path=/" in set_cookie
                    assert "samesite=lax" in set_cookie
                    assert "secure" not in set_cookie

                    denial_results = []
                    first_client.cookies.clear()
                    for username, password in (
                        ("unknown@example.test", "member-password"),
                        ("http-member@example.test", "wrong-password"),
                        ("disabled-member@example.test", "member-password"),
                    ):
                        denied = first_client.post(
                            f"{CANONICAL_API_PREFIX}/auth/login",
                            json={"username": username, "password": password},
                        )
                        body = denied.json()["error"]
                        denial_results.append(
                            (denied.status_code, body["code"], body["message"], body["fields"])
                        )
                    assert denial_results == [
                        (401, "invalid_credentials", "Invalid username or password.", {}),
                    ] * 3

                with TestClient(app) as second_client:
                    second_response = second_client.post(
                        f"{CANONICAL_API_PREFIX}/auth/login",
                        json={
                            "username": "http-member@example.test",
                            "password": "member-password",
                        },
                    )
                    assert second_response.status_code == 200
                    second_token = second_client.cookies.get(settings.session_cookie_name)
                    assert second_token and second_token != first_token

                with session_factory() as session:
                    persisted_old = session.get(AuthSession, old_session_id)
                    assert persisted_old is not None and persisted_old.revoked_at is not None
                    first_session = session.scalar(
                        select(AuthSession).where(
                            AuthSession.token_hash == hash_session_token(first_token)
                        )
                    )
                    second_session = session.scalar(
                        select(AuthSession).where(
                            AuthSession.token_hash == hash_session_token(second_token)
                        )
                    )
                    assert first_session is not None and first_session.revoked_at is None
                    assert second_session is not None and second_session.revoked_at is None
                    persisted_hashes = set(session.scalars(select(AuthSession.token_hash)))
                    assert old_token not in persisted_hashes
                    assert first_token not in persisted_hashes
                    assert second_token not in persisted_hashes

                    assert revoke_session_token(session, first_token) is True
                    session.refresh(second_session)
                    assert second_session.revoked_at is None
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p1_02_api_startup_does_not_bootstrap_administrator_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "bootstrap_boundary") as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            settings = Settings(
                database_url=database_url.render_as_string(hide_password=False),
                testing=True,
                admin_username="must-be-explicit@example.test",
                admin_password="bootstrap-password",
            )
            app = create_app(settings)
            with TestClient(app) as client:
                assert client.get("/health/live").status_code == 200

            engine = create_db_engine(settings)
            try:
                with create_session_factory(engine)() as session:
                    assert session.scalar(
                        select(User).where(User.username == settings.admin_username)
                    ) is None
            finally:
                engine.dispose()

            bootstrap_initial_admin(settings)
            engine = create_db_engine(settings)
            try:
                with create_session_factory(engine)() as session:
                    explicit_admin = session.scalar(
                        select(User).where(User.username == settings.admin_username)
                    )
                    assert explicit_admin is not None
                    assert verify_password(explicit_admin.password_hash, settings.admin_password)
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p1_03_auth_me_returns_only_authoritative_current_user_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "auth_me") as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            settings = Settings(
                database_url=database_url.render_as_string(hide_password=False),
                testing=True,
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with session_factory() as session:
                    member = create_user(
                        session,
                        "current-member@example.test",
                        "member-password",
                    )
                    member_id = member.id
                    token, _ = create_auth_session(session, member, settings)

                app = create_app(settings)
                with TestClient(app) as client:
                    client.cookies.set(
                        settings.session_cookie_name,
                        token,
                        domain="testserver.local",
                        path="/",
                    )
                    response = client.get(f"{CANONICAL_API_PREFIX}/auth/me")
                    assert response.status_code == 200
                    assert response.json() == {
                        "user": {
                            "id": member_id,
                            "displayName": "current-member@example.test",
                            "role": "member",
                            "disabled": False,
                        }
                    }
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def _set_session_cookie(client: TestClient, settings: Settings, token: str) -> None:
    client.cookies.set(
        settings.session_cookie_name,
        token,
        domain="testserver.local",
        path="/",
    )


def _stable_error(response) -> tuple[int, str, str, dict[str, str]]:
    body = response.json()["error"]
    assert body["requestId"] == response.headers[CANONICAL_REQUEST_ID_HEADER]
    return response.status_code, body["code"], body["message"], body["fields"]


def test_p1_03_role_recheck_denial_audit_and_owner_isolation_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "authorization") as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            settings = Settings(
                database_url=database_url.render_as_string(hide_password=False),
                testing=True,
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with session_factory() as session:
                    owner = create_user(session, "owner@example.test", "password")
                    outsider = create_user(session, "outsider@example.test", "password")
                    administrator = create_user(
                        session,
                        "administrator@example.test",
                        "password",
                        role=ROLE_ADMINISTRATOR,
                    )
                    owner_token, owner_auth_session = create_auth_session(session, owner, settings)
                    conversation = create_conversation(
                        session,
                        settings=settings,
                        owner=owner,
                        title="Private",
                        auth_session=owner_auth_session,
                    )
                    conversation_ref = conversation.public_ref
                    outsider_token, _ = create_auth_session(session, outsider, settings)
                    admin_token, _ = create_auth_session(session, administrator, settings)
                    outsider_id = outsider.id
                    admin_id = administrator.id

                app = create_app(settings)
                with TestClient(app) as outsider_client:
                    _set_session_cookie(outsider_client, settings, outsider_token)
                    member_denied = outsider_client.get(f"{CANONICAL_API_PREFIX}/admin/users")
                    assert _stable_error(member_denied) == (
                        403,
                        "forbidden",
                        "Forbidden.",
                        {},
                    )
                    cross_owner = outsider_client.get(
                        f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}"
                    )
                    unknown = outsider_client.get(
                        f"{CANONICAL_API_PREFIX}/conversations/conv_{'0' * 32}"
                    )
                    assert _stable_error(cross_owner) == _stable_error(unknown) == (
                        404,
                        "not_found",
                        "Conversation not found.",
                        {},
                    )

                with TestClient(app) as admin_client:
                    _set_session_cookie(admin_client, settings, admin_token)
                    assert admin_client.get(f"{CANONICAL_API_PREFIX}/admin/users").status_code == 200
                    admin_non_owner = admin_client.get(
                        f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}"
                    )
                    assert _stable_error(admin_non_owner) == (
                        404,
                        "not_found",
                        "Conversation not found.",
                        {},
                    )

                    with session_factory() as session:
                        current_admin = session.get(User, admin_id)
                        assert current_admin is not None
                        current_admin.role = ROLE_MEMBER
                        session.commit()

                    downgraded = admin_client.get(f"{CANONICAL_API_PREFIX}/admin/users")
                    assert _stable_error(downgraded) == (
                        403,
                        "forbidden",
                        "Forbidden.",
                        {},
                    )

                with TestClient(app) as owner_client:
                    _set_session_cookie(owner_client, settings, owner_token)
                    assert owner_client.get(
                        f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}"
                    ).status_code == 200
                    with session_factory() as session:
                        current_owner = session.scalar(
                            select(User).where(User.username == "owner@example.test")
                        )
                        assert current_owner is not None
                        current_owner.is_disabled = True
                        session.commit()
                    assert _stable_error(owner_client.get(f"{CANONICAL_API_PREFIX}/auth/me")) == (
                        401,
                        "unauthenticated",
                        "Authentication required.",
                        {},
                    )

                with session_factory() as session:
                    denied_events = list(
                        session.scalars(
                            select(AuditEvent)
                            .where(AuditEvent.event_name == AUDIT_EVENT_SECURITY_ADMIN_ROUTE_DENIED)
                            .order_by(AuditEvent.created_at, AuditEvent.id)
                        )
                    )
                    assert len(denied_events) == 2
                    assert {event.actor_user_id for event in denied_events} == {outsider_id, admin_id}
                    assert all(event.outcome == "denied" for event in denied_events)
                    assert all(event.safe_error_code == "forbidden" for event in denied_events)
                    assert all(event.request_id for event in denied_events)
                    # P8-01: denial rows stay role-safe — no resource-existence target.
                    assert all(event.target_id is None for event in denied_events)
                    assert all(event.target_kind is None for event in denied_events)
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p1_03_every_registered_admin_route_uses_authoritative_admin_guard() -> None:
    admin_routes = [
        route
        for route in api_router.routes
        if isinstance(route, APIRoute) and route.path.startswith("/admin/")
    ]
    assert admin_routes
    for route in admin_routes:
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert require_admin in dependency_calls, f"{sorted(route.methods)} {route.path} lacks require_admin"


def _assert_safe_readiness_failure(response) -> None:
    assert response.status_code == 503
    assert response.headers["cache-control"] == "private, no-store, no-transform"
    assert response.json() == {
        "error": {
            "code": "dependency_unavailable",
            "message": "Service unavailable.",
            "requestId": response.headers[CANONICAL_REQUEST_ID_HEADER],
            "fields": {},
        }
    }


def test_p1_04_readiness_requires_exact_schema_and_bootstrap_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "readiness") as database_url:
            config = _alembic_config(database_url)
            command.upgrade(config, "head")
            settings = Settings(
                database_url=database_url.render_as_string(hide_password=False),
                testing=True,
                admin_username="readiness-admin@example.test",
                admin_password="bootstrap-password",
            )
            app = create_app(settings)
            with TestClient(app) as client:
                _assert_safe_readiness_failure(client.get("/health/ready"))
                assert client.get("/health/live").json() == {"status": "live"}

                bootstrap_initial_admin(settings)
                ready = client.get("/health/ready")
                assert ready.status_code == 200
                assert ready.json() == {"status": "ready"}

                engine = create_db_engine(settings)
                try:
                    with engine.begin() as connection:
                        connection.execute(
                            text("UPDATE alembic_version SET version_num = :version"),
                            {"version": BASELINE_REVISION},
                        )
                    _assert_safe_readiness_failure(client.get("/health/ready"))
                    assert client.get("/health/live").status_code == 200

                    with engine.begin() as connection:
                        connection.execute(
                            text("UPDATE alembic_version SET version_num = :version"),
                            {"version": HEAD_REVISION},
                        )
                        connection.execute(
                            text("UPDATE users SET is_disabled = true WHERE username = :username"),
                            {"username": settings.admin_username},
                        )
                    _assert_safe_readiness_failure(client.get("/health/ready"))
                    assert client.get("/health/live").status_code == 200
                finally:
                    engine.dispose()
    finally:
        admin_engine.dispose()
