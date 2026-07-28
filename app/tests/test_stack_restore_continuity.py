"""P12-04 U3 — unit proofs for drill seed plan + R13 continuity helpers."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.stack_drill_seed import (
    FORBIDDEN_ANSWER_TEXT,
    ORIGINAL_BYTES,
    PREVIEW_BYTES,
    build_seed_plan,
    expected_audit_rows,
    main as seed_main,
    object_put_plan,
)
from scripts.stack_pg_object_refs_census import DocumentObjectRefs, build_census_refs
from scripts.stack_restore_continuity import (
    LOGIN_PATH_DOCUMENTED,
    audit_ordered_digest,
    check_audit_continuity,
    check_invalid_ref_denied,
    check_preview_range,
    check_preview_reuses_original_census_edge,
    check_redaction_omission,
    check_tombstone_or_fenced_delete,
    main as continuity_main,
    run_continuity_checks,
)


def test_seed_plan_is_synthetic_and_finish_before_fence_documented() -> None:
    plan = build_seed_plan()
    public = plan.to_public_dict()
    assert plan.marker == "p12_04_drill"
    assert public["redacted_turn"]["assistant_answer"] is None
    assert public["redacted_turn"]["forbidden_answer_text"] == FORBIDDEN_ANSWER_TEXT
    assert any("finish" in note.lower() and "fence" in note.lower() for note in plan.notes)
    puts = object_put_plan(plan)
    assert {row["key"] for row in puts} == {put.key for put in plan.object_puts}
    # No raw object bytes in public plan JSON
    serialized = json.dumps(public)
    assert "%PDF" not in serialized
    assert FORBIDDEN_ANSWER_TEXT in serialized  # known probe string for fail-closed tests


def test_seed_plan_only_cli(tmp_path: Path) -> None:
    out = tmp_path / "plan.json"
    assert seed_main(["--plan-only", "--output", str(out)]) == 0
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["domain_id"] == "domain_drill_continuity"
    assert loaded["prepared_source"]["preview_state"] == "ready"


def test_redaction_fail_closed_when_answer_reappears() -> None:
    ok = check_redaction_omission(
        {
            "public_ref": "turn_drill_redacted",
            "status": "redacted",
            "assistant_answer": None,
            "user_message": "ok",
        }
    )
    assert ok.ok is True

    leaked = check_redaction_omission(
        {
            "public_ref": "turn_drill_redacted",
            "status": "redacted",
            "assistant_answer": FORBIDDEN_ANSWER_TEXT,
        }
    )
    assert leaked.ok is False
    assert leaked.detail in {"assistant_answer_present", "forbidden_answer_reappeared"}

    nested = check_redaction_omission(
        {
            "public_ref": "turn_drill_redacted",
            "status": "redacted",
            "assistant_answer": None,
            "debug": {"replay": FORBIDDEN_ANSWER_TEXT},
        }
    )
    assert nested.ok is False
    assert nested.detail == "forbidden_answer_reappeared"


def test_audit_digest_stable() -> None:
    rows = expected_audit_rows()
    digest_a = audit_ordered_digest(rows)
    digest_b = audit_ordered_digest(list(reversed(rows)))
    # Digest is order-sensitive on the provided sequence; continuity uses ordered SQL.
    assert digest_a != digest_b
    ordered = sorted(rows, key=lambda r: (r["created_at"], r["request_id"]))
    assert audit_ordered_digest(ordered) == audit_ordered_digest(ordered)
    result = check_audit_continuity(ordered)
    assert result.ok is True
    assert "digest=" in result.detail

    mutated = [dict(ordered[0]), *ordered[1:]]
    mutated[0]["outcome"] = "failed"
    assert check_audit_continuity(mutated).ok is False


def test_preview_reuses_original_edge() -> None:
    plan = build_seed_plan(preview_reuses_original=True)
    src = plan.prepared_source
    docs = [
        DocumentObjectRefs(
            original_object_key=src.original_object_key,
            original_sha256=src.original_sha256,
            original_size_bytes=src.original_size_bytes,
            preview_object_key=src.preview_object_key,
            preview_sha256=src.preview_sha256,
            preview_size_bytes=src.preview_size_bytes,
            preview_page_map_object_key=src.preview_page_map_object_key,
            preview_page_map_sha256=src.preview_page_map_sha256,
            preview_reuses_original=True,
        )
    ]
    refs = build_census_refs(docs)
    keys = [row["key"] for row in refs]
    assert keys.count(src.original_object_key) == 1
    assert src.preview_object_key == src.original_object_key
    assert check_preview_reuses_original_census_edge(docs).ok is True

    # Distinct preview path still fine.
    distinct = build_seed_plan(preview_reuses_original=False).prepared_source
    docs2 = [
        DocumentObjectRefs(
            original_object_key=distinct.original_object_key,
            original_sha256=distinct.original_sha256,
            preview_object_key=distinct.preview_object_key,
            preview_sha256=distinct.preview_sha256,
            preview_reuses_original=False,
            preview_page_map_object_key=distinct.preview_page_map_object_key,
            preview_page_map_sha256=distinct.preview_page_map_sha256,
        )
    ]
    assert check_preview_reuses_original_census_edge(docs2).ok is True


def test_invalid_ref_denied() -> None:
    assert check_invalid_ref_denied(
        denied=True,
        error_code="composer_ref_unavailable",
    ).ok is True
    assert check_invalid_ref_denied(denied=False).ok is False
    assert check_invalid_ref_denied(
        denied=True,
        error_code="composer_ref_unavailable",
        raw_token_leaked=True,
    ).ok is False
    assert check_invalid_ref_denied(
        denied=True,
        error_code="other_error",
    ).ok is False


def test_preview_range_missing_fails_when_seeded() -> None:
    assert check_preview_range(seeded=False, preview_bytes=None).ok is True
    assert check_preview_range(seeded=True, preview_bytes=None).ok is False
    assert check_preview_range(
        seeded=True,
        preview_bytes=PREVIEW_BYTES,
        range_bytes=PREVIEW_BYTES[0:4],
        range_start=0,
        range_end=3,
    ).ok is True
    assert check_preview_range(
        seeded=True,
        preview_bytes=ORIGINAL_BYTES,
        expected_prefix=b"%PDF-",
    ).ok is True


def test_tombstone_signal() -> None:
    assert check_tombstone_or_fenced_delete(seeded=False).ok is True
    assert check_tombstone_or_fenced_delete(
        seeded=True,
        source_state="deleting",
    ).ok is True
    assert check_tombstone_or_fenced_delete(
        seeded=True,
        content_error_code="document_not_found",
    ).ok is True
    assert check_tombstone_or_fenced_delete(
        seeded=True,
        source_state="prepared",
    ).ok is False


def test_run_continuity_checks_happy_and_redaction_cli_fail(tmp_path: Path) -> None:
    plan = build_seed_plan()
    results = run_continuity_checks(
        turn_projection={
            "public_ref": plan.redacted_turn.public_ref,
            "status": "redacted",
            "assistant_answer": None,
        },
        invalid_ref_denied=True,
        invalid_ref_error_code="composer_ref_unavailable",
        audit_rows=expected_audit_rows(plan),
        preview_seeded=True,
        preview_bytes=PREVIEW_BYTES,
        tombstone_seeded=True,
        tombstone_state="deleting",
    )
    assert all(r.ok for r in results)
    assert "CSRF" in LOGIN_PATH_DOCUMENTED or "login" in LOGIN_PATH_DOCUMENTED.lower()

    bad = {
        "turn": {
            "public_ref": plan.redacted_turn.public_ref,
            "status": "redacted",
            "assistant_answer": FORBIDDEN_ANSWER_TEXT,
        },
        "audit_rows": expected_audit_rows(plan),
        "invalid_ref_denied": True,
        "invalid_ref_error_code": "composer_ref_unavailable",
        "preview_seeded": True,
        "preview_bytes_hex": PREVIEW_BYTES.hex(),
        "tombstone_seeded": True,
        "tombstone_state": "deleting",
    }
    fixture = tmp_path / "bad-continuity.json"
    fixture.write_text(json.dumps(bad), encoding="utf-8")
    assert continuity_main(["--fixture-json", str(fixture)]) == 2


def test_continuity_cli_happy_fixture(tmp_path: Path) -> None:
    plan = build_seed_plan()
    fixture = {
        "turn": {
            "public_ref": plan.redacted_turn.public_ref,
            "status": "redacted",
            "assistant_answer": None,
        },
        "audit_rows": expected_audit_rows(plan),
        "invalid_ref_denied": True,
        "invalid_ref_error_code": "composer_ref_unavailable",
        "preview_seeded": True,
        "preview_bytes_hex": PREVIEW_BYTES.hex(),
        "tombstone_seeded": True,
        "tombstone_state": "deleting",
    }
    path = tmp_path / "ok-continuity.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    assert continuity_main(["--fixture-json", str(path)]) == 0


def test_continuity_cli_requires_fixture_or_database() -> None:
    assert continuity_main([]) == 2
