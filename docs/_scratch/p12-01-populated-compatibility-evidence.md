# P12-01 Populated Compatibility Evidence

Date: 2026-07-28  
Status: Path 1 closed on PostgreSQL 16.  
Plan: `docs/plans/2026-07-28-002-feat-p12-01-populated-compatibility-plan.md`  
Inventory: `docs/_scratch/p12-01-populated-compatibility-inventory.md`  
Release decision: **Path 1 — unsupported populated legacy upgrade** (confirmed 2026-07-28).

## Implemented surfaces

| Surface | Location |
| --- | --- |
| Deferred Wiki recognition constants | `app/context_engine/schema_deferred.py` |
| Catalog reconciler + closed reasons | `app/context_engine/services/schema_compatibility.py` |
| Versioned snapshot (head `f1a8c3d04e92`) | `app/context_engine/schema_snapshots/f1a8c3d04e92.json` |
| Snapshot generator | `app/context_engine/generate_schema_snapshot.py` |
| Migrate entrypoint | `app/context_engine/migrate_release.py` |
| Compose migrate command | `python -m context_engine.migrate_release` |
| Host-native migrate | `scripts/dev.sh` → same module |
| Startup catalog match | `check_catalog_compatibility` in `readiness.py` |
| Unit tests | `test_schema_compatibility_unit.py`, `test_migrate_release.py`, health/worker catalog mismatch |
| PG16 matrix | `app/tests/test_postgres_migration_preflight.py` |

## Authoritative verification

```bash
cd app
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres' \
uv run --frozen --python 3.12 --extra test pytest \
  tests/test_schema_compatibility_unit.py \
  tests/test_migrate_release.py \
  tests/test_postgres_migration_preflight.py \
  tests/test_compose_stack_config.py \
  tests/test_health_contract.py \
  tests/test_worker_readiness.py \
  -q
```

Observed (2026-07-28): focused Path 1 suites green; `test_postgres_migration_preflight.py` **9 passed** against PostgreSQL **16.13**.

Artifact revision at evidence write: see git tip of `feat/p12-01-populated-compatibility` after U5/U6 commits.

## Scenario matrix

| Scenario | Result |
| --- | --- |
| Empty → migrate_release → `alembic check` → bootstrap → ready | pass (`empty_ok`) |
| Populated current-target → migrate no-op → ready | pass (`current_target_ok`) |
| Head + `wiki_pages` | refuse `legacy_database_refused`; fingerprint unchanged; ready `schema_incompatible` |
| Baseline-only (behind) | refuse `revision_behind`; fingerprint unchanged |
| Ahead/unknown `alembic_version` | refuse; fingerprint unchanged |
| Extra unknown table | refuse `unknown_object` |
| Renamed `users` | refuse (`renamed_object` / mismatch class) |
| Missing required table | refuse `partial_schema` |
| `pgcrypto` on otherwise empty | refuse `extension_refused` |
| App factory on empty DB | no schema mutation |

Mutation-zero proof: pre/post `(alembic_revision, catalog fingerprint)` equality on every refuse path.

## Safety / privacy

- HTTP ready failures remain closed `503 dependency_unavailable` without revision/object dumps.
- CLI refuse prints closed reason + short action only.
- Snapshot and reconciler stay server-side; no public endpoint added.

## Operator altitude

Compose/dev matrix Path 1 gate only. Not backup/restore drills (P12-04), not Path 2 supported upgrade, not production HA/TLS.

## Residuals

| Residual | Owner |
| --- | --- |
| Path 2 supported populated upgrade / contraction | deferred product decision |
| Backup/restore, image rollback, failed-worker incident drills | P12-04 |
| Full suite / contract snapshot convergence | P12-02 |
| Shared disposable-PG harness extract | optional follow-up |
