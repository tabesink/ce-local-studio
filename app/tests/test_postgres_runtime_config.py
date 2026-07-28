from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os
from pathlib import Path
import re
from threading import Barrier, BrokenBarrierError
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.models import (
    AUDIT_EVENT_RUNTIME_DEFAULTS_UPDATED,
    AUDIT_EVENT_RUNTIME_MODEL_PROFILE_CREATED,
    AUDIT_EVENT_RUNTIME_PROVIDER_CONFIG_ROTATED,
    AuditEvent,
    DOMAIN_STATE_STOPPED,
    PARSER_DOCLING,
    PARSER_REDUCTO,
    PROFILE_EMBEDDING,
    PROFILE_SYNTHESIS,
    PROVIDER_KINDS,
    PROVIDER_OPENAI,
    PROVIDER_REDUCTO,
    Domain,
    ModelProfile,
    ProviderConfig,
    ROLE_ADMINISTRATOR,
    RuntimeSettings,
    User,
)
from context_engine.api.contract_app import CANONICAL_API_PREFIX, CANONICAL_REQUEST_ID_HEADER
from context_engine.security import hash_session_token
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.csrf import issue_csrf_token
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)
from context_engine.services.runtime_config import (
    DEFAULT_MODEL_PROFILE_IDS,
    DEFAULT_SYNTHESIS_PROFILE_ID,
    MODEL_CATALOG,
    RuntimeConfigError,
    SecretCrypto,
    create_model_profile,
    delete_model_profile,
    rotate_provider_credential,
    runtime_settings_snapshot,
    seed_runtime_config,
    update_model_profile,
    update_runtime_settings,
)


APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
HEAD_REVISION = "d4e7a1b92c80"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p20[123]_[a-z_]+_[0-9a-f]{32}$")

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
    database_name = f"ce_p203_{label}_{uuid4().hex}"
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


def test_p2_01_runtime_config_schema_and_services_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "runtime") as database_url:
            config = _alembic_config(database_url)
            script = ScriptDirectory.from_config(config)
            assert script.get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            settings = Settings(
                database_url=database_url.render_as_string(hide_password=False),
                testing=True,
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with engine.connect() as connection:
                    checks = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT conname FROM pg_constraint "
                                "WHERE conrelid IN ("
                                " 'provider_configs'::regclass,"
                                " 'model_profiles'::regclass,"
                                " 'runtime_settings'::regclass"
                                ")"
                            )
                        )
                    }
                assert "ck_provider_configs_provider_kind" in checks
                assert "ck_model_profiles_embedding_dimensions_required" in checks
                assert "ck_model_profiles_synthesis_dimensions_absent" in checks
                assert "ck_runtime_settings_singleton" in checks

                db = session_factory()
                try:
                    seed_runtime_config(db)
                    openai = db.get(ProviderConfig, PROVIDER_OPENAI)
                    assert openai is not None
                    openai.display_name = "Custom OpenAI Label"
                    openai.credential_ciphertext = "sentinel-ciphertext"
                    openai.requires_credentials = True
                    db.commit()

                    seed_runtime_config(db)
                    openai = db.get(ProviderConfig, PROVIDER_OPENAI)
                    assert openai is not None
                    assert openai.display_name == "Custom OpenAI Label"
                    assert openai.credential_ciphertext == "sentinel-ciphertext"

                    providers = list(db.scalars(select(ProviderConfig)))
                    assert {provider.provider_kind for provider in providers} == set(PROVIDER_KINDS)
                    profiles = list(db.scalars(select(ModelProfile)))
                    assert {profile.id for profile in profiles} >= {entry.seed_id for entry in MODEL_CATALOG}
                    singleton = db.get(RuntimeSettings, 1)
                    assert singleton is not None
                    assert singleton.active_parser_kind == PARSER_DOCLING

                    with pytest.raises((IntegrityError, DBAPIError)):
                        db.add(
                            ModelProfile(
                                id=str(uuid4()),
                                name="Bad Embedding",
                                profile_kind=PROFILE_EMBEDDING,
                                provider_kind=PROVIDER_OPENAI,
                                model_name="text-embedding-3-small",
                                vector_dimensions=None,
                            )
                        )
                        db.commit()
                    db.rollback()

                    with pytest.raises((IntegrityError, DBAPIError)):
                        db.execute(
                            text(
                                "INSERT INTO runtime_settings "
                                "(id, active_synthesis_profile_id, active_parser_kind, created_at, updated_at) "
                                "VALUES (2, NULL, 'docling', NOW(), NOW())"
                            )
                        )
                        db.commit()
                    db.rollback()

                    admin = create_user(db, username="runtime-admin", password="Password123!", role=ROLE_ADMINISTRATOR)
                    audit = AuditContext(actor_user=admin, request_id="req-p201", actor_kind="administrator")

                    created = create_model_profile(
                        db,
                        name="OpenAI GPT-4o Extra",
                        profile_kind=PROFILE_SYNTHESIS,
                        provider_kind=PROVIDER_OPENAI,
                        model_name="gpt-4o",
                        vector_dimensions=None,
                        audit_context=audit,
                    )
                    assert created.id not in DEFAULT_MODEL_PROFILE_IDS
                    created_audit = db.scalar(
                        select(AuditEvent).where(AuditEvent.event_name == AUDIT_EVENT_RUNTIME_MODEL_PROFILE_CREATED)
                    )
                    assert created_audit is not None
                    assert created_audit.request_id == "req-p201"
                    assert created_audit.target_kind == "model_profile"
                    assert created_audit.target_id == created.id

                    with pytest.raises(RuntimeConfigError) as default_delete:
                        delete_model_profile(db, DEFAULT_SYNTHESIS_PROFILE_ID, audit_context=audit)
                    assert default_delete.value.code == "model_profile_in_use"

                    crypto = SecretCrypto.from_settings(settings)
                    # Clear sentinel so rotate can set real ciphertext without leaking plaintext in asserts.
                    openai = db.get(ProviderConfig, PROVIDER_OPENAI)
                    assert openai is not None
                    openai.credential_ciphertext = None
                    openai.version = 1
                    db.commit()
                    rotated = rotate_provider_credential(
                        db,
                        PROVIDER_OPENAI,
                        "test-openai-key",
                        crypto,
                        expected_version=1,
                        audit_context=audit,
                    )
                    assert rotated.version == 2
                    assert rotated.credential_ciphertext is not None
                    assert rotated.credential_ciphertext != "test-openai-key"
                    assert crypto.decrypt_secret(rotated.credential_ciphertext) == "test-openai-key"

                    settings_row = db.get(RuntimeSettings, 1)
                    assert settings_row is not None
                    updated = update_runtime_settings(
                        db,
                        {"active_synthesis_profile_id": DEFAULT_SYNTHESIS_PROFILE_ID},
                        expected_version=settings_row.version,
                        audit_context=audit,
                    )
                    assert updated.active_synthesis_profile_id == DEFAULT_SYNTHESIS_PROFILE_ID
                    defaults_audit = db.scalar(
                        select(AuditEvent).where(AuditEvent.event_name == AUDIT_EVENT_RUNTIME_DEFAULTS_UPDATED)
                    )
                    assert defaults_audit is not None

                    with pytest.raises(RuntimeConfigError) as reducto_not_ready:
                        update_runtime_settings(
                            db,
                            {"active_parser_kind": PARSER_REDUCTO},
                            expected_version=updated.version,
                            audit_context=audit,
                        )
                    assert reducto_not_ready.value.code == "provider_not_ready"

                    reducto = db.get(ProviderConfig, PROVIDER_REDUCTO)
                    assert reducto is not None
                    rotate_provider_credential(
                        db,
                        PROVIDER_REDUCTO,
                        "test-reducto-key",
                        crypto,
                        expected_version=reducto.version,
                        audit_context=audit,
                    )
                    parser_updated = update_runtime_settings(
                        db,
                        {"active_parser_kind": PARSER_REDUCTO},
                        expected_version=updated.version,
                        audit_context=audit,
                    )
                    assert parser_updated.active_parser_kind == PARSER_REDUCTO

                    snapshot = runtime_settings_snapshot(db)
                    serialized = str(snapshot).lower()
                    assert "ciphertext" not in serialized
                    assert "test-openai-key" not in serialized
                    assert "test-reducto-key" not in serialized
                    for provider in snapshot["providers"]:
                        assert set(provider.keys()) == {
                            "kind",
                            "displayName",
                            "requiresCredentials",
                            "configured",
                            "credentialUpdatedAt",
                            "version",
                        }
                        assert "credential" not in provider
                        assert isinstance(provider["version"], int) and provider["version"] >= 1
                    for profile in snapshot["modelProfiles"]:
                        assert set(profile.keys()) == {
                            "id",
                            "name",
                            "profileKind",
                            "providerKind",
                            "modelName",
                            "vectorDimensions",
                            "inUse",
                            "version",
                        }
                        assert "isDefault" not in profile
                    assert set(snapshot["runtimeSettings"].keys()) == {
                        "activeSynthesisProfileId",
                        "activeParserKind",
                        "version",
                    }
                finally:
                    db.close()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p2_02_provider_credential_version_race_and_http_a01_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "cred") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            database_url_text = database_url.render_as_string(hide_password=False)
            settings = Settings(
                database_url=database_url_text,
                testing=True,
                public_origin="http://ce.example.test",
                internal_hosts="testserver",
                trusted_bff_peers="testclient",
                csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
                session_cookie_secure=False,
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with engine.connect() as connection:
                    version_checks = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT conname FROM pg_constraint "
                                "WHERE conrelid IN ("
                                " 'provider_configs'::regclass,"
                                " 'model_profiles'::regclass,"
                                " 'runtime_settings'::regclass"
                                ") AND conname LIKE '%version%'"
                            )
                        )
                    }
                assert "ck_provider_configs_version_positive" in version_checks
                assert "ck_model_profiles_version_positive" in version_checks
                assert "ck_runtime_settings_version_positive" in version_checks

                db = session_factory()
                try:
                    seed_runtime_config(db)
                    admin = create_user(db, username="p202-admin", password="Password123!", role=ROLE_ADMINISTRATOR)
                    audit = AuditContext(actor_user=admin, request_id="req-p202", actor_kind="administrator")
                    crypto = SecretCrypto.from_settings(settings)

                    settings_before = db.get(RuntimeSettings, 1)
                    assert settings_before is not None
                    assert settings_before.active_synthesis_profile_id is None
                    settings_version_before = settings_before.version

                    first = rotate_provider_credential(
                        db,
                        PROVIDER_OPENAI,
                        "first-secret",
                        crypto,
                        expected_version=1,
                        audit_context=audit,
                    )
                    assert first.version == 2
                    db.expire_all()
                    settings_after = db.get(RuntimeSettings, 1)
                    assert settings_after is not None
                    assert settings_after.active_synthesis_profile_id == DEFAULT_SYNTHESIS_PROFILE_ID
                    assert settings_after.version == settings_version_before + 1
                    with pytest.raises(RuntimeConfigError) as stale_settings:
                        update_runtime_settings(
                            db,
                            {"active_parser_kind": PARSER_DOCLING},
                            expected_version=settings_version_before,
                            audit_context=audit,
                        )
                    assert stale_settings.value.code == "stale_revision"

                    with pytest.raises(RuntimeConfigError) as stale:
                        rotate_provider_credential(
                            db,
                            PROVIDER_OPENAI,
                            "stale-secret",
                            crypto,
                            expected_version=1,
                            audit_context=audit,
                        )
                    assert stale.value.status_code == 409
                    assert stale.value.code == "stale_revision"
                    openai = db.get(ProviderConfig, PROVIDER_OPENAI)
                    assert openai is not None
                    assert crypto.decrypt_secret(openai.credential_ciphertext or "") == "first-secret"

                    barrier = Barrier(2)
                    outcomes: list[str] = []
                    admin_id = admin.id

                    def _racing_rotate(secret: str) -> None:
                        local_db = session_factory()
                        try:
                            actor = local_db.get(User, admin_id)
                            assert actor is not None
                            barrier.wait(timeout=5)
                            rotate_provider_credential(
                                local_db,
                                PROVIDER_OPENAI,
                                secret,
                                crypto,
                                expected_version=2,
                                audit_context=AuditContext(
                                    actor_user=actor,
                                    request_id=f"req-{secret}",
                                    actor_kind="administrator",
                                ),
                            )
                            outcomes.append("ok")
                        except RuntimeConfigError as exc:
                            assert exc.code == "stale_revision"
                            outcomes.append("stale")
                        except BrokenBarrierError:
                            outcomes.append("barrier")
                        finally:
                            local_db.close()

                    with ThreadPoolExecutor(max_workers=2) as pool:
                        futures = [
                            pool.submit(_racing_rotate, "race-a"),
                            pool.submit(_racing_rotate, "race-b"),
                        ]
                        for future in futures:
                            future.result(timeout=15)
                    assert sorted(outcomes) == ["ok", "stale"]
                    db.expire_all()
                    openai = db.get(ProviderConfig, PROVIDER_OPENAI)
                    assert openai is not None
                    assert openai.version == 3
                    assert crypto.decrypt_secret(openai.credential_ciphertext or "") in {"race-a", "race-b"}
                    rotate_audits = list(
                        db.scalars(
                            select(AuditEvent).where(
                                AuditEvent.event_name == AUDIT_EVENT_RUNTIME_PROVIDER_CONFIG_ROTATED
                            )
                        )
                    )
                    # Initial rotate plus one concurrent winner; the stale loser writes no audit.
                    assert len(rotate_audits) == 2
                finally:
                    db.close()

                app = create_app(settings)
                with session_factory() as session:
                    admin_row = session.scalar(select(User).where(User.username == "p202-admin"))
                    assert admin_row is not None
                    token, _auth_session = create_auth_session(session, admin_row, settings)
                    csrf = issue_csrf_token(settings, binding=hash_session_token(token))

                with TestClient(app) as client:
                    client.cookies.set(settings.session_cookie_name, token, path="/")
                    client.cookies.set(settings.csrf_cookie_name, csrf, path="/")
                    headers = {
                        "Origin": "http://ce.example.test",
                        CSRF_HEADER: csrf,
                        PUBLIC_HOST_HEADER: "ce.example.test",
                        PUBLIC_PROTO_HEADER: "http",
                        CLIENT_BUCKET_HEADER: "p202-bucket",
                    }
                    missing = client.put(
                        f"{CANONICAL_API_PREFIX}/admin/runtime-settings/providers/openai",
                        headers=headers,
                        json={"credential": "http-secret"},
                    )
                    assert missing.status_code == 428
                    assert missing.json()["error"]["code"] == "validation_error"
                    assert CANONICAL_REQUEST_ID_HEADER in missing.headers

                    snapshot = client.get(
                        f"{CANONICAL_API_PREFIX}/admin/runtime-settings",
                        headers=headers,
                    )
                    assert snapshot.status_code == 200
                    provider = next(item for item in snapshot.json()["providers"] if item["kind"] == "openai")
                    version = provider["version"]
                    assert provider["configured"] is True
                    assert "credential" not in provider

                    stale_http = client.put(
                        f"{CANONICAL_API_PREFIX}/admin/runtime-settings/providers/openai",
                        headers={**headers, "If-Match": f'"{version - 1}"'},
                        json={"credential": "http-stale"},
                    )
                    assert stale_http.status_code == 409
                    assert stale_http.json()["error"]["code"] == "stale_revision"

                    ok = client.put(
                        f"{CANONICAL_API_PREFIX}/admin/runtime-settings/providers/openai",
                        headers={**headers, "If-Match": f'"{version}"'},
                        json={"credential": "http-secret"},
                    )
                    assert ok.status_code == 200
                    assert ok.headers["etag"] == f'"{version + 1}"'
                    assert ok.headers["cache-control"] == "private, no-store, no-transform"
                    body = ok.json()["provider"]
                    assert body["kind"] == "openai"
                    assert body["configured"] is True
                    assert body["version"] == version + 1
                    assert "credential" not in body
                    assert "http-secret" not in str(ok.json()).lower()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()


def test_p2_03_immutable_embedding_and_defaults_on_postgresql_16() -> None:
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "embed") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            database_url_text = database_url.render_as_string(hide_password=False)
            settings = Settings(
                database_url=database_url_text,
                testing=True,
                public_origin="http://ce.example.test",
                internal_hosts="testserver",
                trusted_bff_peers="testclient",
                csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
                session_cookie_secure=False,
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                db = session_factory()
                try:
                    seed_runtime_config(db)
                    admin = create_user(db, username="p203-admin", password="Password123!", role=ROLE_ADMINISTRATOR)
                    audit = AuditContext(actor_user=admin, request_id="req-p203", actor_kind="administrator")

                    used = db.get(ModelProfile, "openai-embedding-default")
                    assert used is not None
                    assert used.vector_dimensions == 1536
                    db.add(
                        Domain(
                            id="domain_manuals",
                            display_name="Equipment Manuals",
                            state=DOMAIN_STATE_STOPPED,
                            embedding_profile_id=used.id,
                            runtime_instance_id=str(uuid4()),
                            control_generation=1,
                        )
                    )
                    db.commit()

                    snapshot = runtime_settings_snapshot(db)
                    used_projection = next(
                        profile for profile in snapshot["modelProfiles"] if profile["id"] == used.id
                    )
                    assert used_projection["inUse"] is True
                    assert used_projection["vectorDimensions"] == 1536

                    with pytest.raises(RuntimeConfigError) as dim_denied:
                        update_model_profile(
                            db,
                            used.id,
                            {"vector_dimensions": 3072, "model_name": "text-embedding-3-large"},
                            expected_version=used.version,
                            audit_context=audit,
                        )
                    assert dim_denied.value.status_code == 409
                    assert dim_denied.value.code == "model_profile_in_use"

                    with pytest.raises(RuntimeConfigError) as name_denied:
                        update_model_profile(
                            db,
                            used.id,
                            {"name": "Renamed Used Embedding"},
                            expected_version=used.version,
                            audit_context=audit,
                        )
                    assert name_denied.value.code == "model_profile_in_use"

                    with pytest.raises(RuntimeConfigError) as delete_denied:
                        delete_model_profile(db, used.id, audit_context=audit)
                    assert delete_denied.value.code == "model_profile_in_use"

                    db.expire_all()
                    used_after = db.get(ModelProfile, used.id)
                    assert used_after is not None
                    assert used_after.vector_dimensions == 1536
                    assert used_after.model_name == "text-embedding-3-small"
                    assert used_after.name == "OpenAI Default Embedding"
                    assert used_after.version == 1

                    unused = create_model_profile(
                        db,
                        name="OpenAI Embedding Large Extra",
                        profile_kind=PROFILE_EMBEDDING,
                        provider_kind=PROVIDER_OPENAI,
                        model_name="text-embedding-3-large",
                        vector_dimensions=3072,
                        audit_context=audit,
                    )
                    unused_version = unused.version
                    renamed = update_model_profile(
                        db,
                        unused.id,
                        {"name": "OpenAI Embedding Large Unused"},
                        expected_version=unused_version,
                        audit_context=audit,
                    )
                    assert renamed.name == "OpenAI Embedding Large Unused"
                    assert renamed.vector_dimensions == 3072
                    assert renamed.version == unused_version + 1

                    settings_row = db.get(RuntimeSettings, 1)
                    assert settings_row is not None
                    with pytest.raises(RuntimeConfigError) as embedding_as_synthesis:
                        update_runtime_settings(
                            db,
                            {"active_synthesis_profile_id": used.id},
                            expected_version=settings_row.version,
                            audit_context=audit,
                        )
                    assert embedding_as_synthesis.value.code == "invalid_active_synthesis_profile"

                    with pytest.raises((IntegrityError, DBAPIError)):
                        db.execute(
                            text(
                                "UPDATE model_profiles SET vector_dimensions = 0 "
                                "WHERE id = :profile_id"
                            ),
                            {"profile_id": unused.id},
                        )
                        db.commit()
                    db.rollback()
                finally:
                    db.close()

                app = create_app(settings)
                with session_factory() as session:
                    admin_row = session.scalar(select(User).where(User.username == "p203-admin"))
                    assert admin_row is not None
                    token, _auth_session = create_auth_session(session, admin_row, settings)
                    csrf = issue_csrf_token(settings, binding=hash_session_token(token))

                with TestClient(app) as client:
                    client.cookies.set(settings.session_cookie_name, token, path="/")
                    client.cookies.set(settings.csrf_cookie_name, csrf, path="/")
                    headers = {
                        "Origin": "http://ce.example.test",
                        CSRF_HEADER: csrf,
                        PUBLIC_HOST_HEADER: "ce.example.test",
                        PUBLIC_PROTO_HEADER: "http",
                        CLIENT_BUCKET_HEADER: "p203-bucket",
                    }

                    snapshot = client.get(
                        f"{CANONICAL_API_PREFIX}/admin/runtime-settings",
                        headers=headers,
                    )
                    assert snapshot.status_code == 200
                    used_http = next(
                        profile
                        for profile in snapshot.json()["modelProfiles"]
                        if profile["id"] == "openai-embedding-default"
                    )
                    assert used_http["inUse"] is True
                    used_version = used_http["version"]

                    denied = client.patch(
                        f"{CANONICAL_API_PREFIX}/admin/runtime-settings/model-profiles/openai-embedding-default",
                        headers={**headers, "If-Match": f'"{used_version}"'},
                        json={
                            "modelName": "text-embedding-3-large",
                            "vectorDimensions": 3072,
                        },
                    )
                    assert denied.status_code == 409
                    assert denied.json()["error"]["code"] == "model_profile_in_use"
                    assert CANONICAL_REQUEST_ID_HEADER in denied.headers

                    created = client.post(
                        f"{CANONICAL_API_PREFIX}/admin/runtime-settings/model-profiles",
                        headers=headers,
                        json={
                            "name": "OpenAI Embedding Ada Extra",
                            "profileKind": "embedding",
                            "providerKind": "openai",
                            "modelName": "text-embedding-ada-002",
                            "vectorDimensions": 1536,
                        },
                    )
                    assert created.status_code == 201
                    body = created.json()["modelProfile"]
                    assert body["profileKind"] == "embedding"
                    assert body["vectorDimensions"] == 1536
                    assert body["inUse"] is False
                    assert "ETag" in created.headers or "etag" in created.headers
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
