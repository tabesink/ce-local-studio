"""Governed preview queue, claim, render, and generation-fenced publication."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from context_engine.adapters.object_storage import ObjectStorageError
from context_engine.adapters.preview_renderer import PreviewRendererError, render_governed_preview
from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    SOURCE_PREVIEW_STATE_FAILED,
    SOURCE_PREVIEW_STATE_QUEUED,
    SOURCE_PREVIEW_STATE_READY,
    SOURCE_PREVIEW_STATE_RUNNING,
    SOURCE_STATE_PREPARED,
    SourceDocument,
)
from context_engine.services.structured_logging import safe_log

logger = logging.getLogger(__name__)


def _storage_from_settings(settings: Settings):
    from context_engine.services.sources import storage_from_settings

    return storage_from_settings(settings)


def queue_source_preview_after_publish(db: Session, source: SourceDocument) -> None:
    """Queue preview work for the current preparation generation (idempotent)."""
    if source.state != SOURCE_STATE_PREPARED:
        return
    now = utc_now()
    source.preview_state = SOURCE_PREVIEW_STATE_QUEUED
    source.preview_generation = int(source.preparation_generation)
    source.preview_error_code = None
    source.preview_error_message = None
    source.preview_lease_owner = None
    source.preview_lease_expires_at = None
    source.preview_updated_at = now
    # Keep prior ready metadata until a successful CAS publish replaces it.


def preview_is_ready(source: SourceDocument) -> bool:
    return (
        source.preview_state == SOURCE_PREVIEW_STATE_READY
        and source.preview_object_key is not None
        and int(source.preview_generation) == int(source.preparation_generation)
        and int(source.preview_version) >= 1
    )


def _lease_current(source: SourceDocument, *, owner: str, now=None) -> bool:
    current = now or utc_now()
    if source.preview_lease_owner != owner:
        return False
    return source.preview_lease_expires_at is not None and source.preview_lease_expires_at >= current


def _heartbeat(db: Session, source: SourceDocument, *, owner: str, lease_seconds: int) -> bool:
    now = utc_now()
    if not _lease_current(source, owner=owner, now=now):
        return False
    source.preview_lease_expires_at = now + timedelta(seconds=lease_seconds)
    source.preview_updated_at = now
    db.commit()
    db.refresh(source)
    return True


def _fail_preview(db: Session, source: SourceDocument, *, code: str, message: str, owner: str) -> None:
    if not _lease_current(source, owner=owner):
        return
    source.preview_state = SOURCE_PREVIEW_STATE_FAILED
    source.preview_error_code = code
    source.preview_error_message = message
    source.preview_lease_owner = None
    source.preview_lease_expires_at = None
    source.preview_updated_at = utc_now()
    db.commit()


def _delete_keys(settings: Settings, keys: list[str]) -> None:
    from context_engine.services.sources import SourceStorageError

    storage = _storage_from_settings(settings)
    try:
        storage.delete_object_keys([key for key in keys if key])
    except SourceStorageError:
        safe_log(logger, "source_preview_worker.orphan_cleanup_deferred", outcome="failed")


def _cas_publish(
    db: Session,
    *,
    source_id: str,
    owner: str,
    preparation_generation: int,
    preview_object_key: str,
    preview_sha256: str,
    preview_size_bytes: int,
    preview_page_count: int,
    preview_renderer_version: str,
    preview_source_sha256: str,
    preview_page_map_object_key: str,
    preview_page_map_sha256: str,
    preview_reuses_original: bool,
) -> bool:
    now = utc_now()
    source = db.get(SourceDocument, source_id)
    if source is None:
        return False
    next_version = int(source.preview_version or 0) + 1
    result = db.execute(
        update(SourceDocument)
        .where(
            SourceDocument.id == source_id,
            SourceDocument.state == SOURCE_STATE_PREPARED,
            SourceDocument.preparation_generation == preparation_generation,
            SourceDocument.preview_generation == preparation_generation,
            SourceDocument.preview_state == SOURCE_PREVIEW_STATE_RUNNING,
            SourceDocument.preview_lease_owner == owner,
            SourceDocument.preview_lease_expires_at.is_not(None),
            SourceDocument.preview_lease_expires_at >= now,
        )
        .values(
            preview_state=SOURCE_PREVIEW_STATE_READY,
            preview_version=next_version,
            preview_object_key=preview_object_key,
            preview_sha256=preview_sha256,
            preview_size_bytes=preview_size_bytes,
            preview_page_count=preview_page_count,
            preview_renderer_version=preview_renderer_version,
            preview_source_sha256=preview_source_sha256,
            preview_page_map_object_key=preview_page_map_object_key,
            preview_page_map_sha256=preview_page_map_sha256,
            preview_reuses_original=preview_reuses_original,
            preview_error_code=None,
            preview_error_message=None,
            preview_lease_owner=None,
            preview_lease_expires_at=None,
            preview_ready_at=now,
            preview_updated_at=now,
        )
    )
    return int(result.rowcount or 0) == 1


class SourcePreviewWorker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run_once(self, db: Session) -> bool:
        source = self._claim_next(db)
        if source is None:
            return False

        owner = self._settings.source_preview_worker_id
        lease_seconds = self._settings.source_preview_lease_seconds
        timeout = float(self._settings.source_preview_timeout_seconds)
        generation = int(source.preview_generation)
        source_id = source.id
        previous_preview_key = source.preview_object_key
        previous_map_key = source.preview_page_map_object_key
        previous_reuses = bool(source.preview_reuses_original)

        from context_engine.services.sources import SourceStorageError

        storage = _storage_from_settings(self._settings)
        written_keys: list[str] = []
        try:
            if not _heartbeat(db, source, owner=owner, lease_seconds=lease_seconds):
                return True
            original_bytes = storage.read_original(source)
            if not _heartbeat(db, source, owner=owner, lease_seconds=lease_seconds):
                return True
            rendered = render_governed_preview(
                original_bytes,
                source.content_type,
                timeout_seconds=timeout,
                source_sha256=source.original_sha256,
            )
            if not _heartbeat(db, source, owner=owner, lease_seconds=lease_seconds):
                _delete_keys(self._settings, written_keys)
                return True

            page_map_bytes = json.dumps(rendered.page_map, separators=(",", ":"), sort_keys=True).encode("utf-8")
            page_map_sha = hashlib.sha256(page_map_bytes).hexdigest()
            map_key = storage.store.put(page_map_bytes, content_type="application/json").key
            written_keys.append(map_key)

            if rendered.reused_original_bytes:
                preview_key = source.original_object_key
                reuses = True
            else:
                preview_key = storage.store.put(rendered.pdf_bytes, content_type="application/pdf").key
                written_keys.append(preview_key)
                reuses = False

            if not _heartbeat(db, source, owner=owner, lease_seconds=lease_seconds):
                _delete_keys(self._settings, written_keys)
                return True

            published = _cas_publish(
                db,
                source_id=source_id,
                owner=owner,
                preparation_generation=generation,
                preview_object_key=preview_key,
                preview_sha256=rendered.checksum_sha256,
                preview_size_bytes=len(rendered.pdf_bytes),
                preview_page_count=rendered.page_count,
                preview_renderer_version=rendered.renderer_version,
                preview_source_sha256=rendered.source_sha256,
                preview_page_map_object_key=map_key,
                preview_page_map_sha256=page_map_sha,
                preview_reuses_original=reuses,
            )
            if not published:
                db.rollback()
                _delete_keys(self._settings, written_keys)
                safe_log(
                    logger,
                    "source_preview_worker.stale_publish",
                    source_id=source_id,
                    outcome="ignored",
                )
                return True
            db.commit()
            # Drop superseded derivatives (never delete reused original).
            stale: list[str] = []
            if previous_map_key and previous_map_key != map_key:
                stale.append(previous_map_key)
            if (
                previous_preview_key
                and previous_preview_key != preview_key
                and not previous_reuses
            ):
                stale.append(previous_preview_key)
            if stale:
                _delete_keys(self._settings, stale)
            safe_log(logger, "source_preview_worker.published", source_id=source_id, outcome="succeeded")
            return True
        except PreviewRendererError as exc:
            db.rollback()
            current = db.get(SourceDocument, source_id)
            if current is not None:
                _fail_preview(db, current, code=exc.code, message=exc.message, owner=owner)
            _delete_keys(self._settings, written_keys)
            return True
        except (ObjectStorageError, SourceStorageError, OSError):
            db.rollback()
            current = db.get(SourceDocument, source_id)
            if current is not None:
                _fail_preview(
                    db,
                    current,
                    code="preview_storage_failed",
                    message="Preview storage failed.",
                    owner=owner,
                )
            _delete_keys(self._settings, written_keys)
            return True
        except Exception:
            db.rollback()
            current = db.get(SourceDocument, source_id)
            if current is not None:
                _fail_preview(
                    db,
                    current,
                    code="preview_render_failed",
                    message="Preview rendering failed.",
                    owner=owner,
                )
            _delete_keys(self._settings, written_keys)
            raise

    def _claim_next(self, db: Session) -> SourceDocument | None:
        now = utc_now()
        source = db.scalar(
            select(SourceDocument)
            .where(
                SourceDocument.state == SOURCE_STATE_PREPARED,
                or_(
                    SourceDocument.preview_state == SOURCE_PREVIEW_STATE_QUEUED,
                    (
                        (SourceDocument.preview_state == SOURCE_PREVIEW_STATE_RUNNING)
                        & (SourceDocument.preview_lease_expires_at.is_not(None))
                        & (SourceDocument.preview_lease_expires_at < now)
                    ),
                ),
            )
            .order_by(SourceDocument.updated_at, SourceDocument.id)
            .with_for_update(skip_locked=True)
        )
        if source is None:
            return None
        if int(source.preview_generation) != int(source.preparation_generation):
            # Stale queue vs newer prep — re-queue for current generation.
            source.preview_generation = int(source.preparation_generation)
        source.preview_state = SOURCE_PREVIEW_STATE_RUNNING
        source.preview_lease_owner = self._settings.source_preview_worker_id
        source.preview_lease_expires_at = now + timedelta(seconds=self._settings.source_preview_lease_seconds)
        source.preview_updated_at = now
        db.commit()
        db.refresh(source)
        return source
