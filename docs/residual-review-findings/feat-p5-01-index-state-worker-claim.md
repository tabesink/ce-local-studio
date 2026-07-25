# Known Residuals — feat/p5-01-index-state-worker-claim

Source review: focused P5-01 tip review (`eaf8cd5`), verdict `ship`,
actionable findings none.

## Testing gaps (accepted)

1. A-08 stale-completion after generation bump — PG proof rejects
   `mark_*` with wrong generation/request while the row still holds G, but
   does not bump `index_generation` (retry/cancel) then attempt completion
   with a captured older identity.
2. `FOR UPDATE SKIP LOCKED` concurrency — claim/skip/reclaim assertions use
   one Session sequentially; a two-connection barrier race is still open.
3. No PG proof for `mark_index_failed_if_current` stale identity, or
   cancel/retry making an in-flight `run_once` completion a no-op end-to-end.

## Residual risks (deferred owners)

1. No lease heartbeat during submit/readiness — long remote calls can expire
   the lease and allow reclaim/re-submit. Owner: P5-03 / DRIFT-28 remainder /
   DRIFT-32 index half.
2. Expired `SUBMITTING` reclaim re-invokes submit; correctness depends on
   idempotent LightRAG submit keys (P5-02/P5-03).
3. SQLite ignores `FOR UPDATE`; only disposable PostgreSQL 16 evidence is
   concurrency-relevant.
