# Known Residuals — feat/p5-02-lightrag-renderer-adapter

Source review: focused P5-02 review (`cb079ae` + lease/timeout fix),
initial verdict `fix`; P1 lease/timeout guard and P2 cleanup budget applied.

## Applied from review

1. Index lease default raised to 180s; Settings requires
   `source_index_lease_seconds > source_index_timeout_seconds`.
2. Native `_run` cancel/gather/shutdown_asyncgens bounded with a 2s cleanup
   budget so the process lock is released after timeout.

## Testing gaps (accepted)

1. Native timeout fixture still uses `asyncio.sleep`, not slow
   `finalize`/`ainsert` under the lock.
2. No full native submit/readiness/delete integration against vendored
   LightRAG with real providers (Compose stays on local).
3. Worker mapping of `source_index_timeout` through
   `mark_index_failed_if_current` under reclaim races remains with P5-03.

## Residual risks (deferred owners)

1. Process-wide `_NATIVE_LIGHTRAG_LIFECYCLE_LOCK` retained — P5-03 concurrency.
2. Native timeout can leave uncertain remote LightRAG outcome — DRIFT-32 /
   P5-03 reconciliation.
3. Index HTTP/eligibility envelopes — P5-03.
