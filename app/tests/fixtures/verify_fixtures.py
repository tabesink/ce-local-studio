#!/usr/bin/env python3
"""Hash/count/projection gate for seeded-demo fixtures (P12-07 U2)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent
FORBIDDEN_HASHES = {"", "*", "TBD", "tbd", "todo", "TODO"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    manifest_path = FIXTURES / "manifest.json"
    if not manifest_path.is_file():
        print("missing manifest.json", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(manifest.get("schemaVersion") or 0) < 1:
        print("invalid schemaVersion", file=sys.stderr)
        return 1
    if manifest.get("clock") != "2026-07-17T12:00:00Z":
        print("clock must be frozen at 2026-07-17T12:00:00Z", file=sys.stderr)
        return 1

    errors: list[str] = []
    entries = list(manifest.get("artifacts") or []) + list(manifest.get("expected") or [])
    if not entries:
        errors.append("manifest has no artifacts")

    for entry in entries:
        rel = entry.get("path")
        digest = str(entry.get("sha256") or "")
        if digest in FORBIDDEN_HASHES or digest.lower() == "tbd":
            errors.append(f"blank/wildcard/TBD hash for {rel}")
            continue
        path = FIXTURES / str(rel)
        if not path.is_file():
            errors.append(f"missing artifact {rel}")
            continue
        data = path.read_bytes()
        actual = _sha256(data)
        if actual != digest:
            errors.append(f"hash mismatch for {rel}")
        if int(entry.get("byteSize") or -1) != len(data):
            errors.append(f"byteSize mismatch for {rel}")

    graph_path = FIXTURES / "expected" / "graph" / "manuals.json"
    if graph_path.is_file():
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        snapshot = graph.get("graph_manuals_snapshot") or {}
        labels = {node.get("label") for node in snapshot.get("nodes") or []}
        if "Pump" not in labels or "Relief valve" not in labels:
            errors.append("graph snapshot missing Pump / Relief valve")
        if not snapshot.get("edges"):
            errors.append("graph snapshot missing connecting edge")
        if snapshot.get("truncated") is not False:
            errors.append("graph_manuals_snapshot.truncated must be false")
        raw_dump = json.dumps(graph).lower()
        for banned in ("properties", "/v1/graph", "lightrag", "chunk_id", "working_dir"):
            if banned in raw_dump:
                errors.append(f"forbidden token in graph expected: {banned}")
    else:
        errors.append("missing expected/graph/manuals.json")

    figure_path = FIXTURES / "expected" / "turn_mina_figure.json"
    if figure_path.is_file():
        figure = json.loads(figure_path.read_text(encoding="utf-8"))
        if figure.get("answer") != "The relief valve is downstream of the pump [1].":
            errors.append("figure answer constant mismatch")
    else:
        errors.append("missing expected/turn_mina_figure.json")

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    print(f"fixtures:verify ok ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
