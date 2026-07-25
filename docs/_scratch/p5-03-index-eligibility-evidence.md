# P5-03 Index Submit/Poll/Retry/Cancel/Delete and Query-Eligibility Evidence

Date: 2026-07-25

Slice: P5-03

Requirements: FR-05; A-08; A-09 index cleanup half; DRIFT-27 cancel/recovery
half; DRIFT-28 persisted backoff remainder; DRIFT-32 index uncertain reconcile;
`docs/contracts/http-api-catalog.md` index retry/cancel envelopes.

Status: DONE - implemented and proven 2026-07-25

## Implemented and retained behavior

- Closed `AdminSourceDto` response models on
  `POST .../index/retry` (`202`) and `POST .../index/cancel` (`200`).
- Mapped private index service codes onto the approved HTTP ErrorCode set
  (`operation_conflict`, `dependency_unavailable`, `not_found`,
  `validation_error`, `domain_state_conflict`).
- `SourceIndexWorker` heartbeats index leases during submit; on
  `source_index_timeout` leaves `submitting` with private
  `source_index_uncertain` and lease-expiry backoff, then probes readiness
  before re-submit (DRIFT-32).
- Not-ready accepted polls schedule persisted backoff via
  `index_lease_expires_at` + `CE_SOURCE_INDEX_POLL_BACKOFF_SECONDS` (DRIFT-28)
  without a schema migration.
- `source_is_query_eligible` requires domain available + prepared + `ready` +
  current request identity; `processing` is never eligible (A-08).
- Advisory `indexRetry` / `indexCancel` actions on `AdminSourceDto`.
- Index remote cleanup remains via `cleanup_index_before_source_delete`
  (P4-04); cancel proves remote absence before terminal `cancelled`.

## Proof-first evidence

1. Unit red→green: eligibility matrix, HTTP error mapping, poll backoff
   scheduling, timeout→uncertain→probe-without-resubmit in
   `tests/test_source_index_eligibility.py`.
2. PostgreSQL 16 green: submit→accepted→ready→eligible; backoff skips leased
   accepted peers; HTTP retry `202 {source}` / in-progress `409
   operation_conflict` / cancel `200` cancelled + not eligible; service retry
   after cancel re-queues — `tests/test_postgres_source_index_eligibility.py`.

## Verification

```text
cd app
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres
python -m pytest tests/test_source_index_eligibility.py tests/test_postgres_source_index_eligibility.py tests/test_postgres_source_index_claim.py tests/test_lightrag_renderer_adapter.py tests/test_sources_service.py -q
# focused suite green
python ../scripts/generate_openapi.py
cd client && npm run generate:api
```

## Residuals / deferred

- Process-wide native LightRAG lifecycle lock retained (DRIFT-27 concurrency).
- Idempotency-Key transport persistence for index retry (shared residual with
  P4-04; no approved idempotency store yet).
- Member Library / Evidence document routes remain P6/P9.
- Worker graceful stop-claim drain remains P10-03 (DRIFT-31).
