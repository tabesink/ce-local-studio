# P7-01 Conversation Ownership and Durable Turn Foundation Evidence

Date: 2026-07-26

Owner: P7-01

Status: DONE

Requirements and cases: FR-06; M-03; M-06; M-08; M-10; M-11; C-04.

## Implemented boundary

- Conversation and turn rows retain private UUID primary keys and now carry
  dedicated persisted `conv_...` and `turn_...` UUID4 public refs. PostgreSQL
  defaults preserve migration-first rollout and application rollback
  compatibility. Runtime creation retries bounded collisions and fails closed.
- Conversations have positive optimistic versions. Create/detail/rename return
  strong ETags; rename/delete require `If-Match`; stale writes fail without
  overwrite.
- Owner CRUD uses one canonical owner-filtered path. Mutations re-lock the
  enabled user/session and conversation in the committing transaction and
  commit with a content-free audit row.
- Listing uses owner-bound stable `(created_at DESC,id DESC)` keyset
  pagination. Its opaque cursor carries only a version and prior public ref;
  malformed, missing, deleted, and cross-owner anchors return
  `cursor_expired`.
- Detail uses the nested closed DTO and deterministic turn order. Redacted
  turns omit answer, Evidence, accepted refs, and private failure state.
  Batched projections defer canonical source text and derive domain query
  eligibility from current authoritative runtime readiness.
- Current stream, resume, cancel, and composer-discovery boundaries resolve
  public refs. Legacy accepted-event rows and digests remain unchanged while
  replay substitutes the owner-authorized conversation public ref.
- Turn insertion, detail-visible turn transitions, and conversation deletion
  acquire the same parent-row lock. Turn creation, Evidence persistence,
  completion, failure, cancellation, and redaction advance the strong detail
  ETag. Concurrent identical turn retries attach to the one durable turn.

## Verification

### Focused backend and generated-contract gate

```text
cd app
.\.venv\Scripts\python.exe -m pytest tests\test_conversations_service.py tests\test_conversation_http_contract.py tests\test_chat_sse_http_contract.py tests\test_canonical_turn_event_behavior.py tests\test_generated_contract_gate.py -q
```

Result: PASS, 28 tests.

This covers title normalization, owner isolation, paging, ETag/If-Match,
transaction-time session/user revalidation, bounded public-ref collisions,
atomic audit rollback, public SSE refs, immutable legacy replay, canonical
denials, Origin/CSRF enforcement, authoritative domain eligibility, generated
components, redacted omission, and strong ETag changes for detail-visible turn
transitions.

### PostgreSQL 16 migration and race evidence

```text
cd app
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=<local disposable PostgreSQL 16 admin URL>
.\.venv\Scripts\python.exe -m pytest tests\test_postgres_conversations.py -q
```

Result: PASS, 4 tests.

The migration test upgrades from `b5c8e2d19f47`, proves backfill format,
positive version, retained cryptographic server defaults, named indexes,
old-app/new-schema inserts, unchanged append-only payload/digest bytes, and
rollback to the prior head after persisted conversation audit events. Barrier
tests prove delete/turn-insert serialization without orphans, one-winner
rename/delete behavior, stale identity-map session revocation, and concurrent
identical turn claims creating one row with one replay.

### Broad backend boundary

```text
cd app
.\.venv\Scripts\python.exe -m pytest tests -q
```

Result: PASS for the complete local backend suite; environment-gated
PostgreSQL tests were skipped in this command and run separately above.

### Static and generated quality

Changed-file Ruff: PASS.

OpenAPI/public-schema generation and check: PASS.

Frontend generated-client typecheck: PASS.

The repository-wide Node test command still has an inherited Windows-only
foundation path-separator assertion and inherited SSE fixture/parser failures.
Neither consumes the P7-01 generated conversation types; all directly affected
backend, generated-contract, and TypeScript type gates pass. This is recorded
as a platform/baseline boundary rather than weakening those unrelated tests.

### Privacy scan

The generated OpenAPI, public DTO JSON Schema, and generated API client were
scanned for `ownerUserId`, private owner/source-block names, trace IDs, and raw
event payload field names. Result: PASS, no matches.

Service/HTTP tests additionally prove:

- public responses contain public conversation, turn, Evidence, document, and
  accepted-ref identifiers only;
- other-owner and unknown reads share the same status/code/message;
- audit rows contain only event name, actor, public target ref, request ID, and
  outcome--never title, question, answer, or excerpt; and
- legacy stored event payloads and digests are not rewritten.

## Rollout and recovery

- Apply Alembic revision `c7d91e5a2f04` before the new application. The
  retained PostgreSQL defaults allow the prior application to insert rows
  against the expanded schema during rollout or after application rollback.
- Rollback to `b5c8e2d19f47` drops only the additive conversation/turn public
  refs and conversation version/index/check. It deliberately retains the
  widened audit-event allowlist because conversation audit rows are
  append-only. Existing private keys, turns, Evidence refs, audit rows, event
  payloads, and event digests remain intact.
- Do not roll the schema back after external consumers begin retaining the new
  public conversation/turn refs without first draining that application
  version.

## Deferred ownership

- Shared durable create-operation idempotency for `POST /conversations`.
- P7-02 through P7-05 chat classification/orchestration/event/redaction work.
- P8 system-wide cross-sink privacy and denial-audit expansion.
