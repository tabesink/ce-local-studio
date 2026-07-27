from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from context_engine.adapters.domain_runtime_controller import (
    CONTROLLER_OUTCOME_FAILED,
    CONTROLLER_OUTCOME_SUCCEEDED,
    CONTROLLER_OUTCOME_UNCERTAIN,
    DomainControllerError,
    DomainRuntimeController,
    LocalDomainRuntimeController,
    RuntimeControllerResult,
    RuntimeHealth,
    controller_from_settings,
)
from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    AUDIT_ACTOR_WORKER,
    AUDIT_EVENT_DOMAIN_CREATED,
    AUDIT_EVENT_DOMAIN_DELETE_FAILED,
    AUDIT_EVENT_DOMAIN_DELETE_QUEUED,
    AUDIT_EVENT_DOMAIN_DELETE_SUCCEEDED,
    AUDIT_EVENT_DOMAIN_STARTED,
    AUDIT_EVENT_DOMAIN_STOPPED,
    AUDIT_OUTCOME_FAILED,
    DOMAIN_OPERATION_ACTIVE_STATUSES,
    DOMAIN_OPERATION_CREATE,
    DOMAIN_OPERATION_DELETE,
    DOMAIN_OPERATION_START,
    DOMAIN_OPERATION_STATUS_CANCELLED,
    DOMAIN_OPERATION_STATUS_FAILED,
    DOMAIN_OPERATION_STATUS_QUEUED,
    DOMAIN_OPERATION_STATUS_RUNNING,
    DOMAIN_OPERATION_STATUS_SUCCEEDED,
    DOMAIN_OPERATION_STOP,
    DOMAIN_STATE_DELETING,
    DOMAIN_STATE_RUNNING,
    DOMAIN_STATE_STOPPED,
    Domain,
    DomainOperation,
    ModelProfile,
    SourceBlock,
    SourceDocument,
    User,
)
from context_engine.services.audit import AuditContext, AuditService, commit_protected_mutation
from context_engine.services.auth import iso_utc
from context_engine.services.structured_logging import safe_log
from context_engine.services.metrics import safe_increment

logger = logging.getLogger(__name__)

DOMAIN_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{1,62}$"
_DOMAIN_ID_RE = re.compile(DOMAIN_ID_PATTERN)

# Re-export adapter surface for existing service/test imports.
__all__ = [
    "DOMAIN_ID_PATTERN",
    "DomainControllerError",
    "DomainError",
    "DomainRuntimeController",
    "LocalDomainRuntimeController",
    "RuntimeControllerResult",
    "RuntimeHealth",
    "controller_from_settings",
]


class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _lease_heartbeat_seconds(lease_seconds: int) -> int:
    return max(1, lease_seconds // 3)


def _assign_operation_lease(
    operation: DomainOperation,
    *,
    owner: str,
    lease_seconds: int,
    now=None,
) -> None:
    current = now or utc_now()
    operation.lease_owner = owner
    operation.lease_expires_at = current + timedelta(seconds=lease_seconds)
    operation.updated_at = current


def _operation_lease_current(
    operation: DomainOperation,
    *,
    owner: str,
    now=None,
) -> bool:
    current = now or utc_now()
    if operation.lease_owner != owner:
        return False
    if operation.lease_expires_at is None or operation.lease_expires_at < current:
        return False
    return True


def _heartbeat_operation_lease(
    operation: DomainOperation,
    *,
    owner: str,
    lease_seconds: int,
    now=None,
) -> bool:
    current = now or utc_now()
    if not _operation_lease_current(operation, owner=owner, now=current):
        return False
    operation.lease_expires_at = current + timedelta(seconds=lease_seconds)
    operation.updated_at = current
    return True


def _mark_operation_uncertain(db: Session, operation: DomainOperation, result: RuntimeControllerResult) -> None:
    now = utc_now()
    operation.message = result.message or "Runtime outcome uncertain; reconciliation required."
    operation.error_code = None
    operation.error_message = None
    operation.updated_at = now
    operation.version += 1
    db.commit()


def _raise_for_controller_result(
    db: Session,
    operation: DomainOperation,
    result: RuntimeControllerResult,
) -> None:
    if result.outcome == CONTROLLER_OUTCOME_SUCCEEDED:
        return
    if result.outcome == CONTROLLER_OUTCOME_UNCERTAIN:
        _mark_operation_uncertain(db, operation, result)
        raise DomainError(503, "dependency_unavailable", "Runtime outcome uncertain.")
    _fail_operation(
        db,
        operation,
        result.safe_code or "dependency_unavailable",
        result.message or "Runtime unavailable.",
    )
    raise DomainError(503, "dependency_unavailable", "Runtime unavailable.")


def _cancel_active_lifecycle_operation(db: Session, domain_id: str, *, message: str) -> DomainOperation | None:
    active = _active_operation(db, domain_id)
    if active is None:
        return None
    if active.operation_type == DOMAIN_OPERATION_DELETE:
        raise DomainError(
            409,
            "domain_operation_in_progress",
            "Another operation is already in progress for this domain.",
        )
    now = utc_now()
    active.status = DOMAIN_OPERATION_STATUS_CANCELLED
    active.message = message
    active.error_code = None
    active.error_message = None
    active.finished_at = now
    active.updated_at = now
    active.version += 1
    active.lease_owner = None
    active.lease_expires_at = None
    return active


def _apply_fenced_state_transition(
    db: Session,
    *,
    domain: Domain,
    operation: DomainOperation,
    settings: Settings,
    target_state: str,
    success_message: str,
    audit_event_name: str,
    audit_context: AuditContext | None,
    lease_owner: str,
) -> DomainOperation:
    now = utc_now()
    if not _operation_lease_current(operation, owner=lease_owner, now=now):
        _cancel_operation(db, operation, "Operation lease lost before completion.")
        db.refresh(operation)
        return operation

    updated = update_domain_state_if_current(
        db,
        domain_id=domain.id,
        runtime_instance_id=domain.runtime_instance_id,
        control_generation=operation.control_generation_at_start,
        state=target_state,
        commit=False,
    )
    if updated == 0:
        _cancel_operation(db, operation, "Stale domain generation; completion ignored.")
        db.refresh(operation)
        return operation

    operation.lease_owner = None
    operation.lease_expires_at = None
    _finish_operation(
        db,
        operation,
        success_message,
        audit_event_name=audit_event_name,
        audit_context=audit_context,
    )
    db.refresh(operation)
    return operation


def _validate_domain_id(domain_id: str) -> None:
    if _DOMAIN_ID_RE.fullmatch(domain_id) is None:
        raise DomainError(422, "validation_error", "Request validation failed.")


def _domain_or_404(db: Session, domain_id: str) -> Domain:
    _validate_domain_id(domain_id)
    domain = db.get(Domain, domain_id)
    if domain is None:
        raise DomainError(404, "not_found", "Domain not found.")
    return domain


def _require_domain_version(domain: Domain, expected_version: int) -> None:
    if domain.version != expected_version:
        raise DomainError(409, "stale_revision", "Resource version is stale.")


def _active_operation(db: Session, domain_id: str) -> DomainOperation | None:
    return db.scalar(
        select(DomainOperation)
        .where(
            DomainOperation.domain_id == domain_id,
            DomainOperation.status.in_(DOMAIN_OPERATION_ACTIVE_STATUSES),
        )
        .order_by(DomainOperation.created_at.desc())
    )


def _ensure_no_active_operation(db: Session, domain_id: str) -> None:
    if _active_operation(db, domain_id) is not None:
        raise DomainError(
            409,
            "domain_operation_in_progress",
            "Another operation is already in progress for this domain.",
        )


def _operation(
    *,
    domain: Domain,
    operation_type: str,
    status: str,
    requested_by_user: User | None,
    request_id: str | None = None,
    message: str,
) -> DomainOperation:
    now = utc_now()
    return DomainOperation(
        id=str(uuid.uuid4()),
        domain_id=domain.id,
        operation_type=operation_type,
        status=status,
        control_generation_at_start=domain.control_generation,
        requested_by_user_id=requested_by_user.id if requested_by_user is not None else None,
        request_id=request_id,
        message=message,
        started_at=now if status == DOMAIN_OPERATION_STATUS_RUNNING else None,
        created_at=now,
        updated_at=now,
    )


def _finish_operation(
    db: Session,
    operation: DomainOperation,
    message: str,
    *,
    audit_event_name: str | None = None,
    audit_context: AuditContext | None = None,
) -> None:
    now = utc_now()

    def mutate() -> DomainOperation:
        operation.status = DOMAIN_OPERATION_STATUS_SUCCEEDED
        operation.message = message
        operation.error_code = None
        operation.error_message = None
        operation.finished_at = now
        operation.updated_at = now
        operation.version += 1
        return operation

    if audit_event_name is not None and audit_context is not None:
        commit_protected_mutation(
            db,
            mutate,
            event_name=audit_event_name,
            context=audit_context,
            target_kind="domain",
            target_id=operation.domain_id,
            metadata={"operationType": operation.operation_type, "operationStatus": DOMAIN_OPERATION_STATUS_SUCCEEDED},
        )
        return
    mutate()
    db.commit()


def _cancel_operation(db: Session, operation: DomainOperation, message: str) -> None:
    now = utc_now()
    operation.status = DOMAIN_OPERATION_STATUS_CANCELLED
    operation.message = message
    operation.error_code = None
    operation.error_message = None
    operation.finished_at = now
    operation.updated_at = now
    operation.version += 1
    db.commit()


def _fail_operation(
    db: Session,
    operation: DomainOperation,
    code: str,
    message: str,
    *,
    audit_event_name: str | None = None,
    audit_context: AuditContext | None = None,
) -> None:
    now = utc_now()
    operation.status = DOMAIN_OPERATION_STATUS_FAILED
    operation.message = message
    operation.error_code = code
    operation.error_message = message
    operation.finished_at = now
    operation.updated_at = now
    operation.version += 1
    if audit_event_name is not None:
        AuditService(db).record(
            audit_event_name,
            context=audit_context or AuditContext(actor_kind=AUDIT_ACTOR_WORKER, request_id=operation.request_id),
            target_kind="domain_operation",
            target_id=operation.id,
            outcome=AUDIT_OUTCOME_FAILED,
            safe_error_code=code,
            metadata={"operationType": operation.operation_type, "operationStatus": operation.status},
        )
    db.commit()


def create_domain(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    display_name: str | None,
    embedding_profile_id: str,
    requested_by_user: User,
    controller: DomainRuntimeController | None = None,
    audit_context: AuditContext | None = None,
) -> Domain:
    _validate_domain_id(domain_id)
    if db.get(Domain, domain_id) is not None:
        raise DomainError(409, "operation_conflict", "Domain id already exists.")

    from context_engine.services.runtime_config import SecretCrypto, TrustedRuntimeResolver

    TrustedRuntimeResolver(db, SecretCrypto.from_settings(settings)).resolve_embedding_profile(embedding_profile_id)
    now = utc_now()
    domain = Domain(
        id=domain_id,
        display_name=display_name or domain_id,
        state=DOMAIN_STATE_STOPPED,
        embedding_profile_id=embedding_profile_id,
        runtime_instance_id=str(uuid.uuid4()),
        control_generation=1,
        version=1,
        created_at=now,
        updated_at=now,
    )
    operation = _operation(
        domain=domain,
        operation_type=DOMAIN_OPERATION_CREATE,
        status=DOMAIN_OPERATION_STATUS_RUNNING,
        requested_by_user=requested_by_user,
        request_id=audit_context.request_id if audit_context is not None else None,
        message="Creating domain.",
    )
    db.add(domain)
    db.add(operation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "operation_conflict", "Domain id already exists.") from exc

    controller = controller or controller_from_settings(settings)
    result = controller.provision(
        domain,
        operation_key=operation.id,
        control_generation=domain.control_generation,
    )
    _raise_for_controller_result(db, operation, result)
    _finish_operation(
        db,
        operation,
        "Domain created.",
        audit_event_name=AUDIT_EVENT_DOMAIN_CREATED,
        audit_context=audit_context,
    )
    db.refresh(domain)
    return domain


def start_domain(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    requested_by_user: User,
    controller: DomainRuntimeController | None = None,
    audit_context: AuditContext | None = None,
) -> DomainOperation:
    domain = _domain_or_404(db, domain_id)
    _ensure_no_active_operation(db, domain.id)
    if domain.state != DOMAIN_STATE_STOPPED:
        raise DomainError(409, "domain_state_conflict", "Domain lifecycle state does not allow this operation.")
    now = utc_now()
    domain.control_generation += 1
    domain.version += 1
    domain.updated_at = now
    operation = _operation(
        domain=domain,
        operation_type=DOMAIN_OPERATION_START,
        status=DOMAIN_OPERATION_STATUS_RUNNING,
        requested_by_user=requested_by_user,
        request_id=audit_context.request_id if audit_context is not None else None,
        message="Starting domain.",
    )
    _assign_operation_lease(
        operation,
        owner=settings.domain_lifecycle_worker_id,
        lease_seconds=settings.domain_lifecycle_lease_seconds,
        now=now,
    )
    db.add(operation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "domain_operation_in_progress", "Another operation is already in progress for this domain.") from exc

    controller = controller or controller_from_settings(settings)
    result = controller.start(
        domain,
        operation_key=operation.id,
        control_generation=operation.control_generation_at_start,
    )
    _raise_for_controller_result(db, operation, result)
    return _apply_fenced_state_transition(
        db,
        domain=domain,
        operation=operation,
        settings=settings,
        target_state=DOMAIN_STATE_RUNNING,
        success_message="Domain started.",
        audit_event_name=AUDIT_EVENT_DOMAIN_STARTED,
        audit_context=audit_context,
        lease_owner=settings.domain_lifecycle_worker_id,
    )


def stop_domain(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    requested_by_user: User,
    controller: DomainRuntimeController | None = None,
    audit_context: AuditContext | None = None,
) -> DomainOperation:
    domain = _domain_or_404(db, domain_id)
    _ensure_no_active_operation(db, domain.id)
    if domain.state != DOMAIN_STATE_RUNNING:
        raise DomainError(409, "domain_state_conflict", "Domain lifecycle state does not allow this operation.")
    now = utc_now()
    domain.control_generation += 1
    domain.version += 1
    domain.updated_at = now
    operation = _operation(
        domain=domain,
        operation_type=DOMAIN_OPERATION_STOP,
        status=DOMAIN_OPERATION_STATUS_RUNNING,
        requested_by_user=requested_by_user,
        request_id=audit_context.request_id if audit_context is not None else None,
        message="Stopping domain.",
    )
    _assign_operation_lease(
        operation,
        owner=settings.domain_lifecycle_worker_id,
        lease_seconds=settings.domain_lifecycle_lease_seconds,
        now=now,
    )
    db.add(operation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "domain_operation_in_progress", "Another operation is already in progress for this domain.") from exc

    controller = controller or controller_from_settings(settings)
    result = controller.stop(
        domain,
        operation_key=operation.id,
        control_generation=operation.control_generation_at_start,
    )
    _raise_for_controller_result(db, operation, result)
    return _apply_fenced_state_transition(
        db,
        domain=domain,
        operation=operation,
        settings=settings,
        target_state=DOMAIN_STATE_STOPPED,
        success_message="Domain stopped.",
        audit_event_name=AUDIT_EVENT_DOMAIN_STOPPED,
        audit_context=audit_context,
        lease_owner=settings.domain_lifecycle_worker_id,
    )


def enqueue_delete_domain(
    db: Session,
    *,
    domain_id: str,
    requested_by_user: User,
    expected_version: int,
    audit_context: AuditContext | None = None,
) -> DomainOperation:
    domain = _domain_or_404(db, domain_id)
    _require_domain_version(domain, expected_version)
    now = utc_now()

    def mutate() -> DomainOperation:
        from context_engine.services.chat_turns import redact_turns_for_domain
        from context_engine.services.sources import _expire_composer_tokens_for_source

        cancelled = _cancel_active_lifecycle_operation(
            db,
            domain.id,
            message="Superseded by domain delete.",
        )
        if cancelled is not None:
            db.flush()
        domain.state = DOMAIN_STATE_DELETING
        domain.control_generation += 1
        domain.version += 1
        domain.updated_at = now
        redact_turns_for_domain(db, domain.id, audit_context=audit_context, commit=False)
        for source_id in db.scalars(select(SourceDocument.id).where(SourceDocument.domain_id == domain.id)):
            _expire_composer_tokens_for_source(db, source_id, now)
        operation = _operation(
            domain=domain,
            operation_type=DOMAIN_OPERATION_DELETE,
            status=DOMAIN_OPERATION_STATUS_QUEUED,
            requested_by_user=requested_by_user,
            request_id=audit_context.request_id if audit_context is not None else None,
            message="Delete queued.",
        )
        operation.control_generation_at_start = domain.control_generation
        db.add(operation)
        return operation

    try:
        if audit_context is not None:
            operation = commit_protected_mutation(
                db,
                mutate,
                event_name=AUDIT_EVENT_DOMAIN_DELETE_QUEUED,
                context=audit_context,
                target_kind="domain",
                target_id=domain.id,
                metadata={
                    "operationType": DOMAIN_OPERATION_DELETE,
                    "operationStatus": DOMAIN_OPERATION_STATUS_QUEUED,
                },
            )
        else:
            operation = mutate()
            db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "domain_operation_in_progress", "Another operation is already in progress for this domain.") from exc
    db.refresh(operation)
    return operation


def update_domain_state_if_current(
    db: Session,
    *,
    domain_id: str,
    runtime_instance_id: str,
    control_generation: int,
    state: str,
    commit: bool = True,
) -> int:
    result = db.execute(
        update(Domain)
        .where(
            Domain.id == domain_id,
            Domain.runtime_instance_id == runtime_instance_id,
            Domain.control_generation == control_generation,
        )
        .values(state=state, updated_at=utc_now(), version=Domain.version + 1)
    )
    if commit:
        db.commit()
    return int(result.rowcount or 0)


def domain_available(db: Session, domain: Domain, controller: DomainRuntimeController) -> bool:
    if domain.state != DOMAIN_STATE_RUNNING:
        return False
    if _active_operation(db, domain.id) is not None:
        return False
    return controller.health(domain).healthy


def _directory_size_bytes(root: Path) -> int:
    try:
        root = root.resolve()
    except OSError:
        return 0
    if not root.exists():
        return 0
    total = 0
    try:
        paths = root.rglob("*")
        for path in paths:
            try:
                if path.is_file():
                    total += path.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def _source_domain_storage_dir(settings: Settings, domain_id: str) -> Path:
    root = Path(settings.source_storage_root).resolve()
    candidate = (root / "domains" / domain_id).resolve()
    if candidate == root or root not in candidate.parents:
        raise DomainControllerError("Source storage path escaped root.")
    return candidate


def _domain_database_bytes(db: Session, domain_id: str) -> int:
    markdown_bytes = db.scalar(
        select(func.coalesce(func.sum(func.length(SourceBlock.canonical_markdown)), 0)).where(
            SourceBlock.domain_id == domain_id
        )
    )
    section_path_bytes = db.scalar(
        select(func.coalesce(func.sum(func.length(SourceBlock.section_path)), 0)).where(
            SourceBlock.domain_id == domain_id,
            SourceBlock.section_path.is_not(None),
        )
    )
    source_metadata_bytes = db.scalar(
        select(
            func.coalesce(
                func.sum(func.length(SourceDocument.original_filename) + func.length(SourceDocument.content_type)),
                0,
            )
        ).where(SourceDocument.domain_id == domain_id)
    )
    return int(markdown_bytes or 0) + int(section_path_bytes or 0) + int(source_metadata_bytes or 0)


def _storage_percent(bytes_value: int, limit_bytes: int) -> int:
    if limit_bytes <= 0:
        return 0
    if bytes_value <= 0:
        return 0
    return min(100, max(1, round((bytes_value / limit_bytes) * 100)))


def _storage_warning(total_bytes: int, limit_bytes: int) -> str:
    if total_bytes >= limit_bytes:
        return "exceeded"
    if total_bytes >= int(limit_bytes * 0.8):
        return "near_limit"
    return "ok"


def safe_domain_storage_summary(
    db: Session,
    settings: Settings,
    domain: Domain,
    controller: DomainRuntimeController,
) -> dict[str, Any]:
    limit_bytes = settings.domain_storage_limit_bytes
    try:
        source_storage_bytes = _directory_size_bytes(_source_domain_storage_dir(settings, domain.id))
    except (OSError, DomainControllerError):
        source_storage_bytes = 0
    runtime_bytes = _directory_size_bytes(controller.runtime_dir(domain.id, domain.runtime_instance_id))
    database_bytes = _domain_database_bytes(db, domain.id)
    total_bytes = source_storage_bytes + runtime_bytes + database_bytes
    return {
        "limitBytes": limit_bytes,
        "totalBytes": total_bytes,
        "totalPercent": _storage_percent(total_bytes, limit_bytes),
        "warning": _storage_warning(total_bytes, limit_bytes),
        "components": [
            {
                "kind": "source_storage",
                "label": "Source storage",
                "bytes": source_storage_bytes,
                "percent": _storage_percent(source_storage_bytes, limit_bytes),
            },
            {
                "kind": "graph_index",
                "label": "Graph index",
                "bytes": runtime_bytes,
                "percent": _storage_percent(runtime_bytes, limit_bytes),
            },
            {
                "kind": "database_metadata",
                "label": "Database metadata",
                "bytes": database_bytes,
                "percent": _storage_percent(database_bytes, limit_bytes),
            },
        ],
        "calculatedAt": iso_utc(utc_now()),
    }


def _embedding_profile_summary(db: Session, domain: Domain) -> dict[str, Any]:
    profile = domain.embedding_profile
    if profile is None:
        profile = db.get(ModelProfile, domain.embedding_profile_id)
    if profile is None:
        raise DomainError(503, "dependency_unavailable", "Embedding profile is unavailable.")
    return {
        "id": profile.id,
        "name": profile.name,
        "vectorDimensions": int(profile.vector_dimensions or 0),
    }


def _domain_allowed_actions(domain: Domain, active: DomainOperation | None) -> list[dict[str, Any]]:
    busy = active is not None
    deleting = domain.state == DOMAIN_STATE_DELETING

    def action(name: str, enabled: bool, reason: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": name, "enabled": enabled}
        if not enabled and reason is not None:
            payload["reasonCode"] = reason
        return payload

    if deleting:
        reason = "domain_state_conflict"
        return [
            action("start", False, reason),
            action("stop", False, reason),
            action("delete", False, reason),
        ]
    if busy:
        reason = "domain_operation_in_progress"
        return [
            action("start", False, reason),
            action("stop", False, reason),
            action("delete", False, reason),
        ]
    return [
        action("start", domain.state == DOMAIN_STATE_STOPPED, "domain_state_conflict"),
        action("stop", domain.state == DOMAIN_STATE_RUNNING, "domain_state_conflict"),
        action("delete", True),
    ]


def safe_domain_admin(db: Session, settings: Settings, domain: Domain, controller: DomainRuntimeController) -> dict[str, Any]:
    del settings  # retained for call-site compatibility; storage is not a public DTO field
    active = _active_operation(db, domain.id)
    return {
        "id": domain.id,
        "displayName": domain.display_name,
        "state": domain.state,
        "queryEligible": domain_available(db, domain, controller),
        "embeddingProfile": _embedding_profile_summary(db, domain),
        "runtimeReady": controller.health(domain).healthy,
        "controlGeneration": domain.control_generation,
        "activeOperationId": active.id if active is not None else None,
        "createdAt": iso_utc(domain.created_at),
        "updatedAt": iso_utc(domain.updated_at),
        "version": domain.version,
        "allowedActions": _domain_allowed_actions(domain, active),
    }


def safe_member_domain(domain: Domain) -> dict[str, Any]:
    return {
        "id": domain.id,
        "displayName": domain.display_name,
        "state": domain.state,
        "queryEligible": True,
    }


def safe_domain_operation(operation: DomainOperation) -> dict[str, Any]:
    error = None
    if operation.error_code is not None or operation.error_message is not None:
        error = {
            "code": operation.error_code or "internal_error",
            "message": operation.error_message or operation.message or "Operation failed.",
        }
    return {
        "id": operation.id,
        "targetKind": "domain",
        "targetRef": operation.domain_id,
        "operationType": operation.operation_type,
        "status": operation.status,
        "generation": operation.control_generation_at_start,
        "message": operation.message,
        "error": error,
        "requestedAt": iso_utc(operation.created_at),
        "startedAt": iso_utc(operation.started_at) if operation.started_at is not None else None,
        "finishedAt": iso_utc(operation.finished_at) if operation.finished_at is not None else None,
        "version": operation.version,
        "allowedActions": [],
    }


def admin_domain_list(db: Session, settings: Settings) -> list[dict[str, Any]]:
    controller = controller_from_settings(settings)
    domains = list(db.scalars(select(Domain).order_by(Domain.id)))
    return [safe_domain_admin(db, settings, domain, controller) for domain in domains]


def member_domain_list(db: Session, settings: Settings) -> list[dict[str, Any]]:
    controller = controller_from_settings(settings)
    domains = list(db.scalars(select(Domain).where(Domain.state == DOMAIN_STATE_RUNNING).order_by(Domain.id)))
    return [safe_member_domain(domain) for domain in domains if domain_available(db, domain, controller)]


def domain_detail(db: Session, settings: Settings, domain_id: str) -> dict[str, Any]:
    controller = controller_from_settings(settings)
    return safe_domain_admin(db, settings, _domain_or_404(db, domain_id), controller)


def domain_status(db: Session, settings: Settings, domain_id: str) -> dict[str, Any]:
    domain = _domain_or_404(db, domain_id)
    controller = controller_from_settings(settings)
    active = _active_operation(db, domain.id)
    return {
        "domain": safe_domain_admin(db, settings, domain, controller),
        "activeOperation": safe_domain_operation(active) if active is not None else None,
    }


def domain_operations(db: Session, domain_id: str) -> list[dict[str, Any]]:
    _domain_or_404(db, domain_id)
    operations = list(
        db.scalars(
            select(DomainOperation)
            .where(DomainOperation.domain_id == domain_id)
            .order_by(DomainOperation.created_at.desc(), DomainOperation.id)
        )
    )
    return [safe_domain_operation(operation) for operation in operations]


def reconcile_uncertain_lifecycle_operations(db: Session, settings: Settings) -> int:
    """Probe uncertain start/stop ops and terminalize when runtime state is clear.

    Delete uncertain ops are reclaimed by DomainDeleteWorker via expired leases.
    """
    controller = controller_from_settings(settings)
    now = utc_now()
    operations = list(
        db.scalars(
            select(DomainOperation)
            .where(
                DomainOperation.operation_type.in_((DOMAIN_OPERATION_START, DOMAIN_OPERATION_STOP)),
                DomainOperation.status == DOMAIN_OPERATION_STATUS_RUNNING,
                DomainOperation.message.is_not(None),
                func.lower(DomainOperation.message).like("%uncertain%"),
            )
            .order_by(DomainOperation.created_at, DomainOperation.id)
            .limit(20)
        )
    )
    resolved = 0
    for operation in operations:
        domain = db.get(Domain, operation.domain_id)
        if domain is None:
            _cancel_operation(db, operation, "Domain removed during reconciliation.")
            resolved += 1
            continue
        if domain.control_generation != operation.control_generation_at_start:
            _cancel_operation(db, operation, "Stale domain generation; reconciliation ignored.")
            resolved += 1
            continue
        health = controller.health(
            domain,
            operation_key=operation.id,
            control_generation=operation.control_generation_at_start,
        )
        if health.outcome == CONTROLLER_OUTCOME_UNCERTAIN:
            _assign_operation_lease(
                operation,
                owner=settings.domain_lifecycle_worker_id,
                lease_seconds=settings.domain_lifecycle_lease_seconds,
                now=now,
            )
            db.commit()
            continue
        if operation.operation_type == DOMAIN_OPERATION_START:
            if health.healthy:
                _assign_operation_lease(
                    operation,
                    owner=settings.domain_lifecycle_worker_id,
                    lease_seconds=settings.domain_lifecycle_lease_seconds,
                    now=now,
                )
                db.commit()
                _apply_fenced_state_transition(
                    db,
                    domain=domain,
                    operation=operation,
                    settings=settings,
                    target_state=DOMAIN_STATE_RUNNING,
                    success_message="Domain started after reconciliation.",
                    audit_event_name=AUDIT_EVENT_DOMAIN_STARTED,
                    audit_context=AuditContext(actor_kind=AUDIT_ACTOR_WORKER, request_id=operation.request_id),
                    lease_owner=settings.domain_lifecycle_worker_id,
                )
                resolved += 1
            else:
                _fail_operation(
                    db,
                    operation,
                    "dependency_unavailable",
                    "Runtime did not become ready during reconciliation.",
                )
                resolved += 1
        elif operation.operation_type == DOMAIN_OPERATION_STOP:
            if not health.healthy:
                _assign_operation_lease(
                    operation,
                    owner=settings.domain_lifecycle_worker_id,
                    lease_seconds=settings.domain_lifecycle_lease_seconds,
                    now=now,
                )
                db.commit()
                _apply_fenced_state_transition(
                    db,
                    domain=domain,
                    operation=operation,
                    settings=settings,
                    target_state=DOMAIN_STATE_STOPPED,
                    success_message="Domain stopped after reconciliation.",
                    audit_event_name=AUDIT_EVENT_DOMAIN_STOPPED,
                    audit_context=AuditContext(actor_kind=AUDIT_ACTOR_WORKER, request_id=operation.request_id),
                    lease_owner=settings.domain_lifecycle_worker_id,
                )
                resolved += 1
            else:
                _assign_operation_lease(
                    operation,
                    owner=settings.domain_lifecycle_worker_id,
                    lease_seconds=settings.domain_lifecycle_lease_seconds,
                    now=now,
                )
                db.commit()
    return resolved


class DomainDeleteWorker:
    def __init__(self, settings: Settings, controller: DomainRuntimeController | None = None) -> None:
        self._settings = settings
        self._controller = controller or controller_from_settings(settings)

    def run_once(self, db: Session) -> bool:
        reconcile_uncertain_lifecycle_operations(db, self._settings)
        operation = self._claim_next_operation(db)
        if operation is None:
            return False

        domain = db.get(Domain, operation.domain_id)
        if domain is None:
            if not self._lease_still_owned(db, operation):
                return True
            _finish_operation(
                db,
                operation,
                "Domain already removed.",
                audit_event_name=AUDIT_EVENT_DOMAIN_DELETE_SUCCEEDED,
                audit_context=AuditContext(actor_kind=AUDIT_ACTOR_WORKER, request_id=operation.request_id),
            )
            return True

        runtime_instance_id = domain.runtime_instance_id
        control_generation = operation.control_generation_at_start
        try:
            from context_engine.services.chat_turns import redact_turns_for_domain
            from context_engine.services.indexing import SourceIndexError
            from context_engine.services.sources import SourceStorageError, purge_domain_sources_local

            if not self._heartbeat(db, operation):
                return True
            context = AuditContext(actor_kind=AUDIT_ACTOR_WORKER, request_id=operation.request_id)
            redact_turns_for_domain(db, domain.id, audit_context=context)
            if not self._heartbeat(db, operation):
                return True
            purge_domain_sources_local(db, self._settings, domain.id, audit_context=context)
            if not self._heartbeat(db, operation):
                return True
            delete_result = self._controller.delete(
                domain,
                operation_key=operation.id,
                control_generation=control_generation,
            )
            if delete_result.outcome == CONTROLLER_OUTCOME_UNCERTAIN:
                db.rollback()
                fresh = db.get(DomainOperation, operation.id)
                if fresh is not None:
                    _mark_operation_uncertain(db, fresh, delete_result)
                return True
            if delete_result.outcome == CONTROLLER_OUTCOME_FAILED:
                db.rollback()
                fresh = db.get(DomainOperation, operation.id)
                if fresh is not None and self._lease_still_owned(db, fresh):
                    _fail_operation(
                        db,
                        fresh,
                        delete_result.safe_code or "domain_runtime_unavailable",
                        delete_result.message or "Runtime resources could not be removed.",
                        audit_event_name=AUDIT_EVENT_DOMAIN_DELETE_FAILED,
                    )
                return True
        except SourceIndexError as exc:
            db.rollback()
            fresh = db.get(DomainOperation, operation.id)
            if fresh is not None and self._lease_still_owned(db, fresh):
                _fail_operation(db, fresh, exc.code, exc.message, audit_event_name=AUDIT_EVENT_DOMAIN_DELETE_FAILED)
            return True
        except SourceStorageError:
            db.rollback()
            fresh = db.get(DomainOperation, operation.id)
            if fresh is not None and self._lease_still_owned(db, fresh):
                _fail_operation(
                    db,
                    fresh,
                    "source_delete_failed",
                    "Source resources could not be removed.",
                    audit_event_name=AUDIT_EVENT_DOMAIN_DELETE_FAILED,
                )
            return True

        if not self._lease_still_owned(db, operation):
            return True

        current = db.get(Domain, domain.id)
        if current is None:
            _finish_operation(
                db,
                operation,
                "Domain already removed.",
                audit_event_name=AUDIT_EVENT_DOMAIN_DELETE_SUCCEEDED,
                audit_context=AuditContext(actor_kind=AUDIT_ACTOR_WORKER, request_id=operation.request_id),
            )
            return True
        if current.runtime_instance_id != runtime_instance_id or current.control_generation != control_generation:
            _cancel_operation(db, operation, "Delete superseded by a newer domain operation.")
            return True
        AuditService(db).record(
            AUDIT_EVENT_DOMAIN_DELETE_SUCCEEDED,
            context=AuditContext(actor_kind=AUDIT_ACTOR_WORKER, request_id=operation.request_id),
            target_kind="domain_operation",
            target_id=operation.id,
            metadata={"operationType": operation.operation_type, "operationStatus": DOMAIN_OPERATION_STATUS_SUCCEEDED},
        )
        # Domain row CASCADE removes domain_operations; audit preserves the outcome.
        db.delete(current)
        db.commit()
        return True

    def _lease_still_owned(self, db: Session, operation: DomainOperation) -> bool:
        db.refresh(operation)
        return _operation_lease_current(
            operation,
            owner=self._settings.domain_delete_worker_id,
        )

    def _heartbeat(self, db: Session, operation: DomainOperation) -> bool:
        now = utc_now()
        if not _heartbeat_operation_lease(
            operation,
            owner=self._settings.domain_delete_worker_id,
            lease_seconds=self._settings.domain_delete_lease_seconds,
            now=now,
        ):
            return False
        db.commit()
        return True

    def _claim_next_operation(self, db: Session) -> DomainOperation | None:
        now = utc_now()
        operation = db.scalar(
            select(DomainOperation)
            .where(
                DomainOperation.operation_type == DOMAIN_OPERATION_DELETE,
                or_(
                    DomainOperation.status == DOMAIN_OPERATION_STATUS_QUEUED,
                    (
                        (DomainOperation.status == DOMAIN_OPERATION_STATUS_RUNNING)
                        & (DomainOperation.lease_expires_at.is_not(None))
                        & (DomainOperation.lease_expires_at < now)
                    ),
                ),
            )
            .order_by(DomainOperation.created_at, DomainOperation.id)
            # Row lock prevents double-claim across worker processes on Postgres;
            # SQLAlchemy's SQLite dialect ignores FOR UPDATE, so dev/tests are unaffected.
            .with_for_update(skip_locked=True)
        )
        if operation is None:
            return None
        operation.status = DOMAIN_OPERATION_STATUS_RUNNING
        _assign_operation_lease(
            operation,
            owner=self._settings.domain_delete_worker_id,
            lease_seconds=self._settings.domain_delete_lease_seconds,
            now=now,
        )
        operation.started_at = operation.started_at or now
        if operation.message and "uncertain" in operation.message.lower():
            operation.message = "Reconciling uncertain delete."
        else:
            operation.message = "Removing runtime resources."
        operation.updated_at = now
        db.commit()
        db.refresh(operation)
        safe_log(
            logger,
            "domain_delete_worker.claimed",
            request_id=operation.request_id,
            domain_id=operation.domain_id,
            operation_id=operation.id,
            outcome="succeeded",
        )
        safe_increment(
            "worker_operation",
            operation_type="domain_delete",
            outcome="succeeded",
        )
        return operation
