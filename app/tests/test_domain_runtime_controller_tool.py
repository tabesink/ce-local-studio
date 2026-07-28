from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from context_engine.tools import domain_runtime_controller as tool


def _payload(runtime_dir: Path, *, domain_id: str = "domain-a") -> dict[str, Any]:
    instance = runtime_dir.name
    return {
        "action": "start",
        "domainId": domain_id,
        "runtimeInstanceId": instance,
        "runtimeName": f"ce_domain_{domain_id}_{instance[:12]}",
        "runtimeDir": str(runtime_dir),
        "operationKey": "op-1",
        "controlGeneration": 1,
    }


def _prepare_runtime_dir(tmp_path: Path, domain_id: str = "domain-a") -> Path:
    instance = str(uuid4())
    runtime_dir = tmp_path / domain_id / instance
    runtime_dir.mkdir(parents=True)
    return runtime_dir


def test_placeholder_start_uses_network_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = _prepare_runtime_dir(tmp_path)
    calls: list[list[str]] = []

    def _fake_docker(args: list[str], *, check: bool = True):
        calls.append(args)
        if args[:1] == ["inspect"]:
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setenv("CE_DOMAIN_CONTROLLER_IMAGE", "alpine:3.20")
    monkeypatch.setattr(tool, "_run_docker", _fake_docker)

    payload = _payload(runtime_dir)
    payload["action"] = "start"
    result = tool.handle_action("start", payload)
    assert result == {}
    run_args = next(args for args in calls if args[:1] == ["run"])
    assert "--network" in run_args
    assert run_args[run_args.index("--network") + 1] == "none"
    assert "sleep 3600" in " ".join(run_args)


def test_real_start_uses_private_network_and_entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = _prepare_runtime_dir(tmp_path)
    calls: list[list[str]] = []

    def _fake_docker(args: list[str], *, check: bool = True):
        calls.append(args)
        if args[:2] == ["network", "inspect"]:
            return type("R", (), {"returncode": 0, "stdout": "[]", "stderr": ""})()
        if args[:1] == ["inspect"]:
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setenv("CE_DOMAIN_CONTROLLER_IMAGE", "context-engine:live")
    monkeypatch.setenv("CE_DOMAIN_CONTROLLER_NETWORK", "ce-domain-runtimes")
    monkeypatch.setenv("CE_DOMAIN_LIGHTRAG_PORT", "9621")
    monkeypatch.setattr(tool, "_run_docker", _fake_docker)

    payload = _payload(runtime_dir)
    payload["action"] = "start"
    tool.handle_action("start", payload)

    run_args = next(args for args in calls if args[:1] == ["run"])
    assert run_args[run_args.index("--network") + 1] == "ce-domain-runtimes"
    assert "context_engine.tools.lightrag_domain_entrypoint" in run_args
    assert "-p" not in run_args
    endpoint = json.loads((runtime_dir / "endpoint.json").read_text(encoding="utf-8"))
    assert endpoint["baseUrl"].startswith("http://ce_domain_")
    assert endpoint["port"] == 9621
    assert endpoint["healthPath"] == "/health"


def test_real_health_requires_private_endpoint_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = _prepare_runtime_dir(tmp_path)
    payload = _payload(runtime_dir)
    payload["action"] = "health"
    runtime_name = payload["runtimeName"]

    container = {
        "Config": {"Labels": {tool.DOMAIN_LABEL: payload["domainId"], tool.INSTANCE_LABEL: payload["runtimeInstanceId"]}},
        "State": {"Running": True},
        "NetworkSettings": {"Ports": {}},
    }

    def _fake_docker(args: list[str], *, check: bool = True):
        if args[:1] == ["inspect"]:
            return type("R", (), {"returncode": 0, "stdout": json.dumps([container]), "stderr": ""})()
        if args[:1] == ["exec"]:
            assert args[1] == runtime_name
            assert "127.0.0.1:9621/health" in args[-1]
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": "refused"})()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setenv("CE_DOMAIN_CONTROLLER_IMAGE", "context-engine:live")
    monkeypatch.setattr(tool, "_run_docker", _fake_docker)

    assert tool.handle_action("health", payload) == {"healthy": False}

    def _healthy_exec(args: list[str], *, check: bool = True):
        if args[:1] == ["inspect"]:
            return type("R", (), {"returncode": 0, "stdout": json.dumps([container]), "stderr": ""})()
        if args[:1] == ["exec"]:
            return type("R", (), {"returncode": 0, "stdout": b'{"status":"healthy"}', "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(tool, "_run_docker", _healthy_exec)
    assert tool.handle_action("health", payload) == {"healthy": True}


def test_write_sealed_provider_env_is_mode_600(tmp_path: Path) -> None:
    runtime_dir = _prepare_runtime_dir(tmp_path)
    path = tool.write_sealed_provider_env(runtime_dir, "EMBEDDING_BINDING=openai\n")
    assert path.is_file()
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600
    assert "EMBEDDING_BINDING=openai" in path.read_text(encoding="utf-8")


def test_entrypoint_rejects_world_readable_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from context_engine.tools import lightrag_domain_entrypoint as entry

    secrets = tmp_path / "secrets"
    secrets.mkdir()
    sealed = secrets / "provider.env"
    sealed.write_text("FOO=bar\n", encoding="utf-8")
    sealed.chmod(0o644)

    monkeypatch.setattr(entry, "RUNTIME_ROOT", tmp_path)
    monkeypatch.setattr(entry, "SECRETS_FILE", sealed)
    monkeypatch.setattr(entry, "WORKING_DIR", tmp_path / "lightrag")

    with pytest.raises(SystemExit) as raised:
        entry._load_sealed_env()
    assert raised.value.code == 1
