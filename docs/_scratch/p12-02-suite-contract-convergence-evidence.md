# P12-02 Suite and Contract Snapshot Convergence Evidence

Date: 2026-07-28  
Status: DONE (scoped boundary)  
Plan: `docs/plans/2026-07-28-003-feat-p12-02-suite-contract-convergence-plan.md`  
Branch tip at evidence write: `feat/p12-02-suite-contract-convergence` @ pre-U4 `3c128bf` (U4 commit updates tip)

## What landed

| Item | Location / Result |
| --- | --- |
| Phase-scope manifest sync | Six plans classified in `docs/phase-scope-manifest.md`; plan-002 public-contract ceiling restored |
| Production-scope allowlist | Path 1 recognition modules skipped in `test_phase_one_production_scope.py` |
| Cross-sink privacy + catalog | SQLite catalog bypass in `test_cross_sink_privacy_scan.py` |
| Root verify comments | Privacy/PG boundary notes in `scripts/verify.sh` |
| CI PostgreSQL job | `.github/workflows/verify.yml` `verify-postgresql` with `pytest -m postgresql` |
| Foundation ownership proof | `test_postgres_foundation.py` P1-03 uses public refs / `not_found` |
| Contract snapshots | Six artifacts live + adversarial gates PASS (no regen required) |

## Commands and results

### Default root verification (no PostgreSQL opt-in)

```bash
bash scripts/verify.sh
```

Observed (2026-07-28): **verification: PASS**

| Check | Result |
| --- | --- |
| phase-scope documentation + fixtures | PASS |
| Python lock / import / ruff | PASS |
| backend tests | **399 passed, 47 skipped** (postgresql marker skipped without opt-in) |
| generated contract snapshots + fixtures | PASS |
| frontend lock / typecheck / tests / build | PASS (152 frontend tests) |
| backend Docker build | PASS |
| Compose configuration | PASS |

Privacy scans (P8-01 / P8-02 / P8-03) ride the default backend pytest step and are green after the catalog-bypass fix.

### Disposable PostgreSQL 16 suite (CI job shape)

```bash
cd app
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres' \
uv run --frozen --python 3.12 --extra test pytest -m postgresql -q
```

Observed (2026-07-28): **51 passed** against PostgreSQL 16 (local `localtest_context_engine-postgres-1` on `:5438`).

CI wires the same opt-in env against a `postgres:16` service on `:5432` in the required `verify-postgresql` job.

### Contract snapshot convergence

```bash
bash scripts/check-generated-contracts.sh
bash scripts/tests/check-generated-contracts.sh
cd app && uv run --frozen --python 3.12 --extra test pytest \
  tests/test_generated_contract_gate.py \
  tests/test_generated_sse_contract.py -q
```

Observed: live compare PASS; adversarial fixtures PASS; generated contract/SSE tests **14 passed**. No artifact regen required in this slice.

## Residuals

| Residual | Owner |
| --- | --- |
| Playwright / visual matrix / two-user cache browser E2E | P12-07 |
| Live Compose smoke (`stack_smoke_*`) | P10 evidence-owned (not root verify) |
| Deployed-ingress SSE / stream-drain / TLS / direct-API denial | P12-05 |
| SBOM / provenance / immutable release manifest | P12-06 |
| Broader handwritten response-DTO adoption | DRIFT-01 (vertical slices) |
| Adversarial security review | P12-03 |
| Backup/restore drills | P12-04 |
| Production acceptance | P12-08 |

## Tracker updates

- `docs/master-build-plan.md` P12-02 → DONE with this evidence link
- DRIFT-09 → backend/CI half closed; E2E residual remains P12-07 (B0 not complete)
- `docs/tech-stack.md` verify paragraph refreshed to match the actual gate boundary

## Explicit non-claims

This slice does **not** claim B0 complete, production release readiness, live Compose smoke, Playwright acceptance, or DRIFT-01 full response-DTO adoption.
