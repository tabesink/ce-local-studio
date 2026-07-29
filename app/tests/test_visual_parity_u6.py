"""P12-07 U6: visual parity manifest + a11y harness contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "app" / "scripts" / "verify_visual_parity_manifest.py"
MANIFEST = ROOT / "app" / "client" / "tests" / "e2e" / "visual-parity-manifest.json"
A11Y_SPEC = ROOT / "app" / "client" / "tests" / "e2e" / "a11y-golden-routes.spec.ts"
VISUAL_SPEC = ROOT / "app" / "client" / "tests" / "e2e" / "visual-matrix.spec.ts"
AT_EVIDENCE = ROOT / "docs" / "_scratch" / "p12-07-graph-assistive-technology-evidence.md"
PACKAGE = ROOT / "app" / "client" / "package.json"
VERIFY = ROOT / "scripts" / "verify.sh"


def test_manifest_check_passes_schema() -> None:
    completed = subprocess.run(
        [sys.executable, str(GATE), "check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["entries"] >= 8


def test_enforce_fails_closed_while_capture_required() -> None:
    completed = subprocess.run(
        [sys.executable, str(GATE), "enforce", "--lane", "pr-fast"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "capture_required" in completed.stderr


def test_a11y_and_visual_harness_wired() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    assert "@axe-core/playwright" in package.get("devDependencies", {})
    a11y = A11Y_SPEC.read_text(encoding="utf-8")
    assert "@pr-fast" in a11y
    assert "expectNoCriticalAxeViolations" in a11y
    assert "graph-workbench" in a11y
    visual = VISUAL_SPEC.read_text(encoding="utf-8")
    assert "toHaveScreenshot" in visual
    assert "visual-parity-manifest.json" in visual
    assert "maxDiffPixelRatio" in visual
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    graph = [e for e in manifest["entries"] if "database-visualize" in e["route"]]
    assert graph
    assert all(e["targetId"] == "graph-workbench" for e in graph)
    assert AT_EVIDENCE.is_file()
    at = AT_EVIDENCE.read_text(encoding="utf-8")
    assert "NO-GO" in at
    assert "NVDA" in at and "VoiceOver" in at


def test_visual_enforce_not_in_default_verify() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    assert "verify_visual_parity_manifest.py enforce" not in text
