"""P12-07 U4: gated @release capacity probe contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "app" / "scripts" / "p12_07_release_capacity_probe.py"
CHECKLIST = ROOT / "docs" / "_scratch" / "p12-07-release-evidence-checklist.md"
VERIFY = ROOT / "scripts" / "verify.sh"
PACKAGE = ROOT / "app" / "client" / "package.json"
RELEASE_SPEC = ROOT / "app" / "client" / "tests" / "e2e" / "release-capacity.spec.ts"


def test_probe_refuses_without_gate() -> None:
    env = {**os.environ, "CE_P12_07_RELEASE": ""}
    env.pop("CE_P12_07_RELEASE", None)
    completed = subprocess.run(
        [sys.executable, str(PROBE), "check"],
        check=False,
        capture_output=True,
        text=True,
        env={k: v for k, v in env.items() if k != "CE_P12_07_RELEASE"},
    )
    assert completed.returncode == 2
    assert "gate_refused" in completed.stderr
    assert "CE_P12_07_RELEASE=1" in completed.stderr


def test_probe_check_and_unit_with_gate() -> None:
    env = {**os.environ, "CE_P12_07_RELEASE": "1"}
    check = subprocess.run(
        [sys.executable, str(PROBE), "check"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert check.returncode == 0, check.stderr
    payload = json.loads(check.stdout)
    assert payload["budgets"]["graphWaitQueueDepth"] == 0

    unit = subprocess.run(
        [sys.executable, str(PROBE), "unit"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert unit.returncode == 0, unit.stderr
    result = json.loads(unit.stdout)
    assert result["Lplus1"]["code"] == "capacity_unavailable"
    assert result["Lplus1"]["shedMs"] <= 1000
    assert result["runtimeCallsDuringShed"] == 1
    assert result["recovery"] == "ok"


def test_release_lane_not_in_default_verify() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    assert "p12_07_release_capacity_probe" not in text
    assert "CE_P12_07_RELEASE" not in text
    assert "test:e2e:release" not in text


def test_release_artifacts_and_scripts_exist() -> None:
    assert CHECKLIST.is_file()
    assert "CE_P12_07_RELEASE=1" in CHECKLIST.read_text(encoding="utf-8")
    assert RELEASE_SPEC.is_file()
    spec = RELEASE_SPEC.read_text(encoding="utf-8")
    assert "@release" in spec
    assert "CE_P12_07_RELEASE" in spec
    package = PACKAGE.read_text(encoding="utf-8")
    assert "test:e2e:release" in package
    assert "--grep @release" in package
