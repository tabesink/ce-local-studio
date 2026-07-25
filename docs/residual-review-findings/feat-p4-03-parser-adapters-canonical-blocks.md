# Known residuals — feat/p4-03-parser-adapters-canonical-blocks

Source: P4-03 code review follow-up (2026-07-25)

Accepted residuals (not blocking P4-03 closure):

1. **Delete dual-write** — `delete_source` / `purge_domain_sources_local` still
   remove object-store bytes before the DB commit. Harden with
   tombstone/outbox in P4-04 delete workflow (DRIFT-29).

2. **Legacy image bytes** — Alembic `a8d3f1c62e90` backfills synthetic
   `legacy_img_*` keys without copying pre-P4-03 filesystem image bytes.
   Greenfield and re-prepare are supported; populated-DB byte migration is
   deferred if needed under legacy retirement.

3. **Reducto URL results** — `type=url` parse results fail closed rather than
   fetching presigned chunk URLs. Resolve before production Reducto at scale.

4. **Live SDK CI** — Docling/Reducto optional extras are not exercised on the
   network in CI; injectable transports/converters prove the product seam.
