# P12-01 Populated Compatibility Inventory

Date: 2026-07-28  
Status: complete for U1 inventory only.  
Plan: `docs/plans/2026-07-28-002-feat-p12-01-populated-compatibility-plan.md`  
Authority: `docs/master-build-plan.md` P12-01 + § Populated-database compatibility barrier; `docs/architecture/legacy-persistence-retirement.md`; DRIFT-33.

## Disposition legend

| Value | Meaning |
| --- | --- |
| `retain` | Already correct; keep |
| `modify` | Change in this slice |
| `add` | New module/test/doc/wiring in this slice |
| `defer-P12-04` | Backup/restore / image rollback / failed-worker drills |
| `defer-Path-2` | Supported populated upgrade / contraction (not chosen) |

## Compatibility path decision

| Decision | Disposition |
| --- | --- |
| Path 1 — unsupported populated legacy upgrade | `retain` (release choice 2026-07-28) |
| Path 2 — supported upgrade + contraction | `defer-Path-2` |
| Archive Wiki service as migration input | refuse — recognition-only |

## Two guards (required)

| Guard | Fact today | Disposition |
| --- | --- | --- |
| Migration preflight (before Alembic writes) | **absent** — Compose/dev run bare `alembic upgrade head` | `add` dedicated entrypoint |
| Startup readiness (before product writes) | head-only via `check_database_schema` | `modify` — exact head **and** catalog match |

## Path 1 refusal classes (must be named in fixtures)

| Class | Closed reason (target) | Disposition |
| --- | --- | --- |
| Legacy objects (Wiki tables / deferred columns/kinds) | `legacy_database_refused` | `add` fixtures + recognition constants |
| Partial schema (missing required objects / incomplete upgrade) | `partial_schema` | `add` |
| Renamed objects | `renamed_object` | `add` |
| Unknown objects | `unknown_object` | `add` |
| Unknown history | `unknown_history` | `add` |
| Behind head | `revision_behind` | `add` (head check exists; must refuse before write) |
| Ahead head | `revision_ahead` | `add` |
| Forbidden / unknown extension | `extension_refused` | `add` |
| Exact head + extra legacy | refuse (not head-OK) | `add` |
| Exact head + missing objects | `partial_schema` | `add` |
| Snapshot key ≠ runtime head | `snapshot_head_mismatch` | `add` |

## Success accept classes

| Class | Migrate preflight | Startup readiness |
| --- | --- | --- |
| Empty DB (no app objects, no `alembic_version`, allowlisted system/extensions only) | accept → upgrade | not ready until bootstrap/catalog |
| Exact current head + catalog match (+ populated Phase 1 data) | accept → no-op | accept if admin/store gates pass |

## Compose / release entrypoints

| Unit | Fact | Disposition |
| --- | --- | --- |
| `app/compose.stack.yml` `migrate.command` | `["alembic", "upgrade", "head"]` | `modify` → preflight→upgrade entrypoint |
| `scripts/dev.sh` | `(cd "$APP_DIR" && "$PYTHON_BIN" -m alembic upgrade head)` | `modify` → same entrypoint |
| `scripts/dev.ps1` | check if present / Alembic caller | `modify` if it upgrades |
| `migrations/env.py` | shared Alembic env; no refuse gate | `retain` — do **not** put primary preflight here |
| API / worker lifespan | never migrates | `retain` |
| `bootstrap` Compose job | after migrate success | `retain` ordering; fails closed when migrate refuses |

## Readiness (`app/context_engine/services/readiness.py`)

| Check | Fact | Disposition |
| --- | --- | --- |
| DB `SELECT 1` | present | `retain` |
| Exact `SUPPORTED_ALEMBIC_HEAD` (`f1a8c3d04e92`) | present | `retain` + extend |
| Catalog match vs versioned snapshot | **absent** | `add` |
| Enabled administrator (API only) | present | `retain` |
| Object-store probe | present | `retain` |
| Public ready body | safe `503` / `{status:ready}` | `retain` privacy |
| `/health/live` process-only | present | `retain` |
| Worker readiness (no admin) | present | `modify` schema helper only |

## Catalog / snapshot

| Item | Fact | Disposition |
| --- | --- | --- |
| Versioned `pg_catalog` snapshot under `app/context_engine/schema_snapshots/` | **absent** | `add` |
| Shared reconciler service | **absent** | `add` `schema_compatibility.py` |
| Production deferred Wiki name constants | test-only in `test_phase_one_schema_scope.py` | `add` `schema_deferred.py`; tests import from production |
| Extension allowlist (+ versions) | **absent** | `add` |
| `alembic check` after fresh upgrade | foundation tests only | `retain` as R3 proof step |

## Tests / harness

| Item | Fact | Disposition |
| --- | --- | --- |
| Disposable PG harness pattern | duplicated across ~17 `test_postgres_*.py` | `retain` mirror with `ce_p1201_*` prefix; shared extract deferred |
| `test_postgres_foundation.py` fresh-install / readiness | head-only / P1-01 | `retain` + extend readiness scenarios as needed |
| `test_health_contract.py` | revision privacy | `modify` catalog-mismatch cases (unit/mock boundary) |
| `test_compose_stack_config.py` | asserts bare Alembic migrate | `modify` — deliberate assertion flip |
| PG16 Path 1 matrix | **absent** | `add` `test_postgres_migration_preflight.py` |
| Entrypoint unit tests | **absent** | `add` `test_migrate_release.py` |
| Mutation-zero proof on refuse | unspecified | `add` — assert `alembic_version` unchanged + relation-name set hash unchanged pre/post refuse |

## Docs / tracker

| Item | Fact | Disposition |
| --- | --- | --- |
| Inventory | this file | `add` (U1) |
| Evidence | absent | `add` U6 |
| Compose runbook migrate step | bare Alembic | `modify` U6 |
| `docs/master-build-plan.md` P12-01 | `BLOCKED` | `modify` U6 → DONE + Path 1 evidence |
| DRIFT-33 | `IN_PROGRESS` | `modify` U6 — Path 1 half; Path 2 residual |
| `legacy-persistence-retirement.md` | hypothesis / stop condition | `modify` status note only (no Path 2 auth) |

## Explicit non-claims

| Concern | Owner |
| --- | --- |
| Supported populated legacy upgrade / contraction | `defer-Path-2` |
| Backup/restore, image rollback, incident drills | `defer-P12-04` |
| Full suite / contract snapshot convergence | P12-02 |
| Shared disposable-PG harness extract | follow-up (optional) |
| Phase 3 Wiki as upgrade target | outside Phase 1 identity |

## Proof strategy (downstream units)

1. U2 — reconciler + snapshot + unit classification (test-first).
2. U3 — migrate entrypoint + Compose/dev wire + contract flip.
3. U4 — readiness catalog match (characterize head-only, then widen; unit mock for mismatch).
4. U5 — disposable PG16 matrix for AE1–AE5 + every refusal class.
5. U6 — runbook + evidence + tracker/DRIFT-33.
