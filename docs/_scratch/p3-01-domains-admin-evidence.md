# P3-01 Domains / Domain Operations Schema and Admin APIs Evidence

Date: 2026-07-25

Slice: P3-01

Requirements and cases: FR-03; A-03 create/start projection; A-05 first-line
conflict; A-10 DELETE `If-Match` shape; DRIFT-12 projection half; HTTP catalog
domain admin rows; closed `AdminDomainDto` / `OperationDto` / `DomainSummaryDto`

Status: DONE

## Implemented and retained behavior

- Alembic head `e3a1c8d04f21` adds positive `version` columns on `domains` and
  `domain_operations`; readiness `SUPPORTED_ALEMBIC_HEAD` advanced to match.
- Admin/member/operation projections use closed catalog DTOs:
  `queryEligible`, nested `embeddingProfile`, `runtimeReady`,
  `controlGeneration`, `activeOperationId`, `version`, `allowedActions`;
  operations expose `targetKind`/`targetRef`/`generation`/`requestedAt`/nested
  `error`. Uncontracted `storageSummary` / `available` / flat
  `embeddingProfileId` are removed from public projections.
- DRIFT-12 projection: start/stop succeed as `202 {operation}` with
  `DomainOperationMutationResponse`; OpenAPI/generated TypeScript regenerated.
- GET detail returns strong `ETag`; DELETE requires `If-Match` (`428` missing /
  `409 stale_revision`); list/operations envelopes include `nextCursor: null`.
- Start/stop bump `control_generation` at intent; sync local-controller
  completion remains in-request for P3-01 pilot usability. Lease races and
  authoritative-refresh under concurrent workers stay with P3-03.
- Create/delete-queue terminal audits use `commit_protected_mutation` where the
  product row and audit must commit together.
- HTTP error codes map to the closed union (`not_found`, `operation_conflict`,
  `dependency_unavailable`, `domain_state_conflict`,
  `domain_operation_in_progress`, `stale_revision`).

## Proof-first evidence

Unit proofs cover closed operation/admin/member projections, allowed-action
gates, and stale-revision mapping. Disposable PostgreSQL 16 then proved schema
version checks, A-03 create→stopped→start operation success with generation
bump, start-while-running conflict, member `queryEligible`, DELETE stale/missing
`If-Match`, and HTTP `201`/`202` closed shapes without lifted fields.

## Verification

```bash
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres \
app/.venv/Scripts/python.exe -m pytest \
  tests/test_domains_service.py \
  tests/test_postgres_domains.py \
  tests/test_runtime_config_service.py \
  tests/test_postgres_runtime_config.py \
  tests/test_postgres_foundation.py \
  tests/test_postgres_audit.py \
  tests/test_audit_service.py \
  tests/test_phase_one_schema_scope.py \
  tests/test_health_contract.py \
  tests/test_authoritative_dto_components.py \
  tests/test_generated_contract_gate.py -q
```

Observed:

```text
......................................................                   [100%]
54 passed
```

Focused counts: 4 domain unit proofs, 1 PostgreSQL/HTTP domain lifecycle proof,
plus retained P2 runtime-config/foundation/audit/schema/health/DTO/contract
regressions on head `e3a1c8d04f21`.

## PostgreSQL / HTTP assertions

- Fresh install reaches single head `e3a1c8d04f21` with
  `ck_domains_version_positive` and `ck_domain_operations_version_positive`.
- Create commits domain `stopped` at generation 1 / version 1.
- Start returns succeeded operation at generation 2; domain becomes `running`.
- Second start returns `409 domain_state_conflict`.
- Member list projects `queryEligible: true` without `available`.
- HTTP create returns `201` closed `AdminDomainDto` + `ETag`.
- HTTP start returns `202 {operation}` (not `{domain}`).
- DELETE without `If-Match` returns `428`; with current version returns
  `202 {operation}` queued delete.

## Residuals / deferred

- Runtime controller port extraction (`adapters/domain_runtime_controller.py`)
  remains P3-02.
- Lease/heartbeat, stale-worker no-ops, and DRIFT-12 authoritative-refresh under
  concurrent leased workers remain P3-03.
- Durable admin `Idempotency-Key` replay store remains unbuilt (same residual
  class as P2 model-profile keys).
- Settings Domain accordion / frontend DTO adoption remains P9-04.
- Operation-row failure codes such as worker `domain_runtime_unavailable` stay
  private to operation projections and are not HTTP `ErrorCode` values.
