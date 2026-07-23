from __future__ import annotations

import json
import logging
import re
import shutil
import shlex
import subprocess
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    SourceBlock,
    SourceDocument,
    User,
)
from context_engine.services.audit import AuditContext, AuditService
from context_engine.services.auth import iso_utc
from context_engine.services.structured_logging import safe_log

logger = logging.getLogger(__name__)

DOMAIN_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{1,62}$"
_DOMAIN_ID_RE = re.compile(DOMAIN_ID_PATTERN)


class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class DomainControllerError(Exception):
    pass


@dataclass(frozen=True)
class RuntimeHealth:
    healthy: bool


class DomainRuntimeController(Protocol):
    uses_docker_socket: bool

    def runtime_dir(self, domain_id: str, runtime_instance_id: str) -> Path: ...

    def provision(self, domain: Domain) -> None: ...

    def start(self, domain: Domain) -> None: ...

    def stop(self, domain: Domain) -> None: ...

    def delete(self, domain: Domain) -> None: ...

    def health(self, domain: Domain) -> RuntimeHealth: ...

    def runtime_name(self, domain: Domain) -> str: ...


class LocalDomainRuntimeController:
    """Private controller boundary used by API/worker tests without Docker access."""

    uses_docker_socket = False

    def __init__(self, settings: Settings) -> None:
        self._root = Path(settings.domain_runtime_root)

    def runtime_dir(self, domain_id: str, runtime_instance_id: str) -> Path:
        return self._root / domain_id / runtime_instance_id

    def provision(self, domain: Domain) -> None:
        runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
        try:
            (runtime_dir / "workspace").mkdir(parents=True, exist_ok=True)
            (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
            runtime_db = runtime_dir / "runtime-db"
            runtime_db.mkdir(parents=True, exist_ok=True)
            (runtime_db / "lightrag.sqlite3").touch(exist_ok=True)
            self._write_record(domain, "stopped")
        except OSError as exc:
            raise DomainControllerError("Runtime storage unavailable.") from exc

    def start(self, domain: Domain) -> None:
        self.provision(domain)
        try:
            runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
            container_record = {
                "containerName": self.runtime_name(domain),
                "runtimeInstanceId": domain.runtime_instance_id,
                "status": "running",
                "hostPorts": [],
            }
            (runtime_dir / "container.json").write_text(json.dumps(container_record, sort_keys=True), encoding="utf-8")
            (runtime_dir / "health.json").write_text(json.dumps({"healthy": True}, sort_keys=True), encoding="utf-8")
            self._write_record(domain, "running")
        except OSError as exc:
            raise DomainControllerError("Runtime start failed.") from exc

    def stop(self, domain: Domain) -> None:
        try:
            runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
            for name in ("container.json", "health.json"):
                target = runtime_dir / name
                if target.exists():
                    target.unlink()
            if runtime_dir.exists():
                self._write_record(domain, "stopped")
        except OSError as exc:
            raise DomainControllerError("Runtime stop failed.") from exc

    def delete(self, domain: Domain) -> None:
        try:
            runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
            if runtime_dir.exists():
                shutil.rmtree(runtime_dir)
            domain_root = self._root / domain.id
            if domain_root.exists() and not any(domain_root.iterdir()):
                domain_root.rmdir()
        except OSError as exc:
            raise DomainControllerError("Runtime delete failed.") from exc

    def health(self, domain: Domain) -> RuntimeHealth:
        runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
        container_path = runtime_dir / "container.json"
        health_path = runtime_dir / "health.json"
        if not container_path.exists() or not health_path.exists():
            return RuntimeHealth(healthy=False)
        try:
            container = json.loads(container_path.read_text(encoding="utf-8"))
            health = json.loads(health_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return RuntimeHealth(healthy=False)
        return RuntimeHealth(healthy=container.get("hostPorts") == [] and health.get("healthy") is True)

    def runtime_name(self, domain: Domain) -> str:
        return f"ce_domain_{domain.id}_{domain.runtime_instance_id[:12]}"

    def _write_record(self, domain: Domain, status: str) -> None:
        runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
        record = {
            "runtimeName": self.runtime_name(domain),
            "runtimeInstanceId": domain.runtime_instance_id,
            "status": status,
        }
        (runtime_dir / "runtime.json").write_text(json.dumps(record, sort_keys=True), encoding="utf-8")


class DockerDomainRuntimeController:
    """Production controller adapter that delegates Docker access to a private command."""

    uses_docker_socket = False

    def __init__(self, settings: Settings) -> None:
        self._root = Path(settings.domain_runtime_root)
        self._command = settings.domain_controller_command
        self._timeout_seconds = settings.domain_controller_timeout_seconds

    def runtime_dir(self, domain_id: str, runtime_instance_id: str) -> Path:
        return self._root / domain_id / runtime_instance_id

    def provision(self, domain: Domain) -> None:
        self._run_action("provision", domain)

    def start(self, domain: Domain) -> None:
        self._run_action("start", domain)

    def stop(self, domain: Domain) -> None:
        self._run_action("stop", domain)

    def delete(self, domain: Domain) -> None:
        self._run_action("delete", domain)

    def health(self, domain: Domain) -> RuntimeHealth:
        try:
            payload = self._run_action("health", domain)
        except DomainControllerError:
            return RuntimeHealth(healthy=False)
        return RuntimeHealth(healthy=payload.get("healthy") is True)

    def runtime_name(self, domain: Domain) -> str:
        return f"ce_domain_{domain.id}_{domain.runtime_instance_id[:12]}"

    def _run_action(self, action: str, domain: Domain) -> dict[str, Any]:
        if not self._command:
            raise DomainControllerError("Runtime controller command is not configured.")
        runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
        request = {
            "action": action,
            "domainId": domain.id,
            "runtimeInstanceId": domain.runtime_instance_id,
            "runtimeName": self.runtime_name(domain),
            "runtimeDir": str(runtime_dir),
        }
        try:
            result = subprocess.run(
                [*shlex.split(self._command, posix=False), action],
                input=json.dumps(request),
                text=True,
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DomainControllerError("Runtime controller unavailable.") from exc
        if result.returncode != 0:
            raise DomainControllerError("Runtime controller action failed.")
        stdout = result.stdout.strip()
        if not stdout:
            return {}
        try:
            parsed = json.loads(stdout)
        except ValueError as exc:
            raise DomainControllerError("Runtime controller returned invalid data.") from exc
        if not isinstance(parsed, dict):
            raise DomainControllerError("Runtime controller returned invalid data.")
        return parsed


def controller_from_settings(settings: Settings) -> DomainRuntimeController:
    kind = settings.domain_runtime_controller_kind.strip().lower()
    if kind == "docker":
        return DockerDomainRuntimeController(settings)
    if kind == "local":
        return LocalDomainRuntimeController(settings)
    raise DomainControllerError("Runtime controller configuration is invalid.")


def _validate_domain_id(domain_id: str) -> None:
    if _DOMAIN_ID_RE.fullmatch(domain_id) is None:
        raise DomainError(422, "validation_error", "Request validation failed.")


def _domain_or_404(db: Session, domain_id: str) -> Domain:
    _validate_domain_id(domain_id)
    domain = db.get(Domain, domain_id)
    if domain is None:
        raise DomainError(404, "domain_not_found", "Domain not found.")
    return domain


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
    operation.status = DOMAIN_OPERATION_STATUS_SUCCEEDED
    operation.message = message
    operation.error_code = None
    operation.error_message = None
    operation.finished_at = now
    operation.updated_at = now
    if audit_event_name is not None and audit_context is not None:
        AuditService(db).record(
            audit_event_name,
            context=audit_context,
            target_kind="domain",
            target_id=operation.domain_id,
            metadata={"operationType": operation.operation_type, "operationStatus": operation.status},
        )
    db.commit()


def _cancel_operation(db: Session, operation: DomainOperation, message: str) -> None:
    now = utc_now()
    operation.status = DOMAIN_OPERATION_STATUS_CANCELLED
    operation.message = message
    operation.error_code = None
    operation.error_message = None
    operation.finished_at = now
    operation.updated_at = now
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
        raise DomainError(409, "domain_id_conflict", "Domain id already exists.")

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
        raise DomainError(409, "domain_id_conflict", "Domain id already exists.") from exc

    try:
        controller = controller or controller_from_settings(settings)
        controller.provision(domain)
    except DomainControllerError as exc:
        _fail_operation(db, operation, "domain_runtime_unavailable", "Runtime resources could not be prepared.")
        raise DomainError(502, "domain_runtime_unavailable", "Runtime unavailable.") from exc
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
) -> Domain:
    domain = _domain_or_404(db, domain_id)
    _ensure_no_active_operation(db, domain.id)
    if domain.state != DOMAIN_STATE_STOPPED:
        raise DomainError(409, "domain_state_conflict", "Domain lifecycle state does not allow this operation.")
    operation = _operation(
        domain=domain,
        operation_type=DOMAIN_OPERATION_START,
        status=DOMAIN_OPERATION_STATUS_RUNNING,
        requested_by_user=requested_by_user,
        request_id=audit_context.request_id if audit_context is not None else None,
        message="Starting domain.",
    )
    db.add(operation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "domain_operation_in_progress", "Another operation is already in progress for this domain.") from exc

    try:
        controller = controller or controller_from_settings(settings)
        controller.start(domain)
    except DomainControllerError as exc:
        _fail_operation(db, operation, "domain_runtime_unavailable", "Runtime did not become ready.")
        raise DomainError(502, "domain_runtime_unavailable", "Runtime unavailable.") from exc
    domain.state = DOMAIN_STATE_RUNNING
    domain.updated_at = utc_now()
    _finish_operation(
        db,
        operation,
        "Domain started.",
        audit_event_name=AUDIT_EVENT_DOMAIN_STARTED,
        audit_context=audit_context,
    )
    db.refresh(domain)
    return domain


def stop_domain(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    requested_by_user: User,
    controller: DomainRuntimeController | None = None,
    audit_context: AuditContext | None = None,
) -> Domain:
    domain = _domain_or_404(db, domain_id)
    _ensure_no_active_operation(db, domain.id)
    if domain.state != DOMAIN_STATE_RUNNING:
        raise DomainError(409, "domain_state_conflict", "Domain lifecycle state does not allow this operation.")
    operation = _operation(
        domain=domain,
        operation_type=DOMAIN_OPERATION_STOP,
        status=DOMAIN_OPERATION_STATUS_RUNNING,
        requested_by_user=requested_by_user,
        request_id=audit_context.request_id if audit_context is not None else None,
        message="Stopping domain.",
    )
    db.add(operation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "domain_operation_in_progress", "Another operation is already in progress for this domain.") from exc

    try:
        controller = controller or controller_from_settings(settings)
        controller.stop(domain)
    except DomainControllerError as exc:
        _fail_operation(db, operation, "domain_runtime_unavailable", "Runtime could not be stopped.")
        raise DomainError(502, "domain_runtime_unavailable", "Runtime unavailable.") from exc
    domain.state = DOMAIN_STATE_STOPPED
    domain.updated_at = utc_now()
    _finish_operation(
        db,
        operation,
        "Domain stopped.",
        audit_event_name=AUDIT_EVENT_DOMAIN_STOPPED,
        audit_context=audit_context,
    )
    db.refresh(domain)
    return domain


def enqueue_delete_domain(
    db: Session,
    *,
    domain_id: str,
    requested_by_user: User,
    audit_context: AuditContext | None = None,
) -> DomainOperation:
    domain = _domain_or_404(db, domain_id)
    _ensure_no_active_operation(db, domain.id)
    now = utc_now()
    domain.state = DOMAIN_STATE_DELETING
    domain.control_generation += 1
    domain.updated_at = now
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
    if audit_context is not None:
        AuditService(db).record(
            AUDIT_EVENT_DOMAIN_DELETE_QUEUED,
            context=audit_context,
            target_kind="domain",
            target_id=domain.id,
            metadata={"operationType": DOMAIN_OPERATION_DELETE, "operationStatus": DOMAIN_OPERATION_STATUS_QUEUED},
        )
    try:
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
) -> int:
    result = db.execute(
        update(Domain)
        .where(
            Domain.id == domain_id,
            Domain.runtime_instance_id == runtime_instance_id,
            Domain.control_generation == control_generation,
        )
        .values(state=state, updated_at=utc_now())
    )
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


def safe_domain_admin(db: Session, settings: Settings, domain: Domain, controller: DomainRuntimeController) -> dict[str, Any]:
    return {
        "id": domain.id,
        "displayName": domain.display_name,
        "state": domain.state,
        "embeddingProfileId": domain.embedding_profile_id,
        "available": domain_available(db, domain, controller),
        "storageSummary": safe_domain_storage_summary(db, settings, domain, controller),
        "createdAt": iso_utc(domain.created_at),
        "updatedAt": iso_utc(domain.updated_at),
    }


def safe_member_domain(domain: Domain) -> dict[str, Any]:
    return {"id": domain.id, "displayName": domain.display_name, "available": True}


def safe_domain_status(db: Session, domain: Domain, controller: DomainRuntimeController) -> dict[str, Any]:
    return {
        "id": domain.id,
        "displayName": domain.display_name,
        "state": domain.state,
        "available": domain_available(db, domain, controller),
    }


def safe_domain_operation(operation: DomainOperation) -> dict[str, Any]:
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


def safe_active_operation(operation: DomainOperation | None) -> dict[str, Any] | None:
    if operation is None:
        return None
    return {
        "id": operation.id,
        "operationType": operation.operation_type,
        "status": operation.status,
        "message": operation.message,
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
    return {
        "domain": safe_domain_status(db, domain, controller),
        "activeOperation": safe_active_operation(_active_operation(db, domain.id)),
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


class DomainDeleteWorker:
    def __init__(self, settings: Settings, controller: DomainRuntimeController | None = None) -> None:
        self._settings = settings
        self._controller = controller or controller_from_settings(settings)

    def run_once(self, db: Session) -> bool:
        operation = self._claim_next_operation(db)
        if operation is None:
            return False

        domain = db.get(Domain, operation.domain_id)
        if domain is None:
            # Goal state already reached: finalize instead of leaving the operation RUNNING.
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

            context = AuditContext(actor_kind=AUDIT_ACTOR_WORKER, request_id=operation.request_id)
            redact_turns_for_domain(db, domain.id, audit_context=context)
            purge_domain_sources_local(db, self._settings, domain.id, audit_context=context)
            self._controller.delete(domain)
        except SourceIndexError as exc:
            db.rollback()
            _fail_operation(db, operation, exc.code, exc.message, audit_event_name=AUDIT_EVENT_DOMAIN_DELETE_FAILED)
            return True
        except SourceStorageError:
            db.rollback()
            _fail_operation(
                db,
                operation,
                "source_delete_failed",
                "Source resources could not be removed.",
                audit_event_name=AUDIT_EVENT_DOMAIN_DELETE_FAILED,
            )
            return True
        except DomainControllerError:
            db.rollback()
            _fail_operation(
                db,
                operation,
                "domain_runtime_unavailable",
                "Runtime resources could not be removed.",
                audit_event_name=AUDIT_EVENT_DOMAIN_DELETE_FAILED,
            )
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
            # A newer control action superseded this delete; do not touch the current runtime.
            _cancel_operation(db, operation, "Delete superseded by a newer domain operation.")
            return True
        AuditService(db).record(
            AUDIT_EVENT_DOMAIN_DELETE_SUCCEEDED,
            context=AuditContext(actor_kind=AUDIT_ACTOR_WORKER, request_id=operation.request_id),
            target_kind="domain_operation",
            target_id=operation.id,
            metadata={"operationType": operation.operation_type, "operationStatus": DOMAIN_OPERATION_STATUS_SUCCEEDED},
        )
        db.delete(current)
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
        operation.lease_owner = self._settings.domain_delete_worker_id
        operation.lease_expires_at = now + timedelta(seconds=self._settings.domain_delete_lease_seconds)
        operation.started_at = operation.started_at or now
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
        return operation
