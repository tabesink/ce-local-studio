# P4-04 Source Outline / Operation / Retry / Cancel / Delete Evidence

Date: 2026-07-25

Slice: P4-04

Requirements: FR-04; FR-08; A-07; A-09; M-11 redaction hook; DRIFT-29;
HTTP catalog outline/operations/retry/cancel/delete; closed Outline +
`OperationDto`.

Status: DONE - implemented and proven 2026-07-25

## Implemented and retained behavior

- Outline returns only `{kind,label,level,pageNumber}` for heading/figure/table
  items; plain text blocks and canonical markdown are omitted.
- `safe_source_operation` projects closed `OperationDto` with
  `targetKind: "source"`, nested `error`, `generation`, `version`, and
  `requestedAt`.
- Source operations list returns `nextCursor` (null in Phase 1).
- Cancel requires strong `If-Match` on source version (`428` / `409 stale_revision`).
- Delete is `202 {operation}`: one protected transaction fences
  `state=deleting`, supersedes active prep, redacts turns, expires live
  composer source tokens, queues `operation_type=delete`, and audits
  `source.delete_queued`.
- `SourceDeleteWorker` leases cleanup (index + object store) then removes the
  source row under preparation-generation fence; failed cleanup leaves
  `deleting` + failed op and is reclaimable.
- Alembic head `b5c8e2d19f47` expands prep op types to `prepare|delete` and
  allowlists delete audit events.
- `purge_domain_sources_local` flushes the fence before object/row cleanup.

## Proof-first evidence

1. `tests/test_sources_service.py` — closed OperationDto + outline privacy.
2. `tests/test_postgres_source_apis.py` — HTTP outline/operations/cancel
   If-Match/`428`, delete `202`, worker removes row after fence on PostgreSQL 16.
3. Existing prep/schema postgres suites remain green at the new head.

## Verification

```text
cd app
python -m pytest tests/test_sources_service.py -q
# 5 passed

CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres
python -m pytest tests/test_postgres_source_apis.py tests/test_postgres_sources_schema.py tests/test_postgres_source_preparation.py -q
# 3 passed

# from repo root
python scripts/generate_openapi.py
python scripts/generate_json_schemas.py
cd app/client && npm run generate:api
```

## Residuals / deferred

- HTTP `Idempotency-Key` transport for retry/delete (no shared helper yet;
  same residual as domain delete).
- Index retry/cancel closed envelopes remain with P5.
- Member document/content routes remain with P6/P9.
- Frontend documents adapter still omits If-Match (P9).
- Broad audit allowlist / privacy scan breadth remains with P8-01.
