from __future__ import annotations

import json
import logging
import re
import secrets
import shutil
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from context_engine.adapters.object_storage import (
    ObjectStorage,
    ObjectStorageError,
    new_object_key,
    object_store_from_root,
)
from context_engine.adapters.parsers import (
    DocumentParser,
    ParserAdapterError,
    ParserRequest,
    PreparedSource,
    default_parser_registry,
    validate_prepared_source,
)
from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    AUDIT_EVENT_SOURCE_DELETED,
    AUDIT_EVENT_SOURCE_PREPARATION_CANCELLED,
    AUDIT_EVENT_SOURCE_PREPARATION_RETRIED,
    AUDIT_EVENT_SOURCE_UPLOADED,
    DOMAIN_STATE_DELETING,
    PARSER_REDUCTO,
    PROVIDER_REDUCTO,
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_CANCELLING,
    SOURCE_INDEX_STATE_CANCELLED,
    SOURCE_INDEX_STATE_FAILED,
    SOURCE_INDEX_STATE_NOT_REQUESTED,
    SOURCE_INDEX_STATE_QUEUED,
    SOURCE_INDEX_STATE_READY,
    SOURCE_INDEX_STATE_SUBMITTING,
    SOURCE_PREP_ACTIVE_STATUSES,
    SOURCE_PREP_OPERATION_PREPARE,
    SOURCE_PREP_STATUS_CANCELLED,
    SOURCE_PREP_STATUS_FAILED,
    SOURCE_PREP_STATUS_QUEUED,
    SOURCE_PREP_STATUS_RUNNING,
    SOURCE_PREP_STATUS_SUCCEEDED,
    SOURCE_STATE_DELETING,
    SOURCE_STATE_PENDING,
    SOURCE_STATE_PREPARED,
    Domain,
    ProviderConfig,
    SourceBlock,
    SourceDocument,
    SourceImage,
    SourcePreparationOperation,
    User,
)
from context_engine.services.audit import AuditContext, AuditService
from context_engine.services.auth import iso_utc
from context_engine.services.indexing import SourceIndexError, cleanup_index_before_source_delete, queue_source_index_after_publish
from context_engine.services.runtime_config import SecretCrypto, ensure_runtime_settings, is_provider_configured
from context_engine.services.source_upload import (
    UploadValidationError,
    validate_upload_bytes,
)
from context_engine.services.structured_logging import safe_log

logger = logging.getLogger(__name__)

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")


class SourceError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class SourceStorageError(Exception):
    pass


def new_document_public_ref() -> str:
    return f"doc_{secrets.token_urlsafe(24)}"


class SourceStorage:
    """Source-facing storage facade over the governed object-store port.

    Originals and derived image bytes use opaque object keys. A legacy
    filesystem layout under domains/... remains only for pre-P4 cleanup.
    """

    def __init__(self, root: str, store: ObjectStorage | None = None) -> None:
        self._root = Path(root).resolve()
        self._store: ObjectStorage = store or object_store_from_root(self._root)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def store(self) -> ObjectStorage:
        return self._store

    def _safe_path(self, *parts: str) -> Path:
        candidate = self._root.joinpath(*parts).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise SourceStorageError("Source storage path escaped root.")
        return candidate

    def source_dir(self, domain_id: str, source_id: str) -> Path:
        return self._safe_path("domains", domain_id, "sources", source_id)

    def put_original(self, data: bytes, *, content_type: str | None = None) -> str:
        try:
            return self._store.put(data, content_type=content_type).key
        except ObjectStorageError as exc:
            raise SourceStorageError("Source original could not be stored.") from exc

    def read_original(self, source: SourceDocument) -> bytes:
        if source.original_object_key:
            try:
                return self._store.get(source.original_object_key)
            except ObjectStorageError as exc:
                raise SourceStorageError("Source original unavailable.") from exc
        # Legacy path fallback for pre-P4-01 rows still under domain layout.
        try:
            return (self.source_dir(source.domain_id, source.id) / "original").read_bytes()
        except OSError as exc:
            raise SourceStorageError("Source original unavailable.") from exc

    def write_image(self, data: bytes, *, content_type: str | None = None) -> str:
        try:
            return self._store.put(data, content_type=content_type).key
        except ObjectStorageError as exc:
            raise SourceStorageError("Source image could not be stored.") from exc

    def delete_object_keys(self, object_keys: list[str]) -> None:
        for key in object_keys:
            if not key:
                continue
            try:
                self._store.delete(key)
            except ObjectStorageError as exc:
                raise SourceStorageError("Source files could not be removed.") from exc

    def delete_source_files(
        self,
        domain_id: str,
        source_id: str,
        *,
        original_object_key: str | None = None,
        image_object_keys: list[str] | None = None,
    ) -> None:
        keys = [key for key in [original_object_key, *(image_object_keys or [])] if key]
        self.delete_object_keys(keys)
        source_dir = self.source_dir(domain_id, source_id)
        try:
            if source_dir.exists():
                shutil.rmtree(source_dir)
            domain_sources = self._safe_path("domains", domain_id, "sources")
            if domain_sources.exists() and not any(domain_sources.iterdir()):
                domain_sources.rmdir()
            domain_root = self._safe_path("domains", domain_id)
            if domain_root.exists() and not any(domain_root.iterdir()):
                domain_root.rmdir()
        except OSError as exc:
            raise SourceStorageError("Source files could not be removed.") from exc


def storage_from_settings(settings: Settings) -> SourceStorage:
    return SourceStorage(settings.source_storage_root)


def sanitize_original_filename(filename: str | None) -> str:
    name = Path(filename or "source-document").name.replace("\\", "_").replace("/", "_").strip()
    name = _SAFE_FILENAME_RE.sub("_", name)
    if not name or name in {".", ".."}:
        name = "source-document"
    return name[:255]


def _domain_or_404(db: Session, domain_id: str) -> Domain:
    domain = db.get(Domain, domain_id)
    if domain is None:
        raise SourceError(404, "domain_not_found", "Domain not found.")
    if domain.state == DOMAIN_STATE_DELETING:
        raise SourceError(409, "domain_state_conflict", "Domain lifecycle state does not allow this operation.")
    return domain


def _source_or_404(db: Session, domain_id: str, source_id: str) -> SourceDocument:
    source = db.get(SourceDocument, source_id)
    if source is None or source.domain_id != domain_id:
        raise SourceError(404, "source_not_found", "Source not found.")
    return source


def _active_operation(db: Session, source_id: str) -> SourcePreparationOperation | None:
    return db.scalar(
        select(SourcePreparationOperation)
        .where(
            SourcePreparationOperation.source_document_id == source_id,
            SourcePreparationOperation.status.in_(SOURCE_PREP_ACTIVE_STATUSES),
        )
        .order_by(SourcePreparationOperation.created_at.desc(), SourcePreparationOperation.id)
    )


def _new_prepare_operation(
    *,
    source: SourceDocument,
    requested_by_user: User | None,
    request_id: str | None = None,
    message: str,
) -> SourcePreparationOperation:
    now = utc_now()
    return SourcePreparationOperation(
        id=str(uuid.uuid4()),
        source_document_id=source.id,
        domain_id=source.domain_id,
        operation_type=SOURCE_PREP_OPERATION_PREPARE,
        status=SOURCE_PREP_STATUS_QUEUED,
        preparation_generation_at_start=source.preparation_generation,
        requested_by_user_id=requested_by_user.id if requested_by_user is not None else None,
        request_id=request_id,
        message=message,
        created_at=now,
        updated_at=now,
    )


def upload_source_bytes(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    requested_by_user: User,
    audit_context: AuditContext | None = None,
) -> tuple[SourceDocument, SourcePreparationOperation]:
    domain = _domain_or_404(db, domain_id)
    try:
        validated = validate_upload_bytes(data, filename=filename, declared_content_type=content_type)
    except UploadValidationError as exc:
        raise SourceError(exc.status_code, exc.code, exc.message) from exc

    duplicate = db.scalar(
        select(SourceDocument.id).where(
            SourceDocument.domain_id == domain.id,
            SourceDocument.original_sha256 == validated.sha256,
        )
    )
    if duplicate is not None:
        raise SourceError(409, "duplicate_source", "Source already exists in this domain.")

    # Freeze active parser kind at upload; retries must not rewrite this field.
    frozen_parser_kind = ensure_runtime_settings(db).active_parser_kind
    source_id = str(uuid.uuid4())
    object_key = new_object_key()
    storage = storage_from_settings(settings)
    object_written = False
    now = utc_now()
    source = SourceDocument(
        id=source_id,
        public_ref=new_document_public_ref(),
        domain_id=domain.id,
        original_filename=sanitize_original_filename(filename),
        content_type=validated.content_type,
        original_sha256=validated.sha256,
        original_size_bytes=validated.size_bytes,
        original_object_key=object_key,
        state=SOURCE_STATE_PENDING,
        parser_kind=frozen_parser_kind,
        preparation_generation=1,
        version=1,
        created_by_user_id=requested_by_user.id,
        created_at=now,
        updated_at=now,
    )
    operation = _new_prepare_operation(
        source=source,
        requested_by_user=requested_by_user,
        request_id=audit_context.request_id if audit_context is not None else None,
        message="Preparation queued.",
    )
    db.add(source)
    db.add(operation)
    try:
        db.flush()
        if audit_context is not None:
            AuditService(db).record(
                AUDIT_EVENT_SOURCE_UPLOADED,
                context=audit_context,
                target_kind="source_document",
                target_id=source.id,
                metadata={
                    "sourceState": source.state,
                    "operationType": operation.operation_type,
                    "operationStatus": operation.status,
                },
            )
        storage.store.put_key(object_key, validated.data, content_type=validated.content_type)
        object_written = True
        db.commit()
        db.refresh(source)
        db.refresh(operation)
        return source, operation
    except IntegrityError as exc:
        db.rollback()
        if object_written:
            storage.delete_source_files(domain.id, source_id, original_object_key=object_key)
        raise SourceError(409, "duplicate_source", "Source already exists in this domain.") from exc
    except (OSError, SourceStorageError, ObjectStorageError) as exc:
        db.rollback()
        if object_written:
            storage.delete_source_files(domain.id, source_id, original_object_key=object_key)
        raise SourceError(500, "dependency_unavailable", "Source storage unavailable.") from exc


def _public_index_state(source: SourceDocument) -> str:
    if source.state == SOURCE_STATE_DELETING:
        return "deleting"
    mapping = {
        SOURCE_INDEX_STATE_NOT_REQUESTED: "not_requested",
        SOURCE_INDEX_STATE_QUEUED: "queued",
        SOURCE_INDEX_STATE_SUBMITTING: "processing",
        SOURCE_INDEX_STATE_ACCEPTED: "processing",
        SOURCE_INDEX_STATE_READY: "ready",
        SOURCE_INDEX_STATE_FAILED: "failed",
        SOURCE_INDEX_STATE_CANCELLING: "deleting",
        SOURCE_INDEX_STATE_CANCELLED: "cancelled",
    }
    return mapping.get(source.index_state, "failed")


def _source_allowed_actions(source: SourceDocument, active: SourcePreparationOperation | None) -> list[dict[str, Any]]:
    busy = active is not None
    deleting = source.state == SOURCE_STATE_DELETING

    def action(name: str, enabled: bool, reason: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": name, "enabled": enabled}
        if not enabled and reason is not None:
            payload["reasonCode"] = reason
        return payload

    if deleting:
        reason = "source_state_conflict"
        return [
            action("retry", False, reason),
            action("cancel", False, reason),
            action("delete", False, reason),
        ]
    if busy:
        return [
            action("retry", False, "source_operation_in_progress"),
            action("cancel", True),
            action("delete", False, "source_operation_in_progress"),
        ]
    return [
        action("retry", source.state == SOURCE_STATE_PENDING, "source_state_conflict"),
        action("cancel", False, "source_operation_not_active"),
        action("delete", True),
    ]


def safe_source(db: Session, source: SourceDocument) -> dict[str, Any]:
    active = _active_operation(db, source.id)
    return {
        "id": source.id,
        "documentRef": source.public_ref,
        "domainId": source.domain_id,
        "displayName": source.original_filename,
        "contentType": source.content_type,
        "sizeBytes": source.original_size_bytes,
        "state": source.state,
        "parserKind": source.parser_kind,
        "indexState": _public_index_state(source),
        "activeOperationId": active.id if active is not None else None,
        "createdAt": iso_utc(source.created_at),
        "updatedAt": iso_utc(source.updated_at),
        "version": source.version,
        "allowedActions": _source_allowed_actions(source, active),
    }


def safe_source_operation(operation: SourcePreparationOperation) -> dict[str, Any]:
    return {
        "id": operation.id,
        "operationType": operation.operation_type,
        "status": operation.status,
        "message": operation.message,
        "errorCode": operation.error_code,
        "errorMessage": operation.error_message,
        "startedAt": iso_utc(operation.started_at) if operation.started_at is not None else None,
        "finishedAt": iso_utc(operation.finished_at) if operation.finished_at is not None else None,
        "createdAt": iso_utc(operation.created_at),
    }


def list_sources(db: Session, domain_id: str) -> list[dict[str, Any]]:
    _domain_or_404(db, domain_id)
    sources = list(
        db.scalars(
            select(SourceDocument)
            .where(SourceDocument.domain_id == domain_id)
            .order_by(SourceDocument.created_at.desc(), SourceDocument.id)
        )
    )
    return [safe_source(db, source) for source in sources]


def source_detail(db: Session, domain_id: str, source_id: str) -> dict[str, Any]:
    _domain_or_404(db, domain_id)
    return safe_source(db, _source_or_404(db, domain_id, source_id))


def source_operations(db: Session, domain_id: str, source_id: str) -> list[dict[str, Any]]:
    _domain_or_404(db, domain_id)
    _source_or_404(db, domain_id, source_id)
    operations = list(
        db.scalars(
            select(SourcePreparationOperation)
            .where(SourcePreparationOperation.source_document_id == source_id)
            .order_by(SourcePreparationOperation.created_at.desc(), SourcePreparationOperation.id)
        )
    )
    return [safe_source_operation(operation) for operation in operations]


def _outline_title(block: SourceBlock) -> str | None:
    try:
        section_path = json.loads(block.section_path or "[]")
    except ValueError:
        section_path = []
    if section_path:
        return str(section_path[-1])[:120]
    if block.heading_level is not None:
        first_line = block.canonical_markdown.splitlines()[0].strip().lstrip("#").strip()
        return first_line[:120] or None
    return None


def source_outline(db: Session, domain_id: str, source_id: str) -> list[dict[str, Any]]:
    _domain_or_404(db, domain_id)
    _source_or_404(db, domain_id, source_id)
    blocks = list(
        db.scalars(
            select(SourceBlock)
            .where(SourceBlock.source_document_id == source_id)
            .order_by(SourceBlock.source_order)
        )
    )
    items: list[dict[str, Any]] = []
    for block in blocks:
        try:
            section_path = json.loads(block.section_path or "[]")
        except ValueError:
            section_path = []
        items.append(
            {
                "sourceOrder": block.source_order,
                "kind": block.kind,
                "headingLevel": block.heading_level,
                "title": _outline_title(block),
                "pageStart": block.page_start,
                "pageEnd": block.page_end,
                "sectionPath": section_path,
            }
        )
    return items


def retry_source(
    db: Session,
    *,
    domain_id: str,
    source_id: str,
    requested_by_user: User,
    audit_context: AuditContext | None = None,
) -> SourcePreparationOperation:
    _domain_or_404(db, domain_id)
    source = _source_or_404(db, domain_id, source_id)
    if source.state != SOURCE_STATE_PENDING:
        raise SourceError(409, "source_state_conflict", "Source state does not allow this operation.")
    if _active_operation(db, source.id) is not None:
        raise SourceError(409, "operation_conflict", "Source preparation is already in progress.")
    # Parser kind remains the value frozen at upload; do not re-read runtime defaults.
    frozen_parser_kind = source.parser_kind
    source.preparation_generation += 1
    source.updated_at = utc_now()
    source.parser_kind = frozen_parser_kind
    operation = _new_prepare_operation(
        source=source,
        requested_by_user=requested_by_user,
        request_id=audit_context.request_id if audit_context is not None else None,
        message="Preparation queued.",
    )
    db.add(operation)
    if audit_context is not None:
        AuditService(db).record(
            AUDIT_EVENT_SOURCE_PREPARATION_RETRIED,
            context=audit_context,
            target_kind="source_preparation_operation",
            target_id=operation.id,
            metadata={"operationType": operation.operation_type, "operationStatus": operation.status},
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SourceError(409, "operation_conflict", "Source preparation is already in progress.") from exc
    db.refresh(operation)
    return operation


def cancel_source(
    db: Session,
    *,
    domain_id: str,
    source_id: str,
    audit_context: AuditContext | None = None,
) -> SourcePreparationOperation:
    _domain_or_404(db, domain_id)
    source = _source_or_404(db, domain_id, source_id)
    if source.state == SOURCE_STATE_PREPARED:
        raise SourceError(409, "source_state_conflict", "Source state does not allow this operation.")
    operation = _active_operation(db, source.id)
    if operation is None:
        raise SourceError(409, "source_state_conflict", "Source state does not allow this operation.")
    now = utc_now()
    source.preparation_generation += 1
    source.updated_at = now
    operation.status = SOURCE_PREP_STATUS_CANCELLED
    operation.message = "Preparation cancelled."
    operation.error_code = None
    operation.error_message = None
    operation.lease_owner = None
    operation.lease_expires_at = None
    operation.finished_at = now
    operation.updated_at = now
    if audit_context is not None:
        AuditService(db).record(
            AUDIT_EVENT_SOURCE_PREPARATION_CANCELLED,
            context=audit_context,
            target_kind="source_preparation_operation",
            target_id=operation.id,
            metadata={"operationType": operation.operation_type, "operationStatus": operation.status},
        )
    db.commit()
    db.refresh(operation)
    return operation


def _cancel_active_operation_for_delete(db: Session, source: SourceDocument, now) -> None:
    operation = _active_operation(db, source.id)
    if operation is None:
        return
    operation.status = SOURCE_PREP_STATUS_CANCELLED
    operation.message = "Preparation cancelled."
    operation.error_code = None
    operation.error_message = None
    operation.lease_owner = None
    operation.lease_expires_at = None
    operation.finished_at = now
    operation.updated_at = now


def delete_source(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    source_id: str,
    audit_context: AuditContext | None = None,
) -> None:
    _domain_or_404(db, domain_id)
    source = _source_or_404(db, domain_id, source_id)
    from context_engine.services.chat_turns import redact_turns_for_source

    redact_turns_for_source(db, source.id, audit_context=audit_context)
    now = utc_now()
    source.state = SOURCE_STATE_DELETING
    source.preparation_generation += 1
    source.updated_at = now
    _cancel_active_operation_for_delete(db, source, now)
    cleanup_index_before_source_delete(db, settings=settings, source=source)
    image_object_keys = [
        image.object_key
        for image in db.scalars(select(SourceImage).where(SourceImage.source_document_id == source.id))
        if image.object_key
    ]
    storage_from_settings(settings).delete_source_files(
        domain_id,
        source_id,
        original_object_key=source.original_object_key,
        image_object_keys=image_object_keys,
    )
    db.delete(source)
    if audit_context is not None:
        AuditService(db).record(
            AUDIT_EVENT_SOURCE_DELETED,
            context=audit_context,
            target_kind="source_document",
            target_id=source_id,
            metadata={"sourceState": SOURCE_STATE_DELETING, "indexState": source.index_state},
        )
    db.commit()


def purge_domain_sources_local(
    db: Session,
    settings: Settings,
    domain_id: str,
    audit_context: AuditContext | None = None,
) -> None:
    storage = storage_from_settings(settings)
    sources = list(db.scalars(select(SourceDocument).where(SourceDocument.domain_id == domain_id)))
    from context_engine.services.chat_turns import redact_turns_for_source

    now = utc_now()
    for source in sources:
        redact_turns_for_source(db, source.id, audit_context=audit_context)
        source.state = SOURCE_STATE_DELETING
        source.preparation_generation += 1
        source.updated_at = now
        _cancel_active_operation_for_delete(db, source, now)
        cleanup_index_before_source_delete(db, settings=settings, source=source)
        image_object_keys = [
            image.object_key
            for image in db.scalars(select(SourceImage).where(SourceImage.source_document_id == source.id))
            if image.object_key
        ]
        storage.delete_source_files(
            source.domain_id,
            source.id,
            original_object_key=source.original_object_key,
            image_object_keys=image_object_keys,
        )
        db.delete(source)
    db.flush()


def _lease_heartbeat_seconds(lease_seconds: int) -> int:
    return max(1, lease_seconds // 3)


def _prep_lease_current(
    operation: SourcePreparationOperation,
    *,
    owner: str,
    now=None,
) -> bool:
    current = now or utc_now()
    if operation.status != SOURCE_PREP_STATUS_RUNNING:
        return False
    if operation.lease_owner != owner:
        return False
    if operation.lease_expires_at is None or operation.lease_expires_at < current:
        return False
    return True


def _heartbeat_prep_lease(
    db: Session,
    operation: SourcePreparationOperation,
    *,
    owner: str,
    lease_seconds: int,
    now=None,
) -> bool:
    current = now or utc_now()
    db.refresh(operation)
    if not _prep_lease_current(operation, owner=owner, now=current):
        return False
    operation.lease_expires_at = current + timedelta(seconds=lease_seconds)
    operation.updated_at = current
    db.commit()
    db.refresh(operation)
    return True


def _fail_operation(db: Session, operation: SourcePreparationOperation, code: str, message: str) -> None:
    now = utc_now()
    operation.status = SOURCE_PREP_STATUS_FAILED
    operation.message = message
    operation.error_code = code
    operation.error_message = message
    operation.lease_owner = None
    operation.lease_expires_at = None
    operation.finished_at = now
    operation.updated_at = now
    db.commit()
    safe_log(
        logger,
        "source_preparation_worker.failed",
        request_id=operation.request_id,
        domain_id=operation.domain_id,
        source_id=operation.source_document_id,
        operation_id=operation.id,
        safe_error_code=code,
        outcome="failed",
    )


def _resolve_parser_credential(db: Session, settings: Settings, parser_kind: str) -> str | None:
    if parser_kind != PARSER_REDUCTO:
        return None
    provider = db.get(ProviderConfig, PROVIDER_REDUCTO)
    if provider is None or not is_provider_configured(provider):
        raise ParserAdapterError("parser_not_ready", "Parser is not configured.", 409)
    if not provider.credential_ciphertext:
        raise ParserAdapterError("parser_not_ready", "Parser is not configured.", 409)
    return SecretCrypto.from_settings(settings).decrypt_secret(provider.credential_ciphertext)


def publish_prepared_source(
    db: Session,
    settings: Settings,
    operation_id: str,
    prepared: PreparedSource,
    *,
    lease_owner: str | None = None,
) -> bool:
    validate_prepared_source(prepared)
    operation = db.get(SourcePreparationOperation, operation_id)
    if operation is None:
        return False
    owner = lease_owner or settings.source_prep_worker_id
    now = utc_now()
    if not _prep_lease_current(operation, owner=owner, now=now):
        return False
    source = db.get(SourceDocument, operation.source_document_id)
    if source is None:
        return False
    if source.state != SOURCE_STATE_PENDING or source.preparation_generation != operation.preparation_generation_at_start:
        return False
    if source.id != prepared.source_document_id or source.parser_kind != prepared.parser_kind:
        raise ParserAdapterError("source_preparation_invalid", "Prepared source did not pass validation.", 422)

    previous_image_keys = [
        image.object_key
        for image in db.scalars(select(SourceImage).where(SourceImage.source_document_id == source.id))
        if image.object_key
    ]
    storage = storage_from_settings(settings)
    db.execute(delete(SourceImage).where(SourceImage.source_document_id == source.id))
    db.execute(delete(SourceBlock).where(SourceBlock.source_document_id == source.id))
    blocks_by_order: dict[int, SourceBlock] = {}
    for prepared_block in sorted(prepared.blocks, key=lambda block: block.source_order):
        block = SourceBlock(
            id=str(uuid.uuid4()),
            source_document_id=source.id,
            domain_id=source.domain_id,
            source_order=prepared_block.source_order,
            kind=prepared_block.kind,
            canonical_markdown=prepared_block.canonical_markdown,
            heading_level=prepared_block.heading_level,
            page_start=prepared_block.page_start,
            page_end=prepared_block.page_end,
            section_path=json.dumps(prepared_block.section_path),
            created_at=now,
        )
        db.add(block)
        blocks_by_order[prepared_block.source_order] = block
    db.flush()
    written_image_keys: list[str] = []
    try:
        for prepared_image in prepared.images:
            block = blocks_by_order[prepared_image.source_order]
            object_key = storage.write_image(prepared_image.bytes_data, content_type=prepared_image.mime_type)
            written_image_keys.append(object_key)
            image = SourceImage(
                id=str(uuid.uuid4()),
                source_document_id=source.id,
                source_block_id=block.id,
                object_key=object_key,
                content_hash=prepared_image.content_hash,
                mime_type=prepared_image.mime_type,
                alt_text=prepared_image.alt_text,
                page_number=prepared_image.page_number,
                created_at=now,
            )
            db.add(image)
        source.state = SOURCE_STATE_PREPARED
        source.updated_at = now
        queue_source_index_after_publish(db, source)
        operation.status = SOURCE_PREP_STATUS_SUCCEEDED
        operation.message = "Preparation succeeded."
        operation.error_code = None
        operation.error_message = None
        operation.lease_owner = None
        operation.lease_expires_at = None
        operation.finished_at = now
        operation.updated_at = now
        db.commit()
    except Exception:
        db.rollback()
        if written_image_keys:
            storage.delete_object_keys(written_image_keys)
        raise
    if previous_image_keys:
        try:
            storage.delete_object_keys(previous_image_keys)
        except SourceStorageError:
            safe_log(
                logger,
                "source_preparation_worker.image_cleanup_deferred",
                request_id=operation.request_id,
                domain_id=operation.domain_id,
                source_id=operation.source_document_id,
                operation_id=operation.id,
                outcome="failed",
            )
    return True


class SourcePreparationWorker:
    def __init__(self, settings: Settings, parsers: dict[str, DocumentParser] | None = None) -> None:
        self._settings = settings
        self._parsers = parsers or default_parser_registry(
            reducto_timeout_seconds=float(settings.source_parser_timeout_seconds)
        )

    def run_once(self, db: Session) -> bool:
        operation = self._claim_next_operation(db)
        if operation is None:
            return False
        source = db.get(SourceDocument, operation.source_document_id)
        if source is None:
            return True
        owner = self._settings.source_prep_worker_id
        lease_seconds = self._settings.source_prep_lease_seconds
        try:
            if not _heartbeat_prep_lease(db, operation, owner=owner, lease_seconds=lease_seconds):
                return True
            original = storage_from_settings(self._settings).read_original(source)
            credential = _resolve_parser_credential(db, self._settings, source.parser_kind)
            parser = self._parsers.get(source.parser_kind)
            if parser is None:
                raise ParserAdapterError("parser_not_ready", "Parser is not configured.", 409)
            prepared = parser.parse(
                ParserRequest(
                    source_document_id=source.id,
                    parser_kind=source.parser_kind,
                    original_bytes=original,
                    content_type=source.content_type,
                    filename=source.original_filename,
                    credential=credential,
                )
            )
            if not _heartbeat_prep_lease(db, operation, owner=owner, lease_seconds=lease_seconds):
                return True
            publish_prepared_source(
                db,
                self._settings,
                operation.id,
                prepared,
                lease_owner=owner,
            )
        except (ParserAdapterError, SourceIndexError) as exc:
            db.rollback()
            current = db.get(SourcePreparationOperation, operation.id)
            if current is not None and _prep_lease_current(current, owner=owner):
                _fail_operation(db, current, exc.code, exc.message)
        except SourceStorageError:
            db.rollback()
            current = db.get(SourcePreparationOperation, operation.id)
            if current is not None and _prep_lease_current(current, owner=owner):
                _fail_operation(db, current, "source_preparation_invalid", "Prepared source did not pass validation.")
        return True

    def _claim_next_operation(self, db: Session) -> SourcePreparationOperation | None:
        now = utc_now()
        operation = db.scalar(
            select(SourcePreparationOperation)
            .where(
                SourcePreparationOperation.operation_type == SOURCE_PREP_OPERATION_PREPARE,
                or_(
                    SourcePreparationOperation.status == SOURCE_PREP_STATUS_QUEUED,
                    (
                        (SourcePreparationOperation.status == SOURCE_PREP_STATUS_RUNNING)
                        & (SourcePreparationOperation.lease_expires_at.is_not(None))
                        & (SourcePreparationOperation.lease_expires_at < now)
                    ),
                ),
            )
            .order_by(SourcePreparationOperation.created_at, SourcePreparationOperation.id)
            # Row lock prevents double-claim across worker processes on Postgres;
            # SQLAlchemy's SQLite dialect ignores FOR UPDATE, so dev/tests are unaffected.
            .with_for_update(skip_locked=True)
        )
        if operation is None:
            return None
        operation.status = SOURCE_PREP_STATUS_RUNNING
        operation.lease_owner = self._settings.source_prep_worker_id
        operation.lease_expires_at = now + timedelta(seconds=self._settings.source_prep_lease_seconds)
        operation.started_at = operation.started_at or now
        operation.message = "Preparing source."
        operation.updated_at = now
        db.commit()
        db.refresh(operation)
        safe_log(
            logger,
            "source_preparation_worker.claimed",
            request_id=operation.request_id,
            domain_id=operation.domain_id,
            source_id=operation.source_document_id,
            operation_id=operation.id,
            outcome="succeeded",
        )
        return operation
