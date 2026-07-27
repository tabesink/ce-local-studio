from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
import hashlib
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

from context_engine.adapters.parsers import (
    DoclingDocumentParser,
    PreparedBlock,
    PreparedImage,
    PreparedSource,
)
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory, utc_now
from context_engine.models import (
    PARSER_DOCLING,
    ROLE_ADMINISTRATOR,
    SOURCE_BLOCK_KIND_FIGURE,
    SOURCE_BLOCK_KIND_TEXT,
    SOURCE_PREP_STATUS_QUEUED,
    SOURCE_PREP_STATUS_RUNNING,
    SOURCE_PREP_STATUS_SUCCEEDED,
    SOURCE_STATE_PENDING,
    SOURCE_STATE_PREPARED,
    SourceBlock,
    SourceImage,
    SourcePreparationOperation,
)
from context_engine.services.audit import AuditContext
from context_engine.services.auth import create_user
from context_engine.services.domains import create_domain
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.runtime_config import SecretCrypto, rotate_provider_credential, seed_runtime_config
from context_engine.services.sources import (
    SourcePreparationWorker,
    publish_prepared_source,
    storage_from_settings,
    upload_source_bytes,
)

APP_ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL"
OPT_IN_ENV = "CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS"
DATABASE_NAME_PATTERN = re.compile(r"^ce_p403_[a-z0-9_]+$")
HEAD_REVISION = "e9f2a1b83c70"

pytestmark = pytest.mark.postgresql


def _required_admin_url() -> URL:
    if os.getenv(OPT_IN_ENV) != "1":
        pytest.skip(f"set {OPT_IN_ENV}=1 to allow disposable PostgreSQL database tests")
    raw_url = os.getenv(ADMIN_URL_ENV)
    if not raw_url:
        pytest.fail(f"{ADMIN_URL_ENV} is required when disposable PostgreSQL database tests are enabled")
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
    database_name = f"ce_p403_{label}_{uuid4().hex}"
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


def _settings(database_url_text: str, tmp_path: Path, *, worker_id: str = "prep-worker-a") -> Settings:
    return Settings(
        database_url=database_url_text,
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        session_cookie_secure=False,
        domain_runtime_controller_kind="local",
        domain_runtime_root=str(tmp_path / "domain-runtimes"),
        source_storage_root=str(tmp_path / "source-storage"),
        source_prep_worker_id=worker_id,
        source_prep_lease_seconds=30,
        source_parser_timeout_seconds=5,
    )


def _sample_prepared(source_id: str) -> PreparedSource:
    png = b"\x89PNG\r\n\x1a\n" + b"p4-03"
    return PreparedSource(
        source_document_id=source_id,
        parser_kind=PARSER_DOCLING,
        blocks=[
            PreparedBlock(source_order=1, kind=SOURCE_BLOCK_KIND_TEXT, canonical_markdown="Canonical body"),
            PreparedBlock(source_order=2, kind=SOURCE_BLOCK_KIND_FIGURE, canonical_markdown="Figure"),
        ],
        images=[
            PreparedImage(
                source_order=2,
                content_hash=hashlib.sha256(png).hexdigest(),
                mime_type="image/png",
                bytes_data=png,
                alt_text="Diagram",
                page_number=1,
            )
        ],
    )


def test_p4_03_publish_fence_and_atomic_blocks_on_postgresql_16(tmp_path: Path) -> None:
    assert HEAD_REVISION == SUPPORTED_ALEMBIC_HEAD
    admin_url = _required_admin_url()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        _assert_postgresql_16(admin_engine)
        with _disposable_database(admin_engine, admin_url, "prep") as database_url:
            config = _alembic_config(database_url)
            assert ScriptDirectory.from_config(config).get_heads() == [HEAD_REVISION]
            command.upgrade(config, "head")

            database_url_text = database_url.render_as_string(hide_password=False)
            settings_a = _settings(database_url_text, tmp_path, worker_id="prep-worker-a")
            engine = create_db_engine(settings_a)
            session_factory = create_session_factory(engine)
            try:
                with engine.connect() as connection:
                    indexes = {
                        row[0]
                        for row in connection.execute(
                            text("SELECT indexname FROM pg_indexes WHERE tablename = 'source_images'")
                        )
                    }
                assert "uq_source_images_object_key" in indexes

                db = session_factory()
                try:
                    seed_runtime_config(db)
                    admin = create_user(db, username="p403-admin", password="Password123!", role=ROLE_ADMINISTRATOR)
                    audit = AuditContext(actor_user=admin, request_id="req-p403", actor_kind="administrator")
                    rotate_provider_credential(
                        db,
                        "openai",
                        "sk-test-openai-p403",
                        SecretCrypto.from_settings(settings_a),
                        expected_version=1,
                        audit_context=audit,
                    )
                    domain = create_domain(
                        db,
                        settings=settings_a,
                        domain_id="domain-prep",
                        display_name="Prep Domain",
                        embedding_profile_id="openai-embedding-default",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    source, operation = upload_source_bytes(
                        db,
                        settings=settings_a,
                        domain_id=domain.id,
                        filename="manual.pdf",
                        content_type="application/pdf",
                        data=b"%PDF-1.4 p4-03 prep fixture",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    assert operation.status == SOURCE_PREP_STATUS_QUEUED

                    parser = DoclingDocumentParser(
                        convert=lambda *_args: {
                            "texts": [{"label": "text", "text": "Worker body"}],
                            "body": {"children": [{"$ref": "#/texts/0"}]},
                        }
                    )
                    worker_a = SourcePreparationWorker(settings_a, parsers={PARSER_DOCLING: parser})
                    assert worker_a.run_once(db) is True
                    db.refresh(source)
                    db.refresh(operation)
                    assert source.state == SOURCE_STATE_PREPARED
                    assert operation.status == SOURCE_PREP_STATUS_SUCCEEDED
                    assert operation.lease_owner is None
                    blocks = list(
                        db.scalars(
                            select(SourceBlock)
                            .where(SourceBlock.source_document_id == source.id)
                            .order_by(SourceBlock.source_order)
                        )
                    )
                    assert [block.canonical_markdown for block in blocks] == ["Worker body"]

                    # Second upload for lease/generation fence cases.
                    source_b, operation_b = upload_source_bytes(
                        db,
                        settings=settings_a,
                        domain_id=domain.id,
                        filename="manual-b.pdf",
                        content_type="application/pdf",
                        data=b"%PDF-1.4 p4-03 second fixture",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    now = utc_now()
                    operation_b.status = SOURCE_PREP_STATUS_RUNNING
                    operation_b.lease_owner = "prep-worker-a"
                    operation_b.lease_expires_at = now - timedelta(seconds=1)
                    operation_b.started_at = now - timedelta(seconds=10)
                    operation_b.updated_at = now
                    db.commit()

                    settings_b = _settings(database_url_text, tmp_path, worker_id="prep-worker-b")
                    worker_b = SourcePreparationWorker(settings_b, parsers={PARSER_DOCLING: parser})
                    claimed = worker_b._claim_next_operation(db)
                    assert claimed is not None
                    assert claimed.id == operation_b.id
                    assert claimed.lease_owner == "prep-worker-b"

                    # Expired former owner cannot publish after reclaim.
                    stale = publish_prepared_source(
                        db,
                        settings_a,
                        operation_b.id,
                        _sample_prepared(source_b.id),
                        lease_owner="prep-worker-a",
                    )
                    assert stale is False
                    db.refresh(source_b)
                    assert source_b.state == SOURCE_STATE_PENDING
                    assert (
                        db.scalar(select(SourceBlock).where(SourceBlock.source_document_id == source_b.id)) is None
                    )

                    published = publish_prepared_source(
                        db,
                        settings_b,
                        operation_b.id,
                        _sample_prepared(source_b.id),
                        lease_owner="prep-worker-b",
                    )
                    assert published is True
                    db.refresh(source_b)
                    db.refresh(operation_b)
                    assert source_b.state == SOURCE_STATE_PREPARED
                    assert operation_b.status == SOURCE_PREP_STATUS_SUCCEEDED
                    images = list(db.scalars(select(SourceImage).where(SourceImage.source_document_id == source_b.id)))
                    assert len(images) == 1
                    assert images[0].object_key.startswith("obj_")
                    storage = storage_from_settings(settings_b)
                    assert storage.store.get(images[0].object_key).startswith(b"\x89PNG")

                    # Generation fence: late gen-1 publish is a no-op.
                    source_c, operation_c = upload_source_bytes(
                        db,
                        settings=settings_b,
                        domain_id=domain.id,
                        filename="manual-c.pdf",
                        content_type="application/pdf",
                        data=b"%PDF-1.4 p4-03 third fixture",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    operation_c.status = SOURCE_PREP_STATUS_RUNNING
                    operation_c.lease_owner = "prep-worker-b"
                    operation_c.lease_expires_at = utc_now() + timedelta(seconds=30)
                    operation_c.preparation_generation_at_start = 1
                    source_c.preparation_generation = 2
                    db.commit()
                    late = publish_prepared_source(
                        db,
                        settings_b,
                        operation_c.id,
                        _sample_prepared(source_c.id),
                        lease_owner="prep-worker-b",
                    )
                    assert late is False
                    db.refresh(source_c)
                    assert source_c.state == SOURCE_STATE_PENDING

                    # CAS fence: reclaim after soft checks / during image staging must no-op.
                    source_d, operation_d = upload_source_bytes(
                        db,
                        settings=settings_b,
                        domain_id=domain.id,
                        filename="manual-d.pdf",
                        content_type="application/pdf",
                        data=b"%PDF-1.4 p4-03 fourth fixture",
                        requested_by_user=admin,
                        audit_context=audit,
                    )
                    operation_d.status = SOURCE_PREP_STATUS_RUNNING
                    operation_d.lease_owner = "prep-worker-a"
                    operation_d.lease_expires_at = utc_now() + timedelta(seconds=30)
                    operation_d.started_at = utc_now()
                    db.commit()

                    storage = storage_from_settings(settings_a)
                    original_write = storage.write_image

                    def reclaim_then_write(data: bytes, *, content_type: str | None = None) -> str:
                        with session_factory() as race_db:
                            raced = race_db.get(SourcePreparationOperation, operation_d.id)
                            assert raced is not None
                            raced.lease_owner = "prep-worker-b"
                            raced.lease_expires_at = utc_now() + timedelta(seconds=30)
                            raced.updated_at = utc_now()
                            race_db.commit()
                        return original_write(data, content_type=content_type)

                    storage.write_image = reclaim_then_write  # type: ignore[method-assign]
                    import context_engine.services.sources as sources_mod

                    original_storage_factory = sources_mod.storage_from_settings
                    sources_mod.storage_from_settings = lambda _settings: storage  # type: ignore[assignment]
                    try:
                        cas_denied = publish_prepared_source(
                            db,
                            settings_a,
                            operation_d.id,
                            _sample_prepared(source_d.id),
                            lease_owner="prep-worker-a",
                        )
                    finally:
                        sources_mod.storage_from_settings = original_storage_factory
                    assert cas_denied is False
                    db.expire_all()
                    db.refresh(source_d)
                    db.refresh(operation_d)
                    assert source_d.state == SOURCE_STATE_PENDING
                    assert operation_d.status == SOURCE_PREP_STATUS_RUNNING
                    assert operation_d.lease_owner == "prep-worker-b"
                    assert (
                        db.scalar(select(SourceBlock).where(SourceBlock.source_document_id == source_d.id)) is None
                    )
                finally:
                    db.close()
            finally:
                engine.dispose()
    finally:
        admin_engine.dispose()
