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
PLACEHOLDER_IMAGE = "alpine:3.20"
DEFAULT_IMAGE = PLACEHOLDER_IMAGE
DEFAULT_NETWORK = "ce-domain-runtimes"
DEFAULT_PORT = 9621
SECRETS_RELATIVE = Path("secrets") / "provider.env"
ENDPOINT_RELATIVE = Path("endpoint.json")
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


def _controller_image() -> str:
    return os.getenv("CE_DOMAIN_CONTROLLER_IMAGE", DEFAULT_IMAGE).strip() or DEFAULT_IMAGE


def _controller_network() -> str:
    return os.getenv("CE_DOMAIN_CONTROLLER_NETWORK", DEFAULT_NETWORK).strip() or DEFAULT_NETWORK


def _controller_port() -> int:
    raw = os.getenv("CE_DOMAIN_LIGHTRAG_PORT", str(DEFAULT_PORT)).strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise ControllerCommandError("Invalid LightRAG port.") from exc
    if not (1 <= port <= 65535):
        raise ControllerCommandError("Invalid LightRAG port.")
    return port


def _is_placeholder_image(image: str) -> bool:
    if os.getenv("CE_DOMAIN_CONTROLLER_PLACEHOLDER", "").strip() == "1":
        return True
    normalized = image.strip().lower()
    return normalized in {PLACEHOLDER_IMAGE, "alpine", "alpine:latest"}


def _ensure_runtime_layout(runtime_dir: Path) -> None:
    (runtime_dir / "workspace").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "runtime-db").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "lightrag").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "secrets").mkdir(parents=True, exist_ok=True)


def _write_endpoint_record(runtime_dir: Path, *, runtime_name: str, port: int) -> None:
    # Private discovery aid for API/worker adapters — never a public DTO field.
    payload = {
        "baseUrl": f"http://{runtime_name}:{port}",
        "port": port,
        "healthPath": "/health",
    }
    (runtime_dir / ENDPOINT_RELATIVE).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _run_docker(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["docker", *args], text=True, capture_output=True, check=False)
    if check and result.returncode != 0:
        raise ControllerCommandError("Docker command failed.")
    return result


def _ensure_network(network: str) -> None:
    inspect = _run_docker(["network", "inspect", network], check=False)
    if inspect.returncode == 0:
        return
    # Private domain network: no host-published ports, but allow provider egress
    # for sealed embedding/extraction calls (OpenAI). Do not create --internal.
    created = _run_docker(["network", "create", network], check=False)
    if created.returncode != 0:
        # Race: another worker may have created it.
        inspect_again = _run_docker(["network", "inspect", network], check=False)
        if inspect_again.returncode != 0:
            raise ControllerCommandError("Docker command failed.")


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


def _probe_private_health(runtime_name: str, port: int) -> bool:
    """Probe /health inside the container (no host publish required)."""
    script = (
        "import urllib.request; "
        f"urllib.request.urlopen('http://127.0.0.1:{port}/health', timeout=2).read()"
    )
    result = _run_docker(["exec", runtime_name, "python", "-c", script], check=False)
    return result.returncode == 0


def handle_action(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action not in _ACTIONS or payload.get("action") != action:
        raise ControllerCommandError("Invalid runtime controller action.")
    runtime_dir = _runtime_dir(payload)
    runtime_name = _runtime_name(payload)
    image = _controller_image()
    placeholder = _is_placeholder_image(image)
    port = _controller_port()
    network = _controller_network()

    if action == "provision":
        _ensure_runtime_layout(runtime_dir)
        if not placeholder:
            _write_endpoint_record(runtime_dir, runtime_name=runtime_name, port=port)
        return {}

    if action == "health":
        container = _inspect(runtime_name)
        base_ok = bool(
            container
            and _labels_match(container, payload)
            and _is_running(container)
            and _has_no_host_ports(container)
        )
        if not base_ok:
            return {"healthy": False}
        if placeholder:
            return {"healthy": True}
        healthy = _probe_private_health(runtime_name, port)
        return {"healthy": healthy}

    if action == "start":
        _ensure_runtime_layout(runtime_dir)
        if not placeholder:
            _ensure_network(network)
            _write_endpoint_record(runtime_dir, runtime_name=runtime_name, port=port)
        container = _inspect(runtime_name)
        if container is not None:
            if not _labels_match(container, payload):
                raise ControllerCommandError("Runtime container name is already in use.")
            if not _is_running(container):
                _run_docker(["start", runtime_name])
            return {}
        if placeholder:
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
                network,
                "--mount",
                f"type=bind,src={runtime_dir},dst=/ce-runtime",
                "-e",
                "HOST=0.0.0.0",
                "-e",
                f"PORT={port}",
                "-e",
                "WORKING_DIR=/ce-runtime/lightrag",
                "-e",
                "WHITELIST_PATHS=/health,/api/*",
                image,
                "python",
                "-m",
                "context_engine.tools.lightrag_domain_entrypoint",
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


def write_sealed_provider_env(runtime_dir: Path, env_body: str) -> Path:
    """Write mode-600 sealed provider env under the domain runtime mount (KTD5)."""
    secrets_dir = runtime_dir / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    target = runtime_dir / SECRETS_RELATIVE
    target.write_text(env_body, encoding="utf-8")
    os.chmod(target, 0o600)
    return target


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
