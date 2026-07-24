# P1-06 Append-Only Audit and Protected-Mutation Evidence

Date: 2026-07-24

Slice: P1-06

Requirements and cases: FR-09; C-02; DRIFT-20

Status: DONE

## Implemented and retained behavior

- Retained closed `audit_events` vocabulary, indexes, and allowlisted
  `AuditService.record` metadata validation.
- Added Alembic revision `c4e8f1a02b93` with PostgreSQL BEFORE UPDATE/DELETE
  triggers that reject mutation of `audit_events`.
- Added ORM `before_update` / `before_delete` listeners that raise
  `AuditError` for append-only defense in the application session.
- Added `commit_protected_mutation` so a product change and its required audit
  row commit together, or neither commits.
- `AuditService.record` now fails closed on validation and persistence errors
  by rolling back the current transaction and raising `audit_unavailable`.
- Readiness `SUPPORTED_ALEMBIC_HEAD` advanced to `c4e8f1a02b93`.
- Public audit-read surfaces remain absent.

## Proof-first evidence

Unit tests initially failed to import `commit_protected_mutation`. After the
helper and fail-closed `record` path landed, unit allowlist/rollback proofs
passed. PostgreSQL 16 then proved trigger presence, atomic disable+audit
success, raw UPDATE/DELETE rejection, and product-row rollback when the
required audit event is rejected.

## Verification

```bash
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres \
app/.venv/bin/python -m pytest \
  tests/test_postgres_audit.py \
  tests/test_postgres_foundation.py \
  tests/test_audit_service.py \
  tests/test_phase_one_observability_scope.py \
  tests/test_phase_one_schema_scope.py -q
```

Observed:

```text
......................                                                   [100%]
22 passed
```

Focused counts: 1 PostgreSQL audit proof, 8 foundation/authz/readiness
PostgreSQL proofs (head-compatible), 4 unit audit proofs, 2 observability
scope proofs, and schema-scope proofs including audit vocabulary absence of
Wiki terms.

## PostgreSQL assertions

- Fresh install reaches single head `c4e8f1a02b93` with
  `trg_audit_events_forbid_update` and `trg_audit_events_forbid_delete`.
- `commit_protected_mutation` persists `users.is_disabled` with a matching
  `user.disabled` audit row, actor, request ID, and trace ID.
- ORM and raw SQL UPDATE/DELETE against `audit_events` fail; the row remains.
- Rejected audit event names raise `AuditError` / `audit_unavailable` and leave
  the product row unchanged with no leaked audit row.

## Rollback and restore boundary

Revision `c4e8f1a02b93` downgrades by dropping the two triggers and the
`ce_forbid_audit_events_mutation` function. It does not alter table columns.
Foundation baseline-to-head retained-data proof still passes through the new
head. Populated legacy compatibility remains blocked under P12-01.

## Boundaries retained

- P8-01 owns broad protected-mutation call-site allowlist coverage, denial
  matrix expansion, and adversarial privacy scans across sinks.
- Feature packages own adopting `commit_protected_mutation` at their
  resource-specific mutation seams.
- Phase 2 owns any product audit-read/export surface.
