"""P7-04 U2: turn lease columns stay private and present on the ORM/schema."""

from __future__ import annotations

from pathlib import Path

from alembic.script import ScriptDirectory

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import ConversationTurn
from context_engine.services.chat_turns import safe_turn_summary

APP_ROOT = Path(__file__).resolve().parents[1]
TURN_LEASE_REVISION = "e9f2a1b83c70"
PRIOR_REVISION = "c7d91e5a2f04"
COMPOSER_CONSUMED_REVISION = "f1a8c3d04e92"
CURRENT_HEAD_REVISION = "a2c7e9f14b80"


def test_turn_lease_migration_revises_conversation_ownership_head() -> None:
    from alembic.config import Config

    scripts = ScriptDirectory.from_config(Config(str(APP_ROOT / "alembic.ini")))
    revision = scripts.get_revision(TURN_LEASE_REVISION)
    assert revision is not None
    assert revision.down_revision == PRIOR_REVISION
    assert CURRENT_HEAD_REVISION in scripts.get_heads()
    assert scripts.get_revision(COMPOSER_CONSUMED_REVISION).down_revision == TURN_LEASE_REVISION
    assert scripts.get_revision(CURRENT_HEAD_REVISION).down_revision == COMPOSER_CONSUMED_REVISION


def test_conversation_turn_exposes_private_lease_fields() -> None:
    columns = {column.name for column in ConversationTurn.__table__.columns}
    assert {
        "lease_owner",
        "lease_expires_at",
        "execution_generation",
        "events_retained_after",
        "claimable_at",
    }.issubset(columns)


def test_database_schema_contract_documents_turn_leases() -> None:
    schema = Path(__file__).resolve().parents[2].joinpath("docs", "database-schema.txt").read_text(
        encoding="utf-8"
    )
    assert "lease_owner varchar(64) NULL" in schema
    assert "execution_generation integer NOT NULL DEFAULT 0" in schema
    assert "events_retained_after integer NOT NULL DEFAULT 0" in schema
    assert "claimable_at timestamp NULL" in schema
    assert "never public DTO/SSE fields" in schema


def test_turn_lease_settings_fail_closed_when_not_exceeding_synthesis() -> None:
    try:
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            testing=True,
            synthesis_timeout_seconds=60,
            turn_lease_seconds=60,
        )
    except ValueError as exc:
        assert "turn_lease_seconds must exceed synthesis_timeout_seconds" in str(exc)
    else:
        raise AssertionError("expected fail-closed lease validation")


def test_safe_turn_summary_omits_lease_fields() -> None:
    now = utc_now()
    turn = ConversationTurn(
        conversation_id="conv-internal",
        client_request_id="req-lease-privacy",
        route="direct_llm",
        status="running",
        user_message="hello",
        composer_ref_fingerprint="0" * 64,
        lease_owner="turn-worker",
        execution_generation=3,
        events_retained_after=2,
        claimable_at=now,
        created_at=now,
        updated_at=now,
    )
    summary = safe_turn_summary(turn)
    forbidden = {
        "leaseOwner",
        "lease_owner",
        "leaseExpiresAt",
        "executionGeneration",
        "eventsRetainedAfter",
        "claimableAt",
    }
    assert forbidden.isdisjoint(summary.keys())
    assert "lease" not in _json_dump_keys(summary)


def _json_dump_keys(payload: dict) -> set[str]:
    keys = set(payload)
    for value in payload.values():
        if isinstance(value, dict):
            keys |= _json_dump_keys(value)
    return keys
