from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

DOMAIN_LABEL = "context-engine.domain-id"
INSTANCE_LABEL = "context-engine.runtime-instance-id"
DEFAULT_IMAGE = "alpine:3.20"
_RUNTIME_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_ACTIONS = {"provision", "start", "health", "stop", "delete"}


class ControllerCommandError(Exception):
    pass


def _payload_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ControllerCommandError("Invalid runtime controller payload.")
    return value


def _runtime_dir(payload: dict[str, Any]) -> Path:
    runtime_dir = Path(_payload_str(payload, "runtimeDir")).resolve()
    domain_id = _payload_str(payload, "domainId")
    runtime_instance_id = _payload_str(payload, "runtimeInstanceId")
    if runtime_dir.name != runtime_instance_id or runtime_dir.parent.name != domain_id:
        raise ControllerCommandError("Invalid runtime directory.")
    if runtime_dir.parent == runtime_dir or runtime_dir.parent.parent == runtime_dir.parent:
        raise ControllerCommandError("Invalid runtime directory.")
    return runtime_dir


def _runtime_name(payload: dict[str, Any]) -> str:
    runtime_name = _payload_str(payload, "runtimeName")
    if _RUNTIME_NAME_RE.fullmatch(runtime_name) is None:
        raise ControllerCommandError("Invalid runtime name.")
    return runtime_name


def _ensure_runtime_layout(runtime_dir: Path) -> None:
    (runtime_dir / "workspace").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "runtime-db").mkdir(parents=True, exist_ok=True)


def _run_docker(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["docker", *args], text=True, capture_output=True, check=False)
    if check and result.returncode != 0:
        raise ControllerCommandError("Docker command failed.")
    return result


def _inspect(runtime_name: str) -> dict[str, Any] | None:
    result = _run_docker(["inspect", runtime_name], check=False)
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise ControllerCommandError("Docker inspect returned invalid data.") from exc
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise ControllerCommandError("Docker inspect returned invalid data.")
    return payload[0]


def _labels_match(container: dict[str, Any], payload: dict[str, Any]) -> bool:
    labels = container.get("Config", {}).get("Labels", {})
    if not isinstance(labels, dict):
        return False
    return labels.get(DOMAIN_LABEL) == payload["domainId"] and labels.get(INSTANCE_LABEL) == payload["runtimeInstanceId"]


def _is_running(container: dict[str, Any]) -> bool:
    return container.get("State", {}).get("Running") is True


def _has_no_host_ports(container: dict[str, Any]) -> bool:
    ports = container.get("NetworkSettings", {}).get("Ports")
    if ports in ({}, None):
        return True
    if not isinstance(ports, dict):
        return False
    return all(not value for value in ports.values())


def handle_action(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action not in _ACTIONS or payload.get("action") != action:
        raise ControllerCommandError("Invalid runtime controller action.")
    runtime_dir = _runtime_dir(payload)
    runtime_name = _runtime_name(payload)

    if action == "provision":
        _ensure_runtime_layout(runtime_dir)
        return {}

    if action == "health":
        container = _inspect(runtime_name)
        healthy = bool(container and _labels_match(container, payload) and _is_running(container) and _has_no_host_ports(container))
        return {"healthy": healthy}

    if action == "start":
        _ensure_runtime_layout(runtime_dir)
        container = _inspect(runtime_name)
        if container is not None:
            if not _labels_match(container, payload):
                raise ControllerCommandError("Runtime container name is already in use.")
            if not _is_running(container):
                _run_docker(["start", runtime_name])
            return {}
        image = os.getenv("CE_DOMAIN_CONTROLLER_IMAGE", DEFAULT_IMAGE)
        _run_docker(
            [
                "run",
                "-d",
                "--name",
                runtime_name,
                "--label",
                f"{DOMAIN_LABEL}={payload['domainId']}",
                "--label",
                f"{INSTANCE_LABEL}={payload['runtimeInstanceId']}",
                "--network",
                "none",
                "--mount",
                f"type=bind,src={runtime_dir},dst=/ce-runtime",
                image,
                "sh",
                "-c",
                "trap 'exit 0' TERM INT; while true; do sleep 3600; done",
            ]
        )
        return {}

    if action == "stop":
        container = _inspect(runtime_name)
        if container is None:
            return {}
        if not _labels_match(container, payload):
            raise ControllerCommandError("Runtime container name is already in use.")
        if _is_running(container):
            _run_docker(["stop", "--time", "10", runtime_name])
        return {}

    if action == "delete":
        container = _inspect(runtime_name)
        if container is not None:
            if not _labels_match(container, payload):
                raise ControllerCommandError("Runtime container name is already in use.")
            _run_docker(["rm", "-f", runtime_name])
        if runtime_dir.exists():
            shutil.rmtree(runtime_dir)
        return {}

    raise ControllerCommandError("Invalid runtime controller action.")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Runtime controller action is required.", file=sys.stderr)
        return 2
    action = args[0]
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ControllerCommandError("Invalid runtime controller payload.")
        result = handle_action(action, payload)
    except (ValueError, OSError, ControllerCommandError):
        print("Runtime controller action failed.", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
