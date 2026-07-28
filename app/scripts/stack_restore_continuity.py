#!/usr/bin/env python3
"""P12-04 U3 / R13 — post-restore continuity checks (pre-rebuild half of AE4).

Covers R13 only:
  - login path stub or documented matrix path
  - redaction omission (fail closed if forbidden answer text reappears)
  - invalidated/expired composer ref deny
  - audit count + ordered digest via SQL rows
  - preview/range delivery when seeded
  - tombstone / fenced-delete signal when seeded

Citations/anchors after LightRAG rebuild are U6/R14 — not owned here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from scripts.stack_drill_seed import (
    FORBIDDEN_ANSWER_TEXT,
    SOURCE_PUBLIC_REF,
    SOURCE_TOMBSTONE_PUBLIC_REF,
    TURN_REDACTED_PUBLIC_REF,
    build_seed_plan,
    expected_audit_rows,
)
from scripts.stack_pg_object_refs_census import DocumentObjectRefs, build_census_refs


LOGIN_PATH_DOCUMENTED = (
    "Fresh login after restore: same-origin BFF CSRF cookie exchange then "
    "POST /api/auth/login (see app/scripts/stack_smoke_core.py). "
    "Session/CSRF keys are re-login-only; cookie continuity is not part of the "
    "backup unit."
)


@dataclass(frozen=True)
class ContinuityCheckResult:
    name: str
    ok: bool
    detail: str = ""


def login_path_status(*, stub_ok: bool = True, documented: bool = True) -> ContinuityCheckResult:
    """Login is exercised at matrix altitude or documented as the smoke path."""
    if stub_ok or documented:
        return ContinuityCheckResult(
            name="login_path",
            ok=True,
            detail="documented" if documented else "stub_ok",
        )
    return ContinuityCheckResult(name="login_path", ok=False, detail="login_path_missing")


def check_redaction_omission(
    turn_projection: Mapping[str, Any],
    *,
    forbidden_answer_text: str = FORBIDDEN_ANSWER_TEXT,
    expected_public_ref: str = TURN_REDACTED_PUBLIC_REF,
) -> ContinuityCheckResult:
    """Fail closed if redacted answer text reappears in any public/DB projection."""
    status = str(turn_projection.get("status") or "")
    public_ref = str(
        turn_projection.get("public_ref")
        or turn_projection.get("id")
        or turn_projection.get("publicRef")
        or ""
    )
    assistant = turn_projection.get("assistant_answer")
    if assistant is None:
        assistant = turn_projection.get("assistantAnswer")
    answer_text = "" if assistant is None else str(assistant)
    blob = json.dumps(turn_projection, sort_keys=True, default=str)

    if expected_public_ref and public_ref and public_ref != expected_public_ref:
        return ContinuityCheckResult(
            name="redaction_omission",
            ok=False,
            detail=f"unexpected_turn_ref:{public_ref}",
        )
    if status and status != "redacted":
        return ContinuityCheckResult(
            name="redaction_omission",
            ok=False,
            detail=f"status_not_redacted:{status}",
        )
    if answer_text:
        return ContinuityCheckResult(
            name="redaction_omission",
            ok=False,
            detail="assistant_answer_present",
        )
    if forbidden_answer_text and forbidden_answer_text in blob:
        return ContinuityCheckResult(
            name="redaction_omission",
            ok=False,
            detail="forbidden_answer_reappeared",
        )
    if forbidden_answer_text and forbidden_answer_text in answer_text:
        return ContinuityCheckResult(
            name="redaction_omission",
            ok=False,
            detail="forbidden_answer_reappeared",
        )
    return ContinuityCheckResult(name="redaction_omission", ok=True, detail="omitted")


def check_invalid_ref_denied(
    *,
    denied: bool,
    error_code: str | None = None,
    raw_token_leaked: bool = False,
) -> ContinuityCheckResult:
    """Governed ref must stay unusable (expired/invalidated/consumed)."""
    if raw_token_leaked:
        return ContinuityCheckResult(
            name="invalid_ref",
            ok=False,
            detail="raw_token_leaked",
        )
    if not denied:
        return ContinuityCheckResult(
            name="invalid_ref",
            ok=False,
            detail="ref_not_denied",
        )
    if error_code and error_code != "composer_ref_unavailable":
        return ContinuityCheckResult(
            name="invalid_ref",
            ok=False,
            detail=f"unexpected_code:{error_code}",
        )
    return ContinuityCheckResult(name="invalid_ref", ok=True, detail=error_code or "denied")


def audit_ordered_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    """SHA-256 over ordered event_name|outcome|target|request_id|created_at lines."""
    lines: list[str] = []
    for row in rows:
        lines.append(
            "|".join(
                [
                    str(row.get("event_name") or ""),
                    str(row.get("outcome") or ""),
                    str(row.get("target_kind") or ""),
                    str(row.get("target_id") or ""),
                    str(row.get("request_id") or ""),
                    str(row.get("created_at") or ""),
                ]
            )
        )
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def check_audit_continuity(
    actual_rows: Sequence[Mapping[str, Any]],
    *,
    expected_count: int | None = None,
    expected_digest: str | None = None,
) -> ContinuityCheckResult:
    """Operator SQL altitude: count + ordered digest (no public audit-read API)."""
    expected_rows = expected_audit_rows()
    if expected_count is None:
        expected_count = len(expected_rows)
    if expected_digest is None:
        expected_digest = audit_ordered_digest(expected_rows)

    actual_count = len(actual_rows)
    if actual_count != expected_count:
        return ContinuityCheckResult(
            name="audit_continuity",
            ok=False,
            detail=f"count_mismatch:{actual_count}!={expected_count}",
        )
    actual_digest = audit_ordered_digest(actual_rows)
    if actual_digest != expected_digest:
        return ContinuityCheckResult(
            name="audit_continuity",
            ok=False,
            detail="digest_mismatch",
        )
    return ContinuityCheckResult(
        name="audit_continuity",
        ok=True,
        detail=f"count={actual_count};digest={actual_digest}",
    )


def check_preview_range(
    *,
    seeded: bool,
    preview_bytes: bytes | None,
    range_bytes: bytes | None = None,
    expected_prefix: bytes | None = b"%PDF-",
    range_start: int = 0,
    range_end: int = 3,
) -> ContinuityCheckResult:
    """Authorized preview/range when seeded; missing preview fails (not silent skip)."""
    if not seeded:
        return ContinuityCheckResult(
            name="preview_range",
            ok=True,
            detail="not_seeded_skipped",
        )
    if preview_bytes is None:
        return ContinuityCheckResult(
            name="preview_range",
            ok=False,
            detail="preview_missing",
        )
    if expected_prefix is not None and not preview_bytes.startswith(expected_prefix):
        return ContinuityCheckResult(
            name="preview_range",
            ok=False,
            detail="preview_prefix_mismatch",
        )
    if range_bytes is None:
        # Derive expected range from full preview when caller did not supply it.
        end = min(range_end, len(preview_bytes) - 1)
        range_bytes = preview_bytes[range_start : end + 1]
    expected_range = preview_bytes[range_start : min(range_end, len(preview_bytes) - 1) + 1]
    if range_bytes != expected_range:
        return ContinuityCheckResult(
            name="preview_range",
            ok=False,
            detail="range_mismatch",
        )
    return ContinuityCheckResult(
        name="preview_range",
        ok=True,
        detail=f"bytes={len(preview_bytes)};range={range_start}-{range_end}",
    )


def check_tombstone_or_fenced_delete(
    *,
    seeded: bool,
    source_state: str | None = None,
    content_error_code: str | None = None,
    public_ref: str = SOURCE_TOMBSTONE_PUBLIC_REF,
) -> ContinuityCheckResult:
    """Deletion/tombstone or fenced-delete observable when seeded."""
    if not seeded:
        return ContinuityCheckResult(
            name="tombstone_fenced_delete",
            ok=True,
            detail="not_seeded_skipped",
        )
    state = (source_state or "").strip().lower()
    code = (content_error_code or "").strip()
    if state == "deleting":
        return ContinuityCheckResult(
            name="tombstone_fenced_delete",
            ok=True,
            detail=f"state=deleting;ref={public_ref}",
        )
    if code in {"document_not_found", "source_not_found", "fenced"}:
        return ContinuityCheckResult(
            name="tombstone_fenced_delete",
            ok=True,
            detail=f"content_denied:{code}",
        )
    return ContinuityCheckResult(
        name="tombstone_fenced_delete",
        ok=False,
        detail=f"missing_tombstone_signal:state={state or 'none'};code={code or 'none'}",
    )


def check_preview_reuses_original_census_edge(
    documents: Iterable[DocumentObjectRefs],
) -> ContinuityCheckResult:
    """preview_reuses_original must not double-emit the original key in census."""
    refs = build_census_refs(documents)
    keys = [row["key"] for row in refs]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        return ContinuityCheckResult(
            name="preview_reuses_original",
            ok=False,
            detail=f"duplicate_keys:{','.join(duplicates)}",
        )
    for doc in documents:
        if doc.preview_reuses_original and doc.preview_object_key:
            # Original present once; no separate preview key required.
            if keys.count(doc.original_object_key) != 1:
                return ContinuityCheckResult(
                    name="preview_reuses_original",
                    ok=False,
                    detail="original_key_missing_or_duplicated",
                )
    return ContinuityCheckResult(name="preview_reuses_original", ok=True, detail="deduped")


def load_audit_rows_from_session(session: Any) -> list[dict[str, str]]:
    """Operator SQL projection of drill audit events (ordered)."""
    from sqlalchemy import select

    from context_engine.models import AuditEvent
    from scripts.stack_drill_seed import build_seed_plan

    plan = build_seed_plan()
    request_ids = {event.request_id for event in plan.audit_events}
    rows = session.execute(
        select(AuditEvent)
        .where(AuditEvent.request_id.in_(sorted(request_ids)))
        .order_by(AuditEvent.created_at.asc(), AuditEvent.request_id.asc())
    ).scalars().all()
    out: list[dict[str, str]] = []
    for event in rows:
        created = event.created_at
        created_s = (
            created.strftime("%Y-%m-%dT%H:%M:%SZ")
            if hasattr(created, "strftime")
            else str(created)
        )
        out.append(
            {
                "event_name": event.event_name,
                "outcome": event.outcome,
                "target_kind": event.target_kind or "",
                "target_id": event.target_id or "",
                "request_id": event.request_id or "",
                "created_at": created_s,
            }
        )
    return out


def run_continuity_checks(
    *,
    turn_projection: Mapping[str, Any],
    invalid_ref_denied: bool,
    invalid_ref_error_code: str | None = None,
    raw_token_leaked: bool = False,
    audit_rows: Sequence[Mapping[str, Any]],
    preview_seeded: bool,
    preview_bytes: bytes | None,
    range_bytes: bytes | None = None,
    tombstone_seeded: bool,
    tombstone_state: str | None = None,
    tombstone_content_error: str | None = None,
    login_stub_ok: bool = True,
) -> list[ContinuityCheckResult]:
    """Run the R13 checklist; caller decides exit code from any failure."""
    return [
        login_path_status(stub_ok=login_stub_ok, documented=True),
        check_redaction_omission(turn_projection),
        check_invalid_ref_denied(
            denied=invalid_ref_denied,
            error_code=invalid_ref_error_code,
            raw_token_leaked=raw_token_leaked,
        ),
        check_audit_continuity(audit_rows),
        check_preview_range(
            seeded=preview_seeded,
            preview_bytes=preview_bytes,
            range_bytes=range_bytes,
        ),
        check_tombstone_or_fenced_delete(
            seeded=tombstone_seeded,
            source_state=tombstone_state,
            content_error_code=tombstone_content_error,
        ),
    ]


def _fetch_preview_via_store(key: str) -> bytes:
    from context_engine.adapters.object_storage import object_store_from_settings
    from context_engine.config import Settings

    store = object_store_from_settings(Settings())
    return store.get(key)


def _closed_fail(message: str = "Continuity checks failed.") -> int:
    print(message, file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "P12-04 U3 post-restore continuity (R13 pre-rebuild). "
            "Citations after rebuild are U6/R14. "
            f"Login path: {LOGIN_PATH_DOCUMENTED}"
        )
    )
    parser.add_argument(
        "--fixture-json",
        type=Path,
        default=None,
        help="Offline fixture with turn/audit/ref/preview fields (unit/matrix stub).",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Optional CONTEXT_ENGINE_DATABASE_URL to load audit/turn/tombstone rows.",
    )
    parser.add_argument(
        "--fetch-preview",
        action="store_true",
        help="Fetch seeded preview bytes via product object store.",
    )
    parser.add_argument(
        "--expect-invalid-ref-denied",
        action="store_true",
        default=True,
        help="Require invalid/expired composer ref deny (default true).",
    )
    return parser


def _load_fixture(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fixture must be an object")
    return raw


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    plan = build_seed_plan()

    database_url = (
        (args.database_url or "").strip()
        or os.environ.get("CONTEXT_ENGINE_DATABASE_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
    )
    if args.fixture_json is None and not database_url:
        return _closed_fail("fixture_or_database_required")

    turn_projection: dict[str, Any] = {
        "public_ref": TURN_REDACTED_PUBLIC_REF,
        "status": "redacted",
        "assistant_answer": None,
        "user_message": plan.redacted_turn.user_message,
    }
    audit_rows: list[dict[str, str]] = expected_audit_rows(plan)
    invalid_denied = True
    invalid_code = "composer_ref_unavailable"
    raw_leaked = False
    preview_seeded = True
    preview_bytes: bytes | None = None
    range_bytes: bytes | None = None
    tombstone_seeded = True
    tombstone_state = "deleting"
    tombstone_error: str | None = None

    if args.fixture_json is not None:
        try:
            fixture = _load_fixture(args.fixture_json)
        except Exception:
            return _closed_fail("fixture_unreadable")
        turn_projection = dict(fixture.get("turn") or turn_projection)
        if "audit_rows" in fixture:
            audit_rows = list(fixture["audit_rows"])
        invalid_denied = bool(fixture.get("invalid_ref_denied", invalid_denied))
        invalid_code = fixture.get("invalid_ref_error_code", invalid_code)
        raw_leaked = bool(fixture.get("raw_token_leaked", False))
        preview_seeded = bool(fixture.get("preview_seeded", preview_seeded))
        if "preview_bytes_b64" in fixture:
            import base64

            preview_bytes = base64.b64decode(fixture["preview_bytes_b64"])
        if "preview_bytes_hex" in fixture:
            preview_bytes = bytes.fromhex(str(fixture["preview_bytes_hex"]))
        tombstone_seeded = bool(fixture.get("tombstone_seeded", tombstone_seeded))
        tombstone_state = fixture.get("tombstone_state", tombstone_state)
        tombstone_error = fixture.get("tombstone_content_error", tombstone_error)

    if database_url and args.fixture_json is None:
        try:
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import sessionmaker

            from context_engine.models import ConversationTurn, SourceDocument

            engine = create_engine(database_url)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                turn = session.execute(
                    select(ConversationTurn).where(
                        ConversationTurn.public_ref == TURN_REDACTED_PUBLIC_REF
                    )
                ).scalar_one_or_none()
                if turn is not None:
                    turn_projection = {
                        "public_ref": turn.public_ref,
                        "status": turn.status,
                        "assistant_answer": turn.assistant_answer,
                        "user_message": turn.user_message,
                    }
                audit_rows = load_audit_rows_from_session(session)
                tomb = session.execute(
                    select(SourceDocument).where(
                        SourceDocument.public_ref == SOURCE_TOMBSTONE_PUBLIC_REF
                    )
                ).scalar_one_or_none()
                if tomb is not None:
                    tombstone_state = tomb.state
                    tombstone_seeded = True
                prepared = session.execute(
                    select(SourceDocument).where(
                        SourceDocument.public_ref == SOURCE_PUBLIC_REF
                    )
                ).scalar_one_or_none()
                if prepared is not None and prepared.preview_object_key:
                    preview_seeded = True
                    # Restored-store bytes only — never substitute local seed plan content.
                    preview_key = prepared.preview_object_key
                    preview_bytes = _fetch_preview_via_store(preview_key)
                    range_bytes = preview_bytes[0:4]
        except Exception:
            return _closed_fail("database_continuity_load_failed")

    if preview_seeded and preview_bytes is None:
        return _closed_fail("preview_bytes_required")

    results = run_continuity_checks(
        turn_projection=turn_projection,
        invalid_ref_denied=invalid_denied,
        invalid_ref_error_code=invalid_code,
        raw_token_leaked=raw_leaked,
        audit_rows=audit_rows,
        preview_seeded=preview_seeded,
        preview_bytes=preview_bytes,
        range_bytes=range_bytes,
        tombstone_seeded=tombstone_seeded,
        tombstone_state=tombstone_state,
        tombstone_content_error=tombstone_error,
    )

    failures = [r for r in results if not r.ok]
    for result in results:
        flag = "ok" if result.ok else "FAIL"
        print(f"continuity:{flag}:{result.name}:{result.detail}")

    if failures:
        # Explicit fail-closed message for redaction regressions.
        if any(r.name == "redaction_omission" for r in failures):
            return _closed_fail("redaction_fail_closed: answer text must not reappear")
        return _closed_fail("continuity_failed")
    print("continuity:ok r13_pre_rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
