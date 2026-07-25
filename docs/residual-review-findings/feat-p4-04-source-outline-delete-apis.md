# Known residuals — feat/p4-04-source-outline-delete-apis

Source: P4-04 code review follow-up (2026-07-25)

Accepted residuals (not blocking P4-04 closure):

1. **Idempotency-Key** — Catalog lists retry/delete keys; no shared HTTP
   Idempotency-Key helper exists yet (same residual as domain delete). Durable
   op `request_id` remains.

2. **Cancel↔delete race coverage** — Service serializes via source version +
   one-active unique index; dedicated PostgreSQL latch races are deferred.

3. **Fence side-effect depth** — Delete fence redacts turns and expires
   composer source tokens; HTTP postgres suite proves outline/cancel/delete
   envelopes and worker row removal, not full redaction/token matrix (P8/P12).

4. **Mutation ETag vs If-Match** — Cancel/delete responses ETag
   `operation.version`; next If-Match must come from a source GET
   (`source.version`). Matches domain lifecycle pattern.

5. **Outline heading label fallback** — When `section_path` is empty, heading
   labels may use the first markdown line (bounded SafeLabel). Closed shape
   still omits canonical body fields.
