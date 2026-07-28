# Legacy Persistence Retirement Boundary

Status: Path 1 (unsupported populated legacy upgrade) was chosen and proven for Phase 1 on 2026-07-28 — see `docs/_scratch/p12-01-populated-compatibility-evidence.md`. This document remains the static closure hypothesis and stop condition for Path 2; it is not a live database census, migration authorization, or permission to drop/contract populated legacy data.

## Historical closure in the lifted tree

The reviewed lifted application contained a deferred knowledge-publication closure spanning:

- page, immutable revision, contribution, and contribution-to-evidence tables;
- cyclic page/current-revision and revision/published-contribution relationships;
- state checks, positive revision/order checks, unique page/revision and publication constraints, supporting indexes, and restrictive/cascading foreign keys;
- optional page and revision targets on composer tokens and accepted turn-reference rows;
- contribution evidence links to conversation-turn Evidence, plus source-deletion invalidation paths;
- service-owned list, edit, submit, review, publish, reject, and invalidation transitions;
- protected mutation and denial event vocabulary in append-only audit history.

Primary historical evidence: `.references/phase-archive-2026-07-23/app/context_engine/services/wiki.py`, `docs/_scratch/p0-07-deferred-surface-inventory.md`, and `docs/_scratch/code-docs-drift-review.md` (DRIFT-33 and related lifecycle findings). The review predates the Phase 3 deferral, so its repair recommendation is superseded by removal from the Phase 1 runtime while its evidence remains historical.

This archive does not contain an exact snapshot of the removed ORM definitions or a recoverable Alembic lineage. It is sufficient to explain why the closure is absent from Phase 1, but it is not migration input and cannot prove or authorize a populated legacy upgrade.

## Phase 1 clean-install target

`docs/database-schema.txt` defines a clean Phase 1 target without this closure. Active ORM metadata, route/service source, composer constraints, and audit vocabulary now match that Wiki-free boundary; `app/tests/test_phase_one_schema_scope.py` enforces the absence. The three-revision Alembic chain now has task-owned PostgreSQL 16 fresh-install and in-rebuild baseline-to-head retained-data proof under P1-01. That chain does not establish an upgrade path from an unknown populated legacy database, and no destructive or populated legacy contraction is authorized. Historical audit rows remain private and append-only; removal must not cascade through them or expose them publicly.

## Blocking compatibility decision

Before any populated database is migrated or contracted, a separately approved release decision must reconcile:

1. live PostgreSQL `pg_catalog` and `information_schema` objects;
2. complete Alembic current/history and recovered release migrations;
3. current and historical ORM metadata;
4. every table, column, enum, sequence, index, constraint, trigger, function, view, object dependency, stored row, accepted reference, token, Evidence link, and audit target/event in the closure.

An unsupported populated upgrade requires a read-only migration preflight that accepts only an empty database or the exact current target catalog/head and refuses legacy, partial, renamed, unknown-object, and unknown-history states before writes. Normal startup separately accepts populated databases only at the exact current target catalog/head.

A supported upgrade additionally requires write/claim fencing, in-flight drain, per-object census and disposition, protected export/backup with separate key custody, rollback-compatible quarantine, prior-version rollback rehearsal, isolated restore proof, count/checksum and FK/orphan validation, audit continuity, affected-conversation read/replay proof, and an approved go/no-go cutoff. Restore or key-recovery failure keeps contraction blocked.
