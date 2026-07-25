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
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import IntegrityError

from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.models import (
    ROLE_ADMINISTRATOR,
    SOURCE_PREP_STATUS_QUEUED,
    SOURCE_STATE_PENDING,
    SourceDocument,
    SourcePreparationOperation,
)
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_user
from context_engine.services.domains import create_domain
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config
from context_engine.services.sources import new_document_public_ref, safe_source, upload_source_bytes

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p401_[a-z0-9_]+$")
HEAD_REVISION = "f4b2c9e18a70"

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
    database_name = f"ce_p401_{label}_{uuid4().hex}"
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


def test_p4_01_source_schema_refs_and_object_storage_on_postgresql_16(tmp_path: Path) -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "sources") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            database_url_text = database_url.render_as_string(hide_password=False)
            storage_root = tmp_path / "source-storage"
            settings = Settings(
                database_url=database_url_text,
                testing=True,
                public_origin="http://ce.example.test",
                internal_hosts="testserver",
                trusted_bff_peers="testclient",
                csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
                session_cookie_secure=False,
                domain_runtime_controller_kind="local",
                domain_runtime_root=str(tmp_path / "domain-runtimes"),
                source_storage_root=str(storage_root),
            )
            engine = create_db_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                with engine.connect() as connection:
                    constraints = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT conname FROM pg_constraint "
                                "WHERE conrelid IN ("
                                " 'source_documents'::regclass,"
                                " 'source_preparation_operations'::regclass"
                                ")"
                            )
                        )
                    }
                    indexes = {
                        row[0]
                        for row in connection.execute(
                            text(
                                "SELECT indexname FROM pg_indexes "
                                "WHERE tablename IN ('source_documents', 'source_preparation_operations')"
                            )
                        )
                    }
                assert "ck_source_documents_version_positive" in constraints
                assert "ck_source_preparation_operations_version_positive" in constraints
                assert "uq_source_documents_public_ref" in indexes
                assert "uq_source_documents_original_object_key" in indexes
                assert "uq_source_documents_domain_hash" in indexes
                assert "uq_source_preparation_operations_one_active" in indexes

                db = session_factory()
                try:
                    seed_runtime_config(db)
                    admin = create_user(db, username="p401-admin", password="Password123!", role=ROLE_ADMINISTRATOR)
                    audit = AuditContext(actor_user=admin, request_id="req-p401", actor_kind="administrator")
                    rotate_provider_credential(
                        db,
                        "openai",
                        "sk-test-openai-p401",
                        SecretCrypto.from_settings(settings),
                        expected_version=1,
                        audit_context=audit,
                    )
                    domain = create_domain(
                        db,
                        settings=settings,
                        domain_id="domain-manuals",
                        display_name="Equipment Manuals",
                        embedding_profile_id="openai-embedding-default",
                        requested_by_user=admin,
                        audit_context=audit,
                    )

                    payload = b"%PDF-1.4 p4-01 fixture bytes"
                    source, operation = upload_source_bytes(
                        db,
                        settings=settings,
                        domain_id=domain.id,
                        filename="pump-service-manual.pdf",
                        content_type="application/pdf",
                        data=payload,
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    assert source.state == SOURCE_STATE_PENDING
                    assert source.public_ref.startswith("doc_")
                    assert source.original_object_key.startswith("obj_")
                    assert source.version == 1
                    assert operation.status == SOURCE_PREP_STATUS_QUEUED
                    assert operation.version == 1
                    object_path = storage_root / "objects" / source.original_object_key
                    assert object_path.read_bytes() == payload

                    projection = safe_source(db, source)
                    assert projection["documentRef"] == source.public_ref
                    assert projection["displayName"] == "pump-service-manual.pdf"
                    assert "originalSha256" not in projection
                    assert source.original_object_key not in str(projection.values())

                    with pytest.raises(IntegrityError):
                        db.add(
                            SourceDocument(
                                id=str(uuid4()),
                                public_ref=new_document_public_ref(),
                                domain_id=domain.id,
                                original_filename="dup.pdf",
                                content_type="application/pdf",
                                original_sha256=source.original_sha256,
                                original_size_bytes=12,
                                original_object_key=f"obj_{uuid4().hex}",
                                state=SOURCE_STATE_PENDING,
                                parser_kind="docling",
                            )
                        )
                        db.flush()
                    db.rollback()

                    with pytest.raises(IntegrityError):
                        db.add(
                            SourcePreparationOperation(
                                id=str(uuid4()),
                                source_document_id=source.id,
                                domain_id=domain.id,
                                status=SOURCE_PREP_STATUS_QUEUED,
                                preparation_generation_at_start=1,
                            )
                        )
                        db.flush()
                    db.rollback()
                finally:
                    db.close()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
