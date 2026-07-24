from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.models import (
    AUDIT_EVENT_RUNTIME_DEFAULTS_UPDATED,
    AUDIT_EVENT_RUNTIME_MODEL_PROFILE_CREATED,
    AuditEvent,
    PARSER_DOCLING,
    PARSER_REDUCTO,
    PROFILE_EMBEDDING,
    PROFILE_SYNTHESIS,
    PROVIDER_KINDS,
    PROVIDER_OPENAI,
    PROVIDER_REDUCTO,
    ModelProfile,
    ProviderConfig,
    ROLE_ADMINISTRATOR,
    RuntimeSettings,
)
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_user
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
    update_runtime_settings,
)


APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
HEAD_REVISION = "c4e8f1a02b93"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p201_[a-z_]+_[0-9a-f]{32}$")

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
    database_name = f"ce_p201_{label}_{uuid4().hex}"
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
                    db.commit()
                    rotate_provider_credential(db, PROVIDER_OPENAI, "test-openai-key", crypto, audit_context=audit)

                    updated = update_runtime_settings(
                        db,
                        {"active_synthesis_profile_id": DEFAULT_SYNTHESIS_PROFILE_ID},
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
                            audit_context=audit,
                        )
                    assert reducto_not_ready.value.code == "provider_not_ready"

                    rotate_provider_credential(db, PROVIDER_REDUCTO, "test-reducto-key", crypto, audit_context=audit)
                    parser_updated = update_runtime_settings(
                        db,
                        {"active_parser_kind": PARSER_REDUCTO},
                        audit_context=audit,
                    )
                    assert parser_updated.active_parser_kind == PARSER_REDUCTO

                    snapshot = runtime_settings_snapshot(db)
                    serialized = str(snapshot).lower()
                    assert "ciphertext" not in serialized
                    assert "test-openai-key" not in serialized
                    assert "test-reducto-key" not in serialized
                    for provider in snapshot["providers"]:
                        assert "credential" not in provider
                        assert "ciphertext" not in provider
                        assert set(provider.keys()) <= {"providerKind", "isConfigured"}
                finally:
                    db.close()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
