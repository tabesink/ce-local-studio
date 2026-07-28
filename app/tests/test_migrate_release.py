"""Unit tests for migrate_release upgrade gating (fakes; no live PostgreSQL)."""

from __future__ import annotations

import pytest

from context_engine.migrate_release import MigrateReleaseError, run_migrate_release
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.schema_compatibility import (
    REASON_CURRENT_TARGET_OK,
    REASON_EMPTY_OK,
    REASON_LEGACY,
    REASON_SNAPSHOT_HEAD_MISMATCH,
    CatalogInventory,
    CompatibilityVerdict,
    inventory_from_parts,
)


HEAD = SUPPORTED_ALEMBIC_HEAD


def _empty() -> CatalogInventory:
    return inventory_from_parts()


def _current() -> CatalogInventory:
    return inventory_from_parts(
        alembic_revision=HEAD,
        relations=(("public", "users", "table"), ("public", "alembic_version", "table")),
        columns=(
            ("public", "users", "id", "uuid"),
            ("public", "alembic_version", "version_num", "character varying"),
        ),
    )


def test_empty_runs_upgrade_once_and_post_checks(monkeypatch) -> None:
    empty = _empty()
    current = _current()
    calls: list[str] = []

    monkeypatch.setattr(
        "context_engine.migrate_release.collect_inventory_from_engine",
        lambda _engine: empty if not calls else current,
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.classify_with_ordered_revisions",
        lambda inventory, **kwargs: (
            CompatibilityVerdict(REASON_EMPTY_OK, True)
            if inventory.alembic_revision is None
            else CompatibilityVerdict(REASON_CURRENT_TARGET_OK, True)
        ),
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.load_expected_snapshot",
        lambda _head=None: current,
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.ordered_revisions",
        lambda _config=None: ("base", HEAD),
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.create_engine",
        lambda *_a, **_k: type("E", (), {"dispose": lambda self: None})(),
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.snapshot_path_for_head",
        lambda _head=None: type("P", (), {"is_file": lambda self: True})(),
    )

    def fake_upgrade(_config, target) -> None:
        calls.append(target)

    reason = run_migrate_release(database_url="postgresql+psycopg://x/y", upgrade=fake_upgrade)
    assert reason == REASON_EMPTY_OK
    assert calls == ["head"]


def test_refuse_does_not_call_upgrade(monkeypatch) -> None:
    legacy = inventory_from_parts(
        alembic_revision=HEAD,
        relations=(("public", "wiki_pages", "table"),),
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.collect_inventory_from_engine",
        lambda _engine: legacy,
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.classify_with_ordered_revisions",
        lambda *_a, **_k: CompatibilityVerdict(REASON_LEGACY, False),
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.load_expected_snapshot",
        lambda _head=None: _current(),
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.ordered_revisions",
        lambda _config=None: (HEAD,),
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.create_engine",
        lambda *_a, **_k: type("E", (), {"dispose": lambda self: None})(),
    )
    monkeypatch.setattr(
        "context_engine.migrate_release.snapshot_path_for_head",
        lambda _head=None: type("P", (), {"is_file": lambda self: True})(),
    )

    def boom(*_a, **_k) -> None:
        raise AssertionError("upgrade must not run on refuse")

    with pytest.raises(MigrateReleaseError) as exc:
        run_migrate_release(database_url="postgresql+psycopg://x/y", upgrade=boom)
    assert exc.value.reason == REASON_LEGACY


def test_missing_snapshot_refuses_before_upgrade(monkeypatch) -> None:
    monkeypatch.setattr(
        "context_engine.migrate_release.snapshot_path_for_head",
        lambda _head=None: type("P", (), {"is_file": lambda self: False})(),
    )

    def boom(*_a, **_k) -> None:
        raise AssertionError("upgrade must not run")

    with pytest.raises(MigrateReleaseError) as exc:
        run_migrate_release(database_url="postgresql+psycopg://x/y", upgrade=boom)
    assert exc.value.reason == REASON_SNAPSHOT_HEAD_MISMATCH
