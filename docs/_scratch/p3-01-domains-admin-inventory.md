# P3-01 Domains / Domain Operations Schema and Admin APIs Inventory

Date: 2026-07-25

Owner: P3-01

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-03; A-03 (create/start projection); A-05
(first-line conflict); A-10 (DELETE `202 {operation}` + `If-Match` shape);
HTTP catalog Runtime settings and domains; DTO `AdminDomainDto` /
`OperationDto` / `DomainSummaryDto`; DRIFT-12 projection half.

## Scope

- Reverify `domains` / `domain_operations` constraints on PostgreSQL 16 at the
  current Alembic head, then add optimistic `version` columns required by
  closed DTOs, `ETag`, and DELETE `If-Match`.
- Replace lifted admin/member/operation projections with closed catalog DTOs
  (`queryEligible`, nested `embeddingProfile`, `runtimeReady`,
  `controlGeneration`, `activeOperationId`, `version`, `allowedActions`;
  operation `targetKind`/`targetRef`/`generation`/`requestedAt`/nested
  `error`).
- Close DRIFT-12 projection: start/stop succeed as `202 {operation}` (not
  `200 {domain}`); align OpenAPI/generated artifacts.
- Wire GET detail `ETag`, DELETE `If-Match` → `428` / `409 stale_revision`,
  list/operations `nextCursor` envelopes, and closed HTTP error codes.
- Bump `control_generation` on start/stop intent; keep sync local-controller
  completion in-request as P3-01 pilot behavior with worker-lease races
  deferred.
- Adopt `commit_protected_mutation` for create and lifecycle terminal audits
  where the product row and audit must commit together.

## Out of scope

- Runtime controller port extraction / `adapters/domain_runtime_controller.py`
  (P3-02).
- Lease owner/expiry/heartbeat, stale-worker no-ops, authoritative-refresh
  under concurrent leased workers (P3-03 / DRIFT-12 race half).
- Full A-10 redaction/cleanup worker proof (P3-03).
- Durable `Idempotency-Key` replay store (catalogued; no Phase 1 store exists
  yet for admin ops — residual, same class as P2 model-profile key).
- Settings Domain accordion / frontend DTO adoption (P9-04).
- `storageSummary` public field (uncontracted; remove from public projection).

## Disposition register

| Surface | Current evidence | Disposition | P3-01 action and completion proof |
| --- | --- | --- | --- |
| Baseline `domains` / `domain_operations` tables + ORM CHECKs/indexes | Present in baseline migration; no dedicated lifecycle proof | retain-and-reverify | Prove constraints/FKs/partial unique active-op index on PG16 |
| `domains.version` / `domain_operations.version` | Missing in schema.txt + ORM; DTO/HTTP require Version/ETag/If-Match | add | Migration + ORM + schema.txt; prove ETag/If-Match |
| Lifted `safe_domain_admin` / member / operation projections | `available`, flat `embeddingProfileId`, `storageSummary`, `errorCode` | replace | Closed `AdminDomainDto` / `DomainSummaryDto` / `OperationDto` snapshots |
| start/stop handlers + OpenAPI `200 {domain}` | DRIFT-12 | modify | `202 {operation}`; conflict codes; regenerate contracts |
| create / list / detail / status / operations / delete | Free-form dicts; delete already `202` without If-Match | modify | Closed envelopes, ETag, If-Match, `nextCursor` |
| Controllers inlined in `services/domains.py` | Local/Docker adapters used by create/start/stop | retain-and-reverify | Keep call sites; do not claim P3-02 port completion |
| `DomainDeleteWorker` lease claim | Exists for queued delete | retain-and-reverify | Keep enqueue path; deep race proof stays P3-03 |
| Frontend `features/domains/api.ts` lifted types | Expects `{domain}` on start/stop | defer to P9 | Producer/OpenAPI ownership only in P3-01 |
| Uncontracted `storageSummary` | Present in admin projection | remove-from-phase-1 | Drop from public DTO projection |

## Retained invariants

- Domains start `stopped`; embedding profile is immutable after create (P2-03).
- One active domain operation per domain (partial unique index).
- Query eligibility requires running + no active op + runtime healthy.
- Protected mutations and required audit rows commit together.
- Private runtime IDs, storage paths, and controller payloads never appear in
  public DTOs.

## Gaps closed by task-owned evidence

1. Unit proofs for closed projections, start/stop returning operations,
   generation bump, conflict codes, and If-Match stale/missing delete.
2. Disposable PostgreSQL 16 proof of schema versions, A-03 create→stopped→start
   `202 {operation}`, concurrent start conflict, DELETE If-Match, and member
   `queryEligible` list.
3. OpenAPI/generated client regeneration for domain admin response shapes.
