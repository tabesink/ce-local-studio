from __future__ import annotations

import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from context_engine.adapters.domain_runtime_controller import (
    CONTROLLER_OUTCOME_FAILED,
    CONTROLLER_OUTCOME_SUCCEEDED,
    CONTROLLER_OUTCOME_UNCERTAIN,
    DockerDomainRuntimeController,
    DomainControllerError,
    LocalDomainRuntimeController,
    controller_from_settings,
)
from context_engine.config import Settings
from context_engine.models import DOMAIN_STATE_STOPPED, Domain


def _domain() -> Domain:
    return Domain(
        id="domain-manuals",
        display_name="Equipment Manuals",
        state=DOMAIN_STATE_STOPPED,
        embedding_profile_id="openai-embedding-default",
        runtime_instance_id=str(uuid4()),
        control_generation=2,
        version=1,
    )


def test_local_controller_lifecycle_records_operation_key(tmp_path: Path) -> None:
    settings = Settings(testing=True, domain_runtime_root=str(tmp_path / "runtimes"), domain_runtime_controller_kind="local")
    controller = LocalDomainRuntimeController(settings)
    domain = _domain()

    provisioned = controller.provision(domain, operation_key="op-create-1", control_generation=1)
    assert provisioned.outcome == CONTROLLER_OUTCOME_SUCCEEDED

    started = controller.start(domain, operation_key="op-start-2", control_generation=2)
    assert started.outcome == CONTROLLER_OUTCOME_SUCCEEDED
    runtime_dir = controller.runtime_dir(domain.id, domain.runtime_instance_id)
    record = json.loads((runtime_dir / "runtime.json").read_text(encoding="utf-8"))
    assert record["operationKey"] == "op-start-2"
    assert record["controlGeneration"] == 2
    assert controller.health(domain).healthy is True

    stopped = controller.stop(domain, operation_key="op-stop-3", control_generation=3)
    assert stopped.outcome == CONTROLLER_OUTCOME_SUCCEEDED
    assert controller.health(domain).healthy is False

    deleted = controller.delete(domain, operation_key="op-delete-4", control_generation=4)
    assert deleted.outcome == CONTROLLER_OUTCOME_SUCCEEDED
    assert not runtime_dir.exists()


def test_docker_controller_timeout_is_uncertain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        testing=True,
        domain_runtime_root=str(tmp_path / "runtimes"),
        domain_runtime_controller_kind="docker",
        domain_controller_command="fake-controller",
        domain_controller_timeout_seconds=1,
    )

    def _timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="fake-controller", timeout=1)

    monkeypatch.setattr(subprocess, "run", _timeout)
    result = DockerDomainRuntimeController(settings).start(
        _domain(),
        operation_key="op-timeout",
        control_generation=2,
    )
    assert result.outcome == CONTROLLER_OUTCOME_UNCERTAIN
    assert "timed out" in (result.message or "").lower()


def test_docker_controller_passes_stable_operation_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _run(cmd, *, input=None, **_kwargs):
        captured["cmd"] = cmd
        captured["payload"] = json.loads(input)
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"healthy": True}), stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    settings = Settings(
        testing=True,
        domain_runtime_root=str(tmp_path / "runtimes"),
        domain_runtime_controller_kind="docker",
        domain_controller_command="fake-controller",
        domain_controller_timeout_seconds=5,
    )
    controller = DockerDomainRuntimeController(settings)
    domain = _domain()
    result = controller.start(domain, operation_key="op-stable-key", control_generation=7)
    assert result.outcome == CONTROLLER_OUTCOME_SUCCEEDED
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["operationKey"] == "op-stable-key"
    assert payload["controlGeneration"] == 7
    assert payload["domainId"] == domain.id
    assert captured["cmd"][-1] == "start"


def test_docker_controller_hard_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _run(cmd, **_kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", _run)
    settings = Settings(
        testing=True,
        domain_runtime_root=str(tmp_path / "runtimes"),
        domain_runtime_controller_kind="docker",
        domain_controller_command="fake-controller",
        domain_controller_timeout_seconds=5,
    )
    result = DockerDomainRuntimeController(settings).stop(
        _domain(),
        operation_key="op-fail",
        control_generation=1,
    )
    assert result.outcome == CONTROLLER_OUTCOME_FAILED


def test_controller_from_settings_rejects_unknown_kind() -> None:
    settings = Settings(testing=True, domain_runtime_controller_kind="bogus")
    with pytest.raises(DomainControllerError):
        controller_from_settings(settings)
    local = controller_from_settings(Settings(testing=True, domain_runtime_controller_kind="local"))
    assert isinstance(local, LocalDomainRuntimeController)
