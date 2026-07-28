"""Unit classification for Path 1 schema compatibility (no live PostgreSQL)."""

from __future__ import annotations

from context_engine.services.schema_compatibility import (
    REASON_AHEAD,
    REASON_BEHIND,
    REASON_CURRENT_TARGET_OK,
    REASON_EMPTY_OK,
    REASON_EXTENSION,
    REASON_LEGACY,
    REASON_PARTIAL,
    REASON_RENAMED,
    REASON_SNAPSHOT_HEAD_MISMATCH,
    REASON_UNKNOWN_HISTORY,
    REASON_UNKNOWN_OBJECT,
    classify_inventory,
    classify_with_ordered_revisions,
    dump_snapshot,
    inventory_from_parts,
    is_empty_inventory,
    load_expected_snapshot,
    write_snapshot,
)
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD


HEAD = SUPPORTED_ALEMBIC_HEAD
ORDERED = ("aaaa", "bbbb", HEAD, "zzzz_future")


def _expected_at_head() -> object:
    return inventory_from_parts(
        alembic_revision=HEAD,
        relations=(("public", "users", "table"), ("public", "alembic_version", "table")),
        columns=(
            ("public", "users", "id", "uuid"),
            ("public", "alembic_version", "version_num", "character varying"),
        ),
    )


def test_empty_inventory_accepted_on_migrate_only() -> None:
    empty = inventory_from_parts()
    assert is_empty_inventory(empty)
    migrate = classify_inventory(empty, policy="migrate", expected=_expected_at_head())
    startup = classify_inventory(empty, policy="startup", expected=_expected_at_head())
    assert migrate.reason == REASON_EMPTY_OK and migrate.accepted
    assert startup.reason == REASON_PARTIAL and not startup.accepted


def test_identical_inventories_are_current_target() -> None:
    expected = _expected_at_head()
    live = inventory_from_parts(
        alembic_revision=HEAD,
        relations=expected.relations,
        columns=expected.columns,
    )
    verdict = classify_inventory(live, policy="startup", expected=expected)
    assert verdict.reason == REASON_CURRENT_TARGET_OK and verdict.accepted


def test_snapshot_head_mismatch_when_file_head_disagrees(tmp_path, monkeypatch) -> None:
    from context_engine.services import schema_compatibility as sc

    monkeypatch.setattr(sc, "SNAPSHOT_DIR", tmp_path)
    expected = _expected_at_head()
    write_snapshot(expected, head=HEAD)
    # Corrupt metadata
    path = sc.snapshot_path_for_head(HEAD)
    path.write_text('{"alembic_head":"not-the-head","inventory":{}}', encoding="utf-8")
    live = inventory_from_parts()
    verdict = classify_inventory(live, policy="migrate", supported_head=HEAD)
    assert verdict.reason == REASON_SNAPSHOT_HEAD_MISMATCH and not verdict.accepted


def test_legacy_wiki_table_refused() -> None:
    expected = _expected_at_head()
    live = inventory_from_parts(
        alembic_revision=HEAD,
        relations=expected.relations + (("public", "wiki_pages", "table"),),
        columns=expected.columns,
    )
    verdict = classify_inventory(live, policy="migrate", expected=expected)
    assert verdict.reason == REASON_LEGACY and not verdict.accepted


def test_missing_required_table_is_partial() -> None:
    expected = _expected_at_head()
    live = inventory_from_parts(
        alembic_revision=HEAD,
        relations=(("public", "alembic_version", "table"),),
        columns=(("public", "alembic_version", "version_num", "character varying"),),
    )
    verdict = classify_inventory(live, policy="startup", expected=expected)
    assert verdict.reason == REASON_PARTIAL and not verdict.accepted


def test_renamed_relation_detected() -> None:
    expected = _expected_at_head()
    live = inventory_from_parts(
        alembic_revision=HEAD,
        relations=(
            ("public", "alembic_version", "table"),
            ("public", "users_renamed", "table"),
        ),
        columns=(
            ("public", "alembic_version", "version_num", "character varying"),
            ("public", "users_renamed", "id", "uuid"),
        ),
    )
    verdict = classify_inventory(live, policy="migrate", expected=expected)
    assert verdict.reason == REASON_RENAMED and not verdict.accepted


def test_unknown_extra_table_refused() -> None:
    expected = _expected_at_head()
    live = inventory_from_parts(
        alembic_revision=HEAD,
        relations=expected.relations + (("public", "mystery", "table"),),
        columns=expected.columns,
    )
    verdict = classify_inventory(live, policy="migrate", expected=expected)
    assert verdict.reason == REASON_UNKNOWN_OBJECT and not verdict.accepted


def test_unknown_extension_refused_even_when_empty_of_tables() -> None:
    live = inventory_from_parts(extensions=(("plpgsql", "1.0"), ("vector", "0.8.0")))
    verdict = classify_inventory(live, policy="migrate", expected=_expected_at_head())
    assert verdict.reason == REASON_EXTENSION and not verdict.accepted


def test_revision_behind_and_ahead() -> None:
    expected = _expected_at_head()
    behind = inventory_from_parts(
        alembic_revision="aaaa",
        relations=expected.relations,
        columns=expected.columns,
    )
    ahead = inventory_from_parts(
        alembic_revision="zzzz_future",
        relations=expected.relations,
        columns=expected.columns,
    )
    behind_v = classify_with_ordered_revisions(
        behind, policy="migrate", ordered_revisions=ORDERED, expected=expected, supported_head=HEAD
    )
    ahead_v = classify_with_ordered_revisions(
        ahead, policy="migrate", ordered_revisions=ORDERED, expected=expected, supported_head=HEAD
    )
    assert behind_v.reason == REASON_BEHIND and not behind_v.accepted
    assert ahead_v.reason == REASON_AHEAD and not ahead_v.accepted


def test_unknown_history_refused() -> None:
    expected = _expected_at_head()
    live = inventory_from_parts(
        alembic_revision="deadbeef0000",
        relations=expected.relations,
        columns=expected.columns,
    )
    verdict = classify_with_ordered_revisions(
        live, policy="migrate", ordered_revisions=ORDERED, expected=expected, supported_head=HEAD
    )
    assert verdict.reason == REASON_UNKNOWN_HISTORY and not verdict.accepted


def test_dump_load_round_trip_stable(tmp_path, monkeypatch) -> None:
    from context_engine.services import schema_compatibility as sc

    monkeypatch.setattr(sc, "SNAPSHOT_DIR", tmp_path)
    expected = _expected_at_head()
    path = write_snapshot(expected, head=HEAD)
    assert path.name == f"{HEAD}.json"
    loaded = load_expected_snapshot(HEAD)
    assert loaded.relations == expected.relations
    assert dump_snapshot(loaded, head=HEAD)["alembic_head"] == HEAD
