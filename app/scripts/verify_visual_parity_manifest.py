#!/usr/bin/env python3
"""P12-07 U6 visual parity manifest gate.

Modes:
  check    — schema + path shape only (safe for default verify / unit tests)
  enforce  — every requested lane entry must be approvalStatus=approved with PNG present

Usage:
  python app/scripts/verify_visual_parity_manifest.py check
  python app/scripts/verify_visual_parity_manifest.py enforce --lane pr-fast
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "app" / "client" / "tests" / "e2e" / "visual-parity-manifest.json"
BASE_DIR = ROOT / "app" / "client" / "tests" / "e2e"
ALLOWED_STATUS = frozenset({"approved", "capture_required", "diverged_approved"})
ALLOWED_LANES = frozenset({"pr-fast", "release"})


def _fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def validate_schema(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schemaVersion") != "1.0":
        errors.append("schemaVersion must be '1.0'")
    if not isinstance(manifest.get("maxDiffPixelRatio"), (int, float)):
        errors.append("maxDiffPixelRatio required")
    elif float(manifest["maxDiffPixelRatio"]) > 0.005 + 1e-9:
        errors.append("maxDiffPixelRatio must be <= 0.005")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty list")
        return errors
    ids: set[str] = set()
    for entry in entries:
        eid = entry.get("id")
        if not eid or eid in ids:
            errors.append(f"duplicate or missing id: {eid!r}")
        ids.add(eid)
        if entry.get("lane") not in ALLOWED_LANES:
            errors.append(f"{eid}: invalid lane")
        if entry.get("approvalStatus") not in ALLOWED_STATUS:
            errors.append(f"{eid}: invalid approvalStatus")
        ratio = entry.get("maxDiffPixelRatio", manifest.get("maxDiffPixelRatio"))
        if float(ratio) > 0.005 + 1e-9:
            errors.append(f"{eid}: maxDiffPixelRatio > 0.005")
        path = entry.get("expectedPath")
        if not path or Path(path).is_absolute() or ".." in Path(path).parts:
            errors.append(f"{eid}: expectedPath must be relative under tests/e2e")
        vp = entry.get("viewport") or {}
        if not isinstance(vp.get("width"), int) or not isinstance(vp.get("height"), int):
            errors.append(f"{eid}: viewport width/height required")
        if "graph" in str(entry.get("route", "")) and entry.get("targetId") != "graph-workbench":
            errors.append(f"{eid}: graph route must cite targetId graph-workbench")
    return errors


def enforce(manifest: dict[str, Any], lane: str | None) -> list[str]:
    errors: list[str] = []
    for entry in manifest["entries"]:
        if lane and entry.get("lane") != lane:
            continue
        eid = entry["id"]
        status = entry.get("approvalStatus")
        if status != "approved" and status != "diverged_approved":
            errors.append(f"{eid}: approvalStatus={status!r} (capture_required fails closed)")
            continue
        png = BASE_DIR / entry["expectedPath"]
        if not png.is_file() or png.stat().st_size < 32:
            errors.append(f"{eid}: missing or empty baseline {png}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "enforce"))
    parser.add_argument("--lane", choices=sorted(ALLOWED_LANES), default=None)
    args = parser.parse_args(argv)

    if not MANIFEST.is_file():
        return _fail(f"missing manifest {MANIFEST}")
    try:
        manifest = load_manifest()
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")

    schema_errors = validate_schema(manifest)
    if schema_errors:
        for err in schema_errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1

    if args.mode == "check":
        print(json.dumps({"ok": True, "entries": len(manifest["entries"])}, indent=2))
        return 0

    enforce_errors = enforce(manifest, args.lane)
    if enforce_errors:
        for err in enforce_errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 2

    print(json.dumps({"ok": True, "mode": "enforce", "lane": args.lane}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
