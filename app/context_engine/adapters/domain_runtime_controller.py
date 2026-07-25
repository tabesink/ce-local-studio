from __future__ import annotations

import json
import logging
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from context_engine.config import Settings
from context_engine.models import Domain

logger = logging.getLogger(__name__)

ControllerOutcome = Literal["succeeded", "failed", "uncertain"]

CONTROLLER_OUTCOME_SUCCEEDED: ControllerOutcome = "succeeded"
CONTROLLER_OUTCOME_FAILED: ControllerOutcome = "failed"
CONTROLLER_OUTCOME_UNCERTAIN: ControllerOutcome = "uncertain"


class DomainControllerError(Exception):
    """Legacy hard-failure signal retained for non-result call sites during migration."""


@dataclass(frozen=True)
class RuntimeControllerResult:
    outcome: ControllerOutcome
    safe_code: str | None = None
    message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeHealth:
    healthy: bool
    outcome: ControllerOutcome = CONTROLLER_OUTCOME_SUCCEEDED
    safe_code: str | None = None
    message: str | None = None


class DomainRuntimeController(Protocol):
    uses_docker_socket: bool

    def runtime_dir(self, domain_id: str, runtime_instance_id: str) -> Path: ...

    def provision(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult: ...

    def start(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult: ...

    def stop(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult: ...

    def delete(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult: ...

    def health(
        self,
        domain: Domain,
        *,
        operation_key: str | None = None,
        control_generation: int | None = None,
    ) -> RuntimeHealth: ...

    def runtime_name(self, domain: Domain) -> str: ...


def _failed(message: str, *, safe_code: str = "dependency_unavailable") -> RuntimeControllerResult:
    return RuntimeControllerResult(
        outcome=CONTROLLER_OUTCOME_FAILED,
        safe_code=safe_code,
        message=message,
    )


def _succeeded(message: str | None = None, *, payload: dict[str, Any] | None = None) -> RuntimeControllerResult:
    return RuntimeControllerResult(
        outcome=CONTROLLER_OUTCOME_SUCCEEDED,
        message=message,
        payload=payload or {},
    )


def _uncertain(message: str, *, safe_code: str = "dependency_unavailable") -> RuntimeControllerResult:
    return RuntimeControllerResult(
        outcome=CONTROLLER_OUTCOME_UNCERTAIN,
        safe_code=safe_code,
        message=message,
    )


class LocalDomainRuntimeController:
    """Filesystem-backed controller used by API/worker tests without Docker access."""

    uses_docker_socket = False

    def __init__(self, settings: Settings) -> None:
        self._root = Path(settings.domain_runtime_root)

    def runtime_dir(self, domain_id: str, runtime_instance_id: str) -> Path:
        return self._root / domain_id / runtime_instance_id

    def provision(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult:
        del operation_key, control_generation
        runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
        try:
            (runtime_dir / "workspace").mkdir(parents=True, exist_ok=True)
            (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
            runtime_db = runtime_dir / "runtime-db"
            runtime_db.mkdir(parents=True, exist_ok=True)
            (runtime_db / "lightrag.sqlite3").touch(exist_ok=True)
            self._write_record(domain, "stopped")
        except OSError:
            return _failed("Runtime storage unavailable.")
        return _succeeded("Runtime provisioned.")

    def start(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult:
        provisioned = self.provision(
            domain,
            operation_key=operation_key,
            control_generation=control_generation,
        )
        if provisioned.outcome != CONTROLLER_OUTCOME_SUCCEEDED:
            return provisioned
        try:
            runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
            container_record = {
                "containerName": self.runtime_name(domain),
                "runtimeInstanceId": domain.runtime_instance_id,
                "operationKey": operation_key,
                "controlGeneration": control_generation,
                "status": "running",
                "hostPorts": [],
            }
            (runtime_dir / "container.json").write_text(json.dumps(container_record, sort_keys=True), encoding="utf-8")
            (runtime_dir / "health.json").write_text(json.dumps({"healthy": True}, sort_keys=True), encoding="utf-8")
            self._write_record(domain, "running", operation_key=operation_key, control_generation=control_generation)
        except OSError:
            return _failed("Runtime start failed.")
        return _succeeded("Runtime started.")

    def stop(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult:
        try:
            runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
            for name in ("container.json", "health.json"):
                target = runtime_dir / name
                if target.exists():
                    target.unlink()
            if runtime_dir.exists():
                self._write_record(domain, "stopped", operation_key=operation_key, control_generation=control_generation)
        except OSError:
            return _failed("Runtime stop failed.")
        return _succeeded("Runtime stopped.")

    def delete(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult:
        del operation_key, control_generation
        try:
            runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
            if runtime_dir.exists():
                shutil.rmtree(runtime_dir)
            domain_root = self._root / domain.id
            if domain_root.exists() and not any(domain_root.iterdir()):
                domain_root.rmdir()
        except OSError:
            return _failed("Runtime delete failed.")
        return _succeeded("Runtime deleted.")

    def health(
        self,
        domain: Domain,
        *,
        operation_key: str | None = None,
        control_generation: int | None = None,
    ) -> RuntimeHealth:
        del operation_key, control_generation
        runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
        container_path = runtime_dir / "container.json"
        health_path = runtime_dir / "health.json"
        if not container_path.exists() or not health_path.exists():
            return RuntimeHealth(healthy=False)
        try:
            container = json.loads(container_path.read_text(encoding="utf-8"))
            health = json.loads(health_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return RuntimeHealth(healthy=False, outcome=CONTROLLER_OUTCOME_FAILED, message="Runtime health unreadable.")
        return RuntimeHealth(healthy=container.get("hostPorts") == [] and health.get("healthy") is True)

    def runtime_name(self, domain: Domain) -> str:
        return f"ce_domain_{domain.id}_{domain.runtime_instance_id[:12]}"

    def _write_record(
        self,
        domain: Domain,
        status: str,
        *,
        operation_key: str | None = None,
        control_generation: int | None = None,
    ) -> None:
        runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
        record: dict[str, Any] = {
            "runtimeName": self.runtime_name(domain),
            "runtimeInstanceId": domain.runtime_instance_id,
            "status": status,
        }
        if operation_key is not None:
            record["operationKey"] = operation_key
        if control_generation is not None:
            record["controlGeneration"] = control_generation
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

    def provision(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult:
        return self._run_action("provision", domain, operation_key=operation_key, control_generation=control_generation)

    def start(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult:
        return self._run_action("start", domain, operation_key=operation_key, control_generation=control_generation)

    def stop(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult:
        return self._run_action("stop", domain, operation_key=operation_key, control_generation=control_generation)

    def delete(
        self,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult:
        return self._run_action("delete", domain, operation_key=operation_key, control_generation=control_generation)

    def health(
        self,
        domain: Domain,
        *,
        operation_key: str | None = None,
        control_generation: int | None = None,
    ) -> RuntimeHealth:
        result = self._run_action(
            "health",
            domain,
            operation_key=operation_key or f"health:{domain.id}:{domain.runtime_instance_id}",
            control_generation=control_generation if control_generation is not None else domain.control_generation,
        )
        if result.outcome == CONTROLLER_OUTCOME_UNCERTAIN:
            return RuntimeHealth(
                healthy=False,
                outcome=CONTROLLER_OUTCOME_UNCERTAIN,
                safe_code=result.safe_code,
                message=result.message,
            )
        if result.outcome == CONTROLLER_OUTCOME_FAILED:
            return RuntimeHealth(
                healthy=False,
                outcome=CONTROLLER_OUTCOME_FAILED,
                safe_code=result.safe_code,
                message=result.message,
            )
        return RuntimeHealth(healthy=result.payload.get("healthy") is True)

    def runtime_name(self, domain: Domain) -> str:
        return f"ce_domain_{domain.id}_{domain.runtime_instance_id[:12]}"

    def _run_action(
        self,
        action: str,
        domain: Domain,
        *,
        operation_key: str,
        control_generation: int,
    ) -> RuntimeControllerResult:
        if not self._command:
            return _failed("Runtime controller command is not configured.")
        runtime_dir = self.runtime_dir(domain.id, domain.runtime_instance_id)
        request = {
            "action": action,
            "domainId": domain.id,
            "runtimeInstanceId": domain.runtime_instance_id,
            "runtimeName": self.runtime_name(domain),
            "runtimeDir": str(runtime_dir),
            "operationKey": operation_key,
            "controlGeneration": control_generation,
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
        except subprocess.TimeoutExpired:
            return _uncertain("Runtime controller timed out with unknown remote outcome.")
        except OSError:
            return _failed("Runtime controller unavailable.")
        if result.returncode != 0:
            return _failed("Runtime controller action failed.")
        stdout = result.stdout.strip()
        if not stdout:
            return _succeeded(payload={})
        try:
            parsed = json.loads(stdout)
        except ValueError:
            return _failed("Runtime controller returned invalid data.")
        if not isinstance(parsed, dict):
            return _failed("Runtime controller returned invalid data.")
        return _succeeded(payload=parsed)


def controller_from_settings(settings: Settings) -> DomainRuntimeController:
    kind = settings.domain_runtime_controller_kind.strip().lower()
    if kind == "docker":
        return DockerDomainRuntimeController(settings)
    if kind == "local":
        return LocalDomainRuntimeController(settings)
    raise DomainControllerError("Runtime controller configuration is invalid.")
