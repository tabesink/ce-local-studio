# P1-07 Durable Idempotency and Keyset Pagination Evidence

Date: 2026-07-28  
Status: DONE  
Plan: `docs/plans/2026-07-28-007-feat-p1-07-idempotency-pagination-plan.md`  
Inventory: `docs/_scratch/p1-07-idempotency-pagination-inventory.md`  
Branch tip at evidence write: `feat/p1-07-idempotency-pagination` @ `ef68200` (+ U4 docs/contract commit)

## What landed

| Item | Location / Result |
| --- | --- |
| Inventory freeze | `docs/_scratch/p1-07-idempotency-pagination-inventory.md` — 10 Idempotency-Key routes add; 5 admin lists modify; conversations/documents credit |
| Durable store | Alembic `a2c7e9f14b80` + `HttpIdempotencyRecord` + `services/idempotency.py`; schema snapshot `schema_snapshots/a2c7e9f14b80.json`; `SUPPORTED_ALEMBIC_HEAD` bumped |
| Create adoption | Optional `Idempotency-Key` on conversation, model-profile, domain, source upload (`routes.py`) |
| Operation adoption | Optional key on domain start/stop/delete, source retry, index retry, source delete |
| Admin keyset | `services/users.py` + domains/sources list helpers; `cursor`/`limit` on five admin lists |
| Catalog closure | Removed conversation-create deferred language from `docs/contracts/http-api-catalog.md` and `docs/architecture/data-and-lifecycle.md` |
| Contracts | `app/contracts/openapi.json` + regenerated `app/client/src/lib/api/generated/openapi.ts` |

## Acceptance mapping

| AE | Proof |
| --- | --- |
| AE1 | Inventory dispositions for every catalog Idempotency-Key and `nextCursor` surface |
| AE2 | `test_postgres_idempotency_races.py` concurrent identical claim → one completed row |
| AE3 | Unit + HTTP fingerprint mismatch → `409 idempotency_conflict` |
| AE4 | `test_admin_pagination.py` multi-page `nextCursor`, last-page null, limit clamp, `cursor_expired` |
| AE5 | `test_conversation_http_contract.py` durable create replay; catalog deferred note removed |

## Commands and results

### Focused unit / HTTP (default SQLite altitude)

```bash
cd app
.venv/bin/python -m pytest \
  tests/test_idempotency_store.py \
  tests/test_operation_idempotency.py \
  tests/test_admin_pagination.py \
  tests/test_conversation_http_contract.py \
  tests/test_turn_execution_leases.py \
  -q
```

Observed (2026-07-28): **26 passed**

### Opted-in PostgreSQL 16 races

```bash
cd app
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres' \
.venv/bin/python -m pytest tests/test_postgres_idempotency_races.py -q
```

Observed (2026-07-28): **3 passed** against PostgreSQL 16 (`localtest_context_engine-postgres-1` on `:5438`).

### Generated contracts

```bash
cd app/client && npm run generate:api
bash scripts/check-generated-contracts.sh
```

Observed (2026-07-28): **generated contract snapshots: PASS**

## Privacy

- Idempotency rows store SHA-256 `key_hash` and fingerprint only — never raw keys, request bodies, credentials, or passwords (`test_idempotency_store.py` privacy case).
- Admin user pages continue to project through `safe_user` (no hashes/sessions).
- Replay paths reconstruct closed DTOs from stored public refs without re-running `commit_protected_mutation`.

## Residuals

| Residual | Owner |
| --- | --- |
| Documents list ordering `(updatedAt,id)` vs catalog global `(createdAt,id)` | Named inventory residual; not re-sorted in P1-07 |
| Idempotency row retention/TTL/compaction | Deferred follow-up (Phase 1 append-only claims) |
| Browser list virtualization / Settings list UX | P9-07 / P12-07 |
| Broader handwritten response DTO adoption (DRIFT-01) | Vertical owners |
| Dedicated HTTP replay tests for every admin create/operation surface | Conversation + domain-start + store races proven; remaining surfaces share the same helper |
| `scripts/check-doc-phase-scope.sh` rejects `closed` scan-file class on P5-04 plan | Pre-existing on `origin/main`; not introduced by P1-07 |

## Tracker

- `docs/master-build-plan.md`: P1-07 DONE; P1 phase DONE.
- `docs/brownfield-refactor-register.md`: comparative-gap row DONE; DRIFT-18 HTTP claim/keyset half DONE.
