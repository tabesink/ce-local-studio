"""P10-05 U4: staging smoke refuses without gate; adapters mode stays network-free."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "provider_staging_smoke.py"
APP_ROOT = Path(__file__).resolve().parents[1]


def _run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    # Strip gate/credentials from parent unless explicitly provided.
    for key in (
        "CE_PROVIDER_STAGING_SMOKE",
        "CE_PROVIDER_STAGING_PROFILE",
        "CE_REDUCTO_API_KEY",
        "REDUCTO_API_KEY",
        "CE_OPENAI_API_KEY",
        "OPENAI_API_KEY",
    ):
        merged.pop(key, None)
    merged.update(env)
    merged["PYTHONPATH"] = str(APP_ROOT) + (
        os.pathsep + merged["PYTHONPATH"] if merged.get("PYTHONPATH") else ""
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(APP_ROOT),
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


def test_smoke_refuses_without_gate_env_before_network() -> None:
    result = _run({}, "--mode", "check", "--profile", "docling")
    assert result.returncode != 0
    assert "gate_refused" in result.stderr
    assert "CE_PROVIDER_STAGING_SMOKE=1" in result.stderr


def test_smoke_refuses_unknown_profile() -> None:
    result = _run(
        {"CE_PROVIDER_STAGING_SMOKE": "1"},
        "--mode",
        "check",
        "--profile",
        "anthropic",
    )
    assert result.returncode != 0
    assert "profile_refused" in result.stderr


def test_smoke_check_ok_with_gate_and_profile() -> None:
    result = _run(
        {"CE_PROVIDER_STAGING_SMOKE": "1", "CE_OBJECT_STORE_KIND": "filesystem"},
        "--mode",
        "check",
        "--profile",
        "docling",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "gate_ok"
    assert payload["productionObjectStoreClaim"] is False


def test_smoke_live_refuses_without_openai_credential() -> None:
    result = _run(
        {"CE_PROVIDER_STAGING_SMOKE": "1"},
        "--mode",
        "live",
        "--profile",
        "openai-embedding",
        "--env-file",
        str(APP_ROOT / ".env.stack.example"),
    )
    assert result.returncode != 0
    assert "credential_refused" in result.stderr


def test_smoke_live_accepts_openai_from_env_file(tmp_path: Path) -> None:
    env_path = tmp_path / "keys.env"
    secret = "test-openai-key-not-for-network"
    env_path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
    result = _run(
        {"CE_PROVIDER_STAGING_SMOKE": "1"},
        "--mode",
        "live",
        "--profile",
        "openai-embedding",
        "--env-file",
        str(env_path),
    )
    # Credential gate must pass; live may still fail at network boundary.
    assert "credential_refused" not in result.stderr
    assert secret not in result.stdout
    assert secret not in result.stderr
    if result.returncode != 0:
        assert "live_failed" in result.stderr or "adapter_failed" in result.stderr


def test_smoke_live_accepts_reducto_from_env_file(tmp_path: Path) -> None:
    env_path = tmp_path / "keys.env"
    secret = "test-reducto-key-not-for-network"
    env_path.write_text(f"REDUCTO_API_KEY={secret}\n", encoding="utf-8")
    result = _run(
        {"CE_PROVIDER_STAGING_SMOKE": "1"},
        "--mode",
        "live",
        "--profile",
        "reducto",
        "--env-file",
        str(env_path),
    )
    assert "credential_refused" not in result.stderr
    assert secret not in result.stdout
    assert secret not in result.stderr
    if result.returncode != 0:
        assert "live_failed" in result.stderr or "adapter_failed" in result.stderr


def test_smoke_env_file_merge_preserves_process_env(tmp_path: Path) -> None:
    env_path = tmp_path / "keys.env"
    env_path.write_text("OPENAI_API_KEY=from-file-should-not-win\n", encoding="utf-8")
    process_secret = "from-process-env-wins"
    result = _run(
        {"CE_PROVIDER_STAGING_SMOKE": "1", "OPENAI_API_KEY": process_secret},
        "--mode",
        "live",
        "--profile",
        "openai-embedding",
        "--env-file",
        str(env_path),
    )
    assert "credential_refused" not in result.stderr
    assert "from-file-should-not-win" not in result.stdout
    assert "from-file-should-not-win" not in result.stderr
    assert process_secret not in result.stdout
    assert process_secret not in result.stderr


def test_smoke_missing_env_file_soft_skips() -> None:
    missing = APP_ROOT / ".no-such-env-file-for-smoke-test"
    assert not missing.exists()
    result = _run(
        {"CE_PROVIDER_STAGING_SMOKE": "1"},
        "--mode",
        "check",
        "--profile",
        "docling",
        "--env-file",
        str(missing),
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "gate_ok"


def test_smoke_adapters_matrix_fixture_proofs() -> None:
    result = _run(
        {"CE_PROVIDER_STAGING_SMOKE": "1"},
        "--mode",
        "adapters",
        "--profile",
        "matrix",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "adapters_ok"
    kinds = {item["kind"] for item in payload["proofs"]}
    assert "docling" in kinds
    assert "reducto" in kinds
    assert "openai-embedding" in kinds
    assert "openai-synthesis" in kinds
