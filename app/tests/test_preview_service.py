"""P10-06 U3: preview queue, CAS publish, stale generation fence (sqlite)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from context_engine.config import Settings
from context_engine.db import Base
from context_engine.models import (
    SOURCE_PREVIEW_STATE_QUEUED,
    SOURCE_PREVIEW_STATE_READY,
    SOURCE_STATE_PREPARED,
    SourceDocument,
)
from context_engine.services.preview import (
    SourcePreviewWorker,
    preview_is_ready,
    queue_source_preview_after_publish,
)
from context_engine.services.sources import SourceStorage


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'preview.db'}",
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        session_cookie_secure=False,
        domain_runtime_controller_kind="local",
        domain_runtime_root=str(tmp_path / "domain-runtimes"),
        source_storage_root=str(tmp_path / "source-storage"),
        source_preview_worker_id="preview-worker-a",
        source_preview_lease_seconds=30,
        source_preview_timeout_seconds=10,
        lightrag_client_kind="local",
    )


def _session(settings: Settings) -> Session:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _prepared_source(db: Session, storage: SourceStorage, *, content_type: str, data: bytes) -> SourceDocument:
    key = storage.put_original(data, content_type=content_type)
    source = SourceDocument(
        id=str(uuid4()),
        public_ref=f"doc_{uuid4().hex[:16]}",
        domain_id="domain_manuals",
        original_filename="sample.bin",
        content_type=content_type,
        original_sha256="a" * 64,
        original_size_bytes=len(data),
        original_object_key=key,
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def test_queue_and_publish_pdf_passthrough(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _session(settings)
    storage = SourceStorage(settings.source_storage_root)
    pdf = b"%PDF-1.4 synthetic-preview-bytes-0123456789"
    source = _prepared_source(db, storage, content_type="application/pdf", data=pdf)

    queue_source_preview_after_publish(db, source)
    db.commit()
    db.refresh(source)
    assert source.preview_state == SOURCE_PREVIEW_STATE_QUEUED
    assert source.preview_generation == 1

    worker = SourcePreviewWorker(settings)
    assert worker.run_once(db) is True
    db.refresh(source)
    assert preview_is_ready(source)
    assert source.preview_state == SOURCE_PREVIEW_STATE_READY
    assert source.preview_version == 1
    assert source.preview_reuses_original is True
    assert source.preview_object_key == source.original_object_key
    assert source.preview_page_map_object_key
    assert storage.store.get(source.preview_page_map_object_key)


def test_markdown_publish_writes_derived_pdf(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _session(settings)
    storage = SourceStorage(settings.source_storage_root)
    md = (Path(__file__).parent / "fixtures/documents/sample_preview.md").read_bytes()
    source = _prepared_source(db, storage, content_type="text/markdown", data=md)
    queue_source_preview_after_publish(db, source)
    db.commit()

    assert SourcePreviewWorker(settings).run_once(db) is True
    db.refresh(source)
    assert preview_is_ready(source)
    assert source.preview_reuses_original is False
    assert source.preview_object_key != source.original_object_key
    assert storage.store.get(source.preview_object_key).startswith(b"%PDF-")


def test_stale_generation_cannot_publish(tmp_path: Path) -> None:
    from datetime import timedelta

    from context_engine.db import utc_now
    from context_engine.models import SOURCE_PREVIEW_STATE_RUNNING
    from context_engine.services.preview import _cas_publish

    settings = _settings(tmp_path)
    db = _session(settings)
    storage = SourceStorage(settings.source_storage_root)
    pdf = b"%PDF-1.4 synthetic-preview-bytes-0123456789"
    source = _prepared_source(db, storage, content_type="application/pdf", data=pdf)
    now = utc_now()
    source.preview_state = SOURCE_PREVIEW_STATE_RUNNING
    source.preview_generation = 1
    source.preview_lease_owner = settings.source_preview_worker_id
    source.preview_lease_expires_at = now + timedelta(seconds=30)
    source.preparation_generation = 2  # newer prep fences stale worker
    db.commit()

    published = _cas_publish(
        db,
        source_id=source.id,
        owner=settings.source_preview_worker_id,
        preparation_generation=1,
        preview_object_key=source.original_object_key,
        preview_sha256="b" * 64,
        preview_size_bytes=len(pdf),
        preview_page_count=1,
        preview_renderer_version="ce-preview-pdf-passthrough-v1",
        preview_source_sha256="a" * 64,
        preview_page_map_object_key="obj_map_stale",
        preview_page_map_sha256="c" * 64,
        preview_reuses_original=True,
    )
    assert published is False
    db.refresh(source)
    assert source.preview_state == SOURCE_PREVIEW_STATE_RUNNING
    assert not preview_is_ready(source)


def test_worker_build_includes_preview_slot() -> None:
    from context_engine.worker import build_workers, run_once_pass

    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        session_cookie_secure=False,
        domain_runtime_controller_kind="local",
        lightrag_client_kind="local",
    )
    workers = build_workers(settings)
    assert "preview" in workers
    assert run_once_pass.__code__.co_argcount >= 6
