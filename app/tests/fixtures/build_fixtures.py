#!/usr/bin/env python3
"""Deterministic seeded-demo fixture builder (P12-07 U2). Network-free."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from context_engine.adapters.preview_renderer import _assemble_pdf  # noqa: E402

FIXTURES = Path(__file__).resolve().parent
CLOCK = "2026-07-17T12:00:00Z"
SCHEMA_VERSION = 1


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pump_manual_pages() -> list[str]:
    pages: list[str] = []
    for index in range(1, 25):
        if index == 7:
            pages.append(
                "Page 7\nSection 2.1 Lockout\n"
                "Isolate electrical power before opening the service panel."
            )
        elif index == 12:
            pages.append(
                "Page 12\nTorque table\n"
                "M12 fasteners use the listed 80 N·m service torque."
            )
        elif index == 18:
            pages.append(
                "Page 18\nSection 4.2 Relief valve\n"
                "Figure 4 places the relief valve downstream of the pump."
            )
        elif index == 20:
            pages.append("Page 20\nThe inspection diagram is shown on this page.")
        else:
            pages.append(f"Page {index}\nSynthetic Equipment Manuals pump corpus.")
    return pages


def _safety_bulletin_pages() -> list[str]:
    return [
        "Page 1\nSafety bulletin overlapping pump and valve terms.",
        "Page 2\nRelief valve inspection reminder for operators.",
        "Page 3\nPump isolation checklist.",
    ]


def _leave_policy_pages() -> list[str]:
    return [f"Page {i}\nWorkplace leave policy synthetic text." for i in range(1, 6)]


def _service_notes_pages() -> list[str]:
    return ["Page 1\nService notes prepared but not indexed.", "Page 2\nAdmin lifecycle only."]


def _legacy_delete_pages() -> list[str]:
    return ["Page 1\nLegacy procedures content fenced during delete."]


def _write_bytes(path: Path, data: bytes, *, update: bool) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = _sha256(data)
    if path.exists() and not update:
        existing = path.read_bytes()
        if existing != data:
            raise SystemExit(
                f"Refusing to overwrite changed artifact {path.relative_to(FIXTURES)}; pass --update."
            )
    else:
        path.write_bytes(data)
    return {
        "path": str(path.relative_to(FIXTURES)).replace("\\", "/"),
        "sha256": digest,
        "byteSize": len(data),
        "mediaType": "application/pdf",
    }


def _graph_expected() -> dict[str, object]:
    return {
        "graph_manuals_snapshot": {
            "domain": {"ref": "domain_manuals", "name": "Equipment Manuals"},
            "nodes": [
                {
                    "ref": "gn_fixture_pump_manuals_0001",
                    "label": "Pump",
                    "kind": "equipment",
                    "degree": 1,
                },
                {
                    "ref": "gn_fixture_relief_manuals_0001",
                    "label": "Relief valve",
                    "kind": "equipment",
                    "degree": 1,
                },
            ],
            "edges": [
                {
                    "ref": "ge_fixture_pump_relief_0001",
                    "sourceRef": "gn_fixture_pump_manuals_0001",
                    "targetRef": "gn_fixture_relief_manuals_0001",
                    "label": "feeds",
                }
            ],
            "truncated": False,
        },
        "graph_label_relief_valve": {
            "items": [
                {
                    "nodeRef": "gn_fixture_relief_manuals_0001",
                    "label": "Relief valve",
                    "kind": "equipment",
                }
            ]
        },
        "graph_manuals_empty": {
            "domain": {"ref": "domain_manuals", "name": "Equipment Manuals"},
            "nodes": [],
            "edges": [],
            "truncated": False,
        },
        "figure_answer": "The relief valve is downstream of the pump [1].",
    }


def build(*, update: bool) -> dict[str, object]:
    documents: list[dict[str, object]] = []
    specs = [
        ("documents/doc_pump_manual.pdf", _pump_manual_pages(), "doc_pump_manual", 24, ["M-04", "M-05", "M-15"]),
        ("documents/doc_safety_bulletin.pdf", _safety_bulletin_pages(), "doc_safety_bulletin", 3, ["M-04"]),
        ("documents/doc_service_notes.pdf", _service_notes_pages(), "doc_service_notes", 2, ["A-07"]),
        ("documents/doc_leave_policy.pdf", _leave_policy_pages(), "doc_leave_policy", 5, ["M-02"]),
        ("documents/doc_legacy_delete.pdf", _legacy_delete_pages(), "doc_legacy_delete", 1, ["A-10"]),
        ("documents/doc_service_notes.md", None, "doc_service_notes_md", None, ["R9"]),
    ]

    for rel, pages, key, page_count, cases in specs:
        path = FIXTURES / rel
        if pages is None:
            data = (
                "# Service notes (markdown)\n\n"
                "Synthetic non-PDF source for R9 governed preview coverage.\n"
            ).encode("utf-8")
            meta = _write_bytes(path, data, update=update)
            meta["mediaType"] = "text/markdown"
            meta["pageCount"] = None
        else:
            data = _assemble_pdf(pages)
            meta = _write_bytes(path, data, update=update)
            meta["pageCount"] = page_count
            # Preview bytes currently equal source PDF for synthetic PDF fixtures.
            preview_path = FIXTURES / "previews" / Path(rel).name
            preview_meta = _write_bytes(preview_path, data, update=update)
            meta["preview"] = preview_meta
        meta["fixtureKey"] = key
        meta["dependentCaseIds"] = cases
        documents.append(meta)

    expected = _graph_expected()
    expected_path = FIXTURES / "expected" / "graph" / "manuals.json"
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    expected_bytes = (json.dumps(expected, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if expected_path.exists() and not update and expected_path.read_bytes() != expected_bytes:
        raise SystemExit("Refusing to overwrite changed expected/graph/manuals.json; pass --update.")
    expected_path.write_bytes(expected_bytes)

    figure_path = FIXTURES / "expected" / "turn_mina_figure.json"
    figure_body = {
        "answer": expected["figure_answer"],
        "citation": "[1]",
        "evidenceFixtureKey": "ev_mina_figure_valve",
        "clock": CLOCK,
    }
    figure_bytes = (json.dumps(figure_body, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if figure_path.exists() and not update and figure_path.read_bytes() != figure_bytes:
        raise SystemExit("Refusing to overwrite changed expected/turn_mina_figure.json; pass --update.")
    figure_path.write_bytes(figure_bytes)

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "clock": CLOCK,
        "generator": "app/tests/fixtures/build_fixtures.py",
        "artifacts": documents,
        "expected": [
            {
                "path": "expected/graph/manuals.json",
                "sha256": _sha256(expected_bytes),
                "byteSize": len(expected_bytes),
                "fixtureKey": "graph_manuals_expected",
                "dependentCaseIds": ["M-14", "M-15", "E2E-M15"],
            },
            {
                "path": "expected/turn_mina_figure.json",
                "sha256": _sha256(figure_bytes),
                "byteSize": len(figure_bytes),
                "fixtureKey": "turn_mina_figure_expected",
                "dependentCaseIds": ["M-04", "M-05"],
            },
        ],
    }
    manifest_path = FIXTURES / "manifest.json"
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic Context Engine fixtures.")
    parser.add_argument("--update", action="store_true", help="Allow overwriting changed artifacts.")
    args = parser.parse_args(argv)
    manifest = build(update=args.update)
    print(f"Wrote {len(manifest['artifacts'])} document artifacts and manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
