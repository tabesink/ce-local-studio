# P0-07 Deferred Surface Inventory

Date: 2026-07-23  
Status: historical characterization baseline plus completed active Phase 1 removal evidence.

## Active public and browser seams

| Deferred layer | Current active seam | Phase 1 disposition |
| --- | --- | --- |
| Wiki | ten `/wiki/*` and `/admin/wiki/*` handlers in `app/context_engine/api/routes.py` | remove from registered API/OpenAPI before any public snapshot is accepted |
| Wiki | `services/wiki.py`; Wiki imports/types in `composer_refs.py`, `chat_turns.py`, `sources.py`, models, and audit vocabulary | retire transitively only with the clean-install/compatibility plan; do not delete rows or model state opportunistically |
| Wiki | chat inspector Wiki tab and composer placeholder in `app/client/src/features/chat-shell/ChatShell.tsx` | remove from the production bundle and browser tests |
| Observability | `GET /admin/audit-events` and `GET /admin/domains/{domain_id}/diagnostics/lightrag` | remove from registered API/OpenAPI; retain only private audit writes, allowlisted logs, correlation, metrics and health |
| Observability | `/logs` route, `features/logs-observability/*`, navigation entry, and tests | remove from production route tree/navigation/bundle and update tests to the Phase 1 route manifest |

## Dependency boundary

The future briefs require absence, not hidden routes. The legacy-persistence document blocks destructive schema/model contraction until the explicit populated-database decision and preflight exist. Therefore P0-07 separates:

1. **safe now:** public API registration, frontend route/navigation/bundle, generated-contract and test references;
2. **blocked until compatibility work:** table/enum/model/service deletion, populated-data changes, and deletion-hook surgery that could strand data or break audit continuity.

At the historical baseline this inventory blocked P0-06 snapshots because generation would have published deferred APIs. That blocker is now cleared for the active Phase 1 tree; P0-06 remains open for unrelated route/DTO/SSE parity.

## Post-characterization checkpoint

The active Phase 1 tree now excludes the inventoried deferred publication and product-observability routes, client route/navigation/build seams, audit/diagnostic read service, read-event vocabulary, and diagnostic-only audit metadata keys. `app/tests/test_phase_one_observability_scope.py` positively preserves private transactional audit writes while rejecting the deferred read surface.

## Final active-tree closure

- Registered FastAPI routes and generated OpenAPI contain no deferred publication, audit-read, or diagnostic operation.
- The physical Next route tree is exactly `chat`, `database-visualize`, `documents`, `forbidden`, `login`, and `settings`; the empty residual `logs/` directory was removed.
- Active backend/frontend source, production manifests, Docker/Compose inputs, environment example, generation script, and development launcher contain no deferred public marker.
- Active ORM metadata, composer kinds/columns, audit constraints/metadata, and backend source contain no deferred publication implementation.
- Generic unsupported composer kinds/tokens/accepted refs fail closed and add no prompt content. Phase 1 no longer carries legacy-publication-shaped compatibility tests.
- Stale compiled `diagnostics.pyc` was removed, and the active package is regression-tested against compiled deferred modules.
- Private transactional audit writes and health/readiness remain positively tested. P8 owns missing real-boundary append-only, denial, safe-log/correlation, bounded-metric, privacy, and failure evidence; P0-07 neither implements nor removes those controls.

The configured Alembic directory/history is still absent. P0-07 therefore proves only the clean-install active ORM/package target and performs no populated-database mutation. Discovery or retirement of legacy database objects remains blocked behind the explicit P12-01 path in `architecture/legacy-persistence-retirement.md`.


## Closure verification

Verified on 2026-07-23 with `bash scripts/verify.sh`:

- phase-scope documentation passed across 54 governed files, including adversarial checker fixtures;
- Python lock integrity, backend import, and backend lint passed;
- backend tests passed: 49 tests, including the P0-07 negative-production-scope and retained-safety suites;
- generated OpenAPI and TypeScript snapshots reproduced byte-for-byte, including fixture checks;
- frontend typecheck and 53 frontend tests passed;
- the optimized Next.js production build exposed only `/`, `/_not-found`, `/chat`, `/database-visualize`, `/documents`, `/forbidden`, `/login`, and `/settings`;
- the backend Docker image built successfully and the Compose configuration validated.

The verified P0-07 input manifest has SHA-256 `0056471f547246534363a88abe92ee3ab32b5510f9857e8b9c20cfe0bdb4e756`. It covers the five Phase 1 scope suites, active model/route/audit/composer/prompt code, generated OpenAPI, package and container manifests, environment example, and development/contract-generation scripts. This evidence file is intentionally excluded from its own manifest.

Known non-blocking warnings remain owned outside P0-07: the Starlette `TestClient`/`httpx` deprecation, six high-severity npm audit findings, Node module-type warnings, and Next.js middleware-to-proxy deprecation. They do not reintroduce a deferred Wiki or observability product surface.
