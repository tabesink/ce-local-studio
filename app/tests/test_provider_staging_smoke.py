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
    )
    assert result.returncode != 0
    assert "credential_refused" in result.stderr


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
