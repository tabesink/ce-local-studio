# P5-01 Index State / Generation Fields and Worker Claim Loop Evidence

Date: 2026-07-25

Slice: P5-01

Requirements: FR-05; A-08 lease/generation fence half; DRIFT-28 claim/lease
half; `docs/database-schema.txt` source_documents index fields.

Status: DONE - implemented and proven 2026-07-25

## Implemented and retained behavior

- Retained internal `index_state` CHECK vocabulary
  (`not_requested|queued|submitting|accepted|ready|failed|cancelling|cancelled`)
  with public DTO mapping unchanged from P4-01.
- Retained index generation, request identity, content hash, remote id, error,
  lease, and timestamp columns from the baseline schema (no new migration).
- `SourceIndexWorker._claim_next_source` now assigns lease owner/expiry on every
  claim path: queued→submitting, expired submitting reclaim, and accepted
  readiness when lease is absent or expired.
- Unexpired submitting/accepted leases are not double-claimed
  (`FOR UPDATE SKIP LOCKED` retained).
- `mark_index_accepted_if_current` / `mark_index_ready_if_current` continue to
  reject mismatched generation or request id.

## Proof-first evidence

1. Red baseline: reclaim after expired submitting lease left
   `index_lease_owner` as the previous worker (`index-worker-a` vs expected
   `index-worker-b`) in `tests/test_postgres_source_index_claim.py`.
2. Green after claim-loop lease assignment on PostgreSQL 16: schema columns/
   CHECKs/index, queued claim, reclaim, accepted lease skip/reclaim, and
   generation/request fence no-ops.

## Verification

```text
cd app
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres
python -m pytest tests/test_postgres_source_index_claim.py -q
# 1 passed
```

## Residuals / deferred

- Versioned renderer and LightRAG adapter timeout/isolation → P5-02 (DRIFT-27).
- Index submit/poll/retry/cancel/delete envelopes, persisted readiness backoff,
  and query-eligibility service → P5-03 (DRIFT-28 remainder, DRIFT-32 index).
- No collapse of private CHECK vocabulary to public `processing`/`deleting`.
- Worker graceful stop-claim drain remains P10-03 (DRIFT-31).
