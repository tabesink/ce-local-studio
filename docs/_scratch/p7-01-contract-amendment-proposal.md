# P7-01 Contract Amendment Proposal

Date: 2026-07-26

Status: approved by the user on 2026-07-26; D5 Option A selected

## Purpose

The mandatory LFG plan review found that P7-01 could not be implemented without choosing between conflicting or incomplete approved contracts. This memo records the user-approved decision package and the exact authority files it amends. D5 Option A explicitly defers shared durable create idempotency; D1-D4 and D6 authorize the P7-01 implementation plan.

## Verified current state

- `docs/contracts/http-api-catalog.md` defines `GET /conversations/{conversationId}` as `200 {conversation,turns}`.
- `docs/contracts/dto-schema-catalog.md` instead defines `ConversationDetailDto` as a flat `ConversationSummaryDto & {turns}` object.
- `ConversationSummaryDto` contains `version`, and rename/delete require `If-Match`, but `docs/database-schema.txt` and `Conversation` currently contain no version.
- `POST /conversations` says `Idempotency-Key` is supported, but `docs/database-schema.txt` defines no durable create-idempotency record. Earlier P2/P3/P4 evidence records the same shared residual.
- Protected mutations must audit atomically, while the closed `AUDIT_EVENT_NAMES` database constraint contains no conversation create/rename/delete event.
- Global pagination requires `(createdAt,id)` order. The current service orders by `updated_at`, then `created_at`, then `id`.
- The global contract requires an opaque cursor but does not require cursor signing or a new secret.
- The current conversation and turn UUID primary keys are emitted publicly even though root guidance says private database IDs stay behind the API; the documents do not explicitly say whether these PKs are intentionally public opaque refs.

## Recommended decision package

### D1. Use the nested conversation-detail envelope

Choose the HTTP catalog shape:

```ts
type ConversationDetailResponseDto = {
  conversation: ConversationSummaryDto;
  turns: TurnDto[];
};
```

Retire the flat `ConversationDetailDto` definition or redefine it as this response envelope. This preserves the existing route shape and follows the repository's other mutation/detail response-envelope patterns.

Rejected alternative: change the route to a flat conversation object with `turns`.

Reason: that would contradict the more transport-specific HTTP catalog and cause avoidable route/client churn.

### D2. Add persisted conversation versions

Add `conversations.version integer NOT NULL DEFAULT 1 CHECK >= 1` to `docs/database-schema.txt`, SQLAlchemy, and one additive Alembic revision. Create returns version 1; rename locks the owned row, compares `If-Match`, increments exactly once, and returns the new ETag. Delete locks and compares the version before deletion.

Rejected alternative: synthesize version from timestamps or return a constant.

Reason: neither can prove monotonic optimistic concurrency under same-timestamp or concurrent writes.

### D3. Follow global `(createdAt,id)` pagination

Order conversations by `created_at DESC, id DESC`, using the public conversation ref as the tie-breaker. A cursor contains only the prior conversation ref in a versioned base64url envelope. On the next request, the service owner-filters that ref, reads its `(created_at,id)` position, and applies the keyset predicate. A missing, malformed, cross-owner, or deleted cursor target returns `cursor_expired`.

This design needs no signing key: tampering can only select another opaque conversation ref, and the authoritative owner predicate rejects cross-owner refs before deriving a position.

Rejected alternatives:

- `updatedAt` ordering, because it conflicts with the global contract and makes rename reorder pages.
- A signed cursor with a new deployment secret, because no key lifecycle is approved and owner-filtered lookup already supplies the authorization boundary.

### D4. Add closed conversation audit events

Approve these internal event names:

- `conversation.created`
- `conversation.renamed`
- `conversation.deleted`

Each mutation uses `commit_protected_mutation` with the current session/user revalidated inside the committing transaction. Audit metadata contains no title, question, answer, Evidence excerpt, raw request body, session token, or private source/block ID. Tests force audit failure and prove product rollback.

Rejected alternative: defer all conversation auditing to P8.

Reason: P8 owns system-wide coverage, but the root invariant requires each protected mutation to be atomic when it lands.

### D5. Make one explicit create-idempotency choice

Two coherent options exist; one must be approved.

#### Option A — defer conversation-create `Idempotency-Key` explicitly

Amend the `POST /conversations` row to say `Idempotency-Key deferred pending the shared durable create-operation record contract`, and narrow P7-01 completion claims accordingly. Keep `(conversation_id,client_request_id)` turn idempotency unchanged.

This matches the residual treatment already recorded for model-profile, domain, and source create/operation routes, but leaves the global create-idempotency contract incomplete for a later approved cross-capability slice.

#### Option B — approve a shared durable idempotency record now

Add a product-owned schema that stores only:

- owner/actor scope
- capability/operation scope
- SHA-256 key hash
- normalized request fingerprint
- safe terminal status and resource linkage/projection needed for replay
- created/expiry timestamps
- a uniqueness constraint over actor + capability + key hash

The contract must also decide retention, replay after target deletion, key reuse after expiry, concurrent first-writer behavior, and privacy/audit treatment. P7-01 would then implement the shared facility rather than a conversation-only table.

Recommendation: Option A for P7-01, followed by one separately approved shared idempotency slice before Phase 1 release. Option B materially expands P7-01 and cannot be safely inferred from the current schema.

### D6. Clarify public conversation and turn identifiers

Choose one of:

- Declare the random UUID primary keys for `conversations` and `conversation_turns` to be intentionally public opaque refs, not private IDs; or
- Add separate unique `public_ref` columns and migrate all public DTO/SSE payloads to them.

Recommendation: add separate `public_ref` columns for consistency with source documents and Evidence refs. If the smaller first option is preferred, the database/schema and privacy contracts must explicitly classify these two PKs as public opaque identifiers so the root private-ID rule is not ambiguous.

## Additional required P7-01 proof

Regardless of the choices above, the implementation-ready plan must require:

- current session/user enabled state revalidation inside every mutation transaction;
- CSRF and allowed-Origin tests for create, rename, and delete;
- slice-scoped privacy scans across responses, errors, structured logs, audit rows, traces, metrics, snapshots, and failure artifacts;
- owner-filtered timing/error-shape checks for unknown and other-owned refs;
- PostgreSQL barriers for stale rename, delete/delete, disablement/mutation, and delete/turn-insert races;
- filtering of individually redacted Evidence rows even if brownfield parent state is inconsistent.

## Authority files requiring coordinated amendment

- `docs/contracts/http-api-catalog.md`
- `docs/contracts/dto-schema-catalog.md`
- `docs/database-schema.txt`
- `docs/interaction-behavior-prd.md` if create-idempotency or identifier classification changes acceptance behavior
- `docs/architecture/data-and-lifecycle.md`
- `docs/architecture/security-operations-and-quality.md`
- `docs/quality/definition-of-done.md` only if clarification is needed; invariants must not be weakened
- `docs/plans/2026-07-26-001-feat-conversation-ownership-plan.md` after the decisions are approved

## Approval record

The user approved this proposal on 2026-07-26. P7-01 proceeds with D1-D4, D6, and D5 Option A.
