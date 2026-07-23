# P0-01 Layout Inventory and Decision

Date: 2026-07-23  
Status: complete for P0-01; this is execution evidence, not a release completion record.

## Observed lifted layout

| Surface | Physical location before P0-01 | Referenced location | Disposition |
| --- | --- | --- | --- |
| Backend package | `app/server/` | `context_engine` in all backend imports, package discovery, Uvicorn, Docker, Compose, and Alembic assumptions | modify: canonicalize as `app/context_engine/` |
| Backend manifest and lock | `app/pyproject.toml`, `app/uv.lock` | `app/` | retain-and-reverify: preserve pins, make the package discoverable from the manifest root, and install images with frozen `uv sync` |
| Migrations | absent; `app/alembic.ini` names `migrations` | `app/migrations/` in Docker, Alembic, and development reload arguments | retain the canonical path; P1 owns the Alembic baseline and no migration is fabricated in P0-01 |
| Frontend | `app/client/` | Compose and `scripts/dev.sh` incorrectly used `frontend/` | modify: retain `app/client/` and point callers there |
| Vendored retrieval runtime | `app/vendor/lightrag/` | Docker and package discovery use `vendor/` | retain-and-reverify; it remains private and no vendor behavior changes here |
| Backend Docker image | `app/Dockerfile` | copied missing `README.md` and migration directory | modify: copy only present manifest/config/package/vendor inputs; P1 adds the canonical migration package |
| Development entry | `scripts/dev.sh` | assumed root-level backend, migrations, and frontend | modify: root script enters `app/` for backend/Alembic and `app/client/` for the frontend |

## Evidence before mutation

- `cd app && python3 -c 'import context_engine'` failed with `ModuleNotFoundError`.
- `cd app/client && npm run typecheck` failed on the pre-existing `Button` `className` prop mismatch in `SettingsPanel.tsx`. This is a P9 frontend-kit drift, not part of the layout repair.
- `app/compose.stack.yml` targeted `./frontend`, which does not exist.
- `app/Dockerfile` copied `README.md`, `context_engine/`, and `migrations/`; none existed at its build context root.

## P0-01 boundary

This unit aligns paths only. It does not create a migration baseline (P1), fix frontend behavior/type errors (P9), remove Phase 2/3 seams (P0-07 after the compatibility inventory), or change product contracts. The authoritative clean-install and populated-database decisions remain those in `docs/architecture/legacy-persistence-retirement.md`.

## Verification after mutation

- `cd app && python3 -c 'import context_engine'` passed and resolved `app/context_engine/__init__.py`.
- All canonical backend Python files compiled successfully.
- `uv lock --check` passed; the backend image now uses `uv sync --frozen --no-dev` and imported `context_engine` successfully inside the built image.
- `docker compose -f app/compose.stack.yml config --quiet` passed with non-secret placeholder environment values.
- `bash -n scripts/dev.sh` passed.

The existing frontend typecheck remains red at `SettingsPanel.tsx` because the lifted Button contract does not accept `className`; that is retained as P9 evidence rather than patched in this layout-only unit.

## Root-gate baseline on 2026-07-23

P0-05 adds `scripts/verify.sh` and `.github/workflows/verify.yml` as the pinned root loop. `bash scripts/verify.sh` passed documentation scope, Python lock integrity, backend import and lint, frontend dependency-lock installation, backend Docker build, and Compose configuration. It deliberately returned nonzero for four inherited gaps:

1. backend tests: no files exist in the configured `app/tests` target;
2. frontend typecheck and production build: `SettingsPanel.tsx` passes `className` to a Button contract that does not accept it (P9-01/P9-04 evidence);
3. frontend tests: 47/55 pass; eight tests resolve historical design/factory documentation under `app/` even though the authoritative package is at the repository root.

The gate is a truthful P0 baseline, not B0 or release evidence. Its additional required gates are introduced by P0-03/P0-06 and the owning migration, privacy, browser, and deployed-ingress packages.

## P0-03 error-envelope slice

`app/context_engine/api/errors.py` now always emits the catalog’s closed `error.fields` record, including `{}` when no field failures exist. Validation errors project field names to the safe fixed message rather than exposing raw validator data. The existing browser error decoder now uses the same record shape, including local transport fallbacks.

Proof-first evidence: the new `app/tests/test_api_errors.py` initially failed because `fields` was omitted, then passed (`2 passed`) after the implementation change. `npm run typecheck` reports no error-envelope issues; its only remaining error is the inherited Settings Button `className` mismatch recorded above.


## Subsequent P0-05 revalidation on 2026-07-23

The red results above remain the historical P0-01 baseline. P0-05 later repaired the inherited `SettingsButton.className` type mismatch and replaced the lifted UIUX-factory assertions with tests against the reviewed root `DESIGN.md`, `docs/frontend/` contract package, and subordinate frontend-factory plan. The current `bash scripts/verify.sh` run passes all checks, including 40 backend tests, live and adversarial OpenAPI/TypeScript snapshot checks, 53 frontend tests, frontend typecheck/build, the backend image build, and Compose configuration.

P0-05 is now `DONE` for its bounded CI deliverable after adding reproducible OpenAPI/TypeScript live and stale-artifact checks. Canonical HTTP catalog/SSE parity, real PostgreSQL/migration behavior, privacy scanning, browser E2E, and deployed-ingress integration remain owned by P0-06 and later packages. The six high-severity advisories reported by `npm ci` remain recorded dependency evidence and do not authorize an unreviewed forced lockfile upgrade.
