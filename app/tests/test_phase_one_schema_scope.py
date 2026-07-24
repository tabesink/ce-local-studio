from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from context_engine.db import Base
from context_engine.models import (
    COMPOSER_REF_KINDS,
    TURN_EVENT_SCHEMA_VERSION,
    TURN_EVENT_TYPES,
    TURN_STATUS_CANCELLED,
    TURN_STATUSES,
)
from context_engine.services.audit import ALLOWED_AUDIT_METADATA_KEYS
from context_engine.services.chat_turns import TurnStreamEvent, encode_sse_event


DEFERRED_WIKI_TABLES = {
    "wiki_pages",
    "wiki_revisions",
    "wiki_contributions",
    "wiki_contribution_evidence_refs",
}
PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "context_engine"


def test_phase_one_metadata_excludes_deferred_wiki_schema() -> None:
    assert DEFERRED_WIKI_TABLES.isdisjoint(Base.metadata.tables)
    assert COMPOSER_REF_KINDS == ("source", "evidence", "template")

    accepted_ref_columns = Base.metadata.tables["conversation_turn_composer_refs"].columns
    assert "wiki_page_id" not in accepted_ref_columns
    assert "wiki_revision_id" not in accepted_ref_columns


def test_phase_one_audit_schema_excludes_deferred_wiki_vocabulary() -> None:
    audit_table = Base.metadata.tables["audit_events"]
    constraint_sql = " ".join(
        str(constraint.sqltext)
        for constraint in audit_table.constraints
        if hasattr(constraint, "sqltext")
    ).casefold()

    assert "wiki." not in constraint_sql
    assert not any("wiki" in key.casefold() for key in ALLOWED_AUDIT_METADATA_KEYS)


def test_phase_one_turn_event_ledger_matches_canonical_sse_contract() -> None:
    event_table = Base.metadata.tables["conversation_turn_events"]

    assert set(event_table.columns.keys()) == {
        "id",
        "turn_id",
        "sequence",
        "schema_version",
        "event_type",
        "payload_json",
        "payload_digest",
        "occurred_at",
    }
    assert TURN_EVENT_SCHEMA_VERSION == "1.0"
    assert TURN_EVENT_TYPES == (
        "turn.accepted",
        "route.selected",
        "retrieval.started",
        "retrieval.completed",
        "evidence.delta",
        "answer.delta",
        "turn.completed",
        "turn.failed",
        "turn.cancelled",
        "turn.redacted",
    )
    assert any(
        index.unique and tuple(column.name for column in index.columns) == ("turn_id", "sequence")
        for index in event_table.indexes
    )


def test_phase_one_public_refs_and_cancelled_status_match_contract() -> None:
    public_ref_tables = (
        Base.metadata.tables["source_documents"],
        Base.metadata.tables["conversation_turn_evidence_refs"],
        Base.metadata.tables["conversation_turn_composer_refs"],
    )

    for table in public_ref_tables:
        assert not table.columns["public_ref"].nullable
        assert any(
            index.unique and tuple(column.name for column in index.columns) == ("public_ref",)
            for index in table.indexes
        )

    assert TURN_STATUS_CANCELLED == "cancelled"
    assert TURN_STATUSES == ("running", "completed", "failed", "cancelled", "redacted")


def test_canonical_sse_encoder_uses_event_id_and_versioned_envelope() -> None:
    event = TurnStreamEvent(
        event_id="evt_123",
        turn_id="turn_123",
        sequence=3,
        event_type="answer.delta",
        occurred_at=datetime(2026, 7, 24, 12, 0, 0),
        payload={"text": "Grounded answer."},
    )

    frame = encode_sse_event(event)
    lines = frame.splitlines()
    assert lines[:2] == ["id: evt_123", "event: answer.delta"]
    envelope = json.loads(lines[2].removeprefix("data: "))
    assert envelope == {
        "schemaVersion": "1.0",
        "eventId": "evt_123",
        "turnId": "turn_123",
        "sequence": 3,
        "type": "answer.delta",
        "occurredAt": "2026-07-24T12:00:00Z",
        "payload": {"text": "Grounded answer."},
    }


def test_active_package_contains_no_deferred_wiki_implementation() -> None:
    assert PACKAGE_ROOT.is_dir()
    assert all(
        "wiki" not in path.read_text().casefold()
        for path in PACKAGE_ROOT.rglob("*.py")
    )
