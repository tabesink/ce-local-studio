# P1-06 Append-Only Audit and Protected-Mutation Inventory

Date: 2026-07-24

Owner: P1-06

Status: DONE - implemented and proven 2026-07-24

Requirements and cases: FR-09; C-02; DRIFT-20

## Scope

This inventory is the required brownfield checkpoint for the P1-06 append-only
audit schema, transactional `AuditService`, and protected-mutation helper.
Existing files are evidence only. P1-06 receives completion credit only after
PostgreSQL 16 proves atomic mutation+audit commit, fail-closed rollback when
audit persistence fails, and database-enforced append-only history.

P1-06 does not claim full mutation-site allowlist adoption (P8-01), privacy
scans across every sink (P8), product audit-read surfaces (Phase 2 / removed),
or resource-specific protected mutations owned by later feature packages.

## Disposition register

| Surface | Current evidence | Disposition | P1-06 action and completion proof |
| --- | --- | --- | --- |
| `audit_events` table / ORM | Baseline migration and `AuditEvent` model match closed event/actor/outcome checks, indexes, and metadata column | retain-and-reverify | Prove fresh-install head includes the table and check constraints against PostgreSQL 16 |
| Append-only invariant | Documented in `database-schema.txt` and PRD; no UPDATE/DELETE API; no DB trigger or ORM guard | add | Add PostgreSQL BEFORE UPDATE/DELETE triggers plus ORM before_update/before_delete guards; prove UPDATE/DELETE fail and INSERT succeeds |
| `AuditService.record` | Allowlists event names, actor kinds, outcomes, and flat metadata keys/size; flushes into the caller session; rolls back on SQLAlchemy failure | modify | Keep allowlists; ensure validation failures also fail closed without leaving a committable product change; prove invalid event/metadata raise `audit_unavailable` |
| Protected-mutation helper | Absent; call sites manually `record` then `commit`, so audit failure semantics are uneven | add | Add `commit_protected_mutation` that runs mutate+required audit in one transaction and commits both or neither |
| Denial audit hook | `require_admin` records `security.admin_route_denied` then commits | retain-and-reverify | Keep denial path; broader denial-coverage matrix remains P8-01 |
| Public audit/diagnostic read | Removed from Phase 1 registration by P0-07 | retain absence | Do not add list/read/export APIs; keep `test_phase_one_observability_scope.py` green |
| Call-site adoption of the helper | Domains, sources, runtime config, chat redaction still use ad-hoc `record`+`commit` | defer feature owners / P8-01 | Prove the helper at the service boundary with a synthetic protected state change; do not rewrite every later-phase call site in this slice |

## Retained invariants

- Audit history is private and append-only; Phase 1 exposes no product read/export surface.
- Protected state mutations and their required audit row commit together or roll back together.
- Audit failure surfaces as `503 audit_unavailable` with no product change.
- Metadata is service-validated flat JSON, allowlisted keys only, <=4096 bytes.
- Event names, actor kinds, and outcomes remain closed unions from ORM/schema.
- Raw prompts, answers, excerpts, credentials, paths, stack traces, and private
  storage/runtime identifiers stay out of audit metadata.

## Gaps closed by task-owned evidence

1. Database-enforced append-only triggers on `audit_events`.
2. A reusable protected-mutation commit helper with atomic success and rollback
   on audit failure.
3. PostgreSQL 16 proof that a product row change is not visible when the
   required audit write fails.
4. Focused unit proof for allowlist rejection and helper rollback without a
   database when practical, plus real-boundary PostgreSQL proof for triggers
   and transactional commit.

## Completed evidence design

The P1-06 proof will use the existing disposable PostgreSQL 16 harness pattern
(`CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1` plus administrative URL),
upgrade to the new Alembic head, insert a valid audit row, prove UPDATE/DELETE
are rejected by the database, prove `commit_protected_mutation` persists a
synthetic user disablement with `user.disabled`, and prove an injected audit
failure rolls back the product change while raising `AuditError`.
