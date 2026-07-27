# P7-01 Conversation Foundation Inventory

Date: 2026-07-26

Status: reconciled

## Retained

- Private UUID primary keys and existing foreign-key/cascade relationships for
  conversations, turns, events, Evidence refs, and accepted composer refs.
- The existing turn route/status/counter checks, one-running-turn partial
  index, client-request uniqueness, append-only event ledger, and event
  payload digests.
- Existing owner relationships, durable user questions, safe terminal answer
  projection, and redaction omission behavior.
- Existing Evidence and accepted-ref public refs.

## Modified in P7-01

- Added dedicated persisted `conv_…` and `turn_…` UUID4 public refs with
  PostgreSQL server defaults, unique indexes, upgrade backfill, and rollback
  support.
- Added positive conversation versions, strong ETags, owner-bound
  `(created_at DESC, id DESC)` pagination, and current-row locking.
- Added content-free `conversation.created`, `conversation.renamed`, and
  `conversation.deleted` audit events.
- Replaced private conversation/turn IDs at the current HTTP, SSE,
  resume/cancel, and composer-discovery boundaries.
- Added a replay-only compatibility projection that substitutes the
  owner-authorized conversation public ref in legacy `turn.accepted` events
  without changing stored payload bytes or digests.
- Added the shared parent-row lock before turn insertion so deletion and
  submission cannot create an orphan.
- Registered the nested `ConversationDetailResponseDto`, CRUD envelopes,
  paging transport, ETag/If-Match behavior, private no-store responses, and
  generated browser contracts.

## Deferred

- Durable `Idempotency-Key` behavior for conversation creation remains
  deferred until the shared create-operation idempotency record is approved.
- P7-02 through P7-05 continue to own intent classification, orchestration,
  canonical live/resume/replay behavior, terminal persistence, cancellation
  semantics, and source/domain redaction integration.
- P8 retains system-wide denial-audit and cross-sink privacy coverage.

## Removed from public compatibility

- Private conversation UUIDs and private turn UUIDs are no longer accepted as
  route identifiers.
- The pilot flat conversation detail shape is replaced by the approved nested
  `{conversation,turns}` response.
- The pilot `conversation_not_found` error is replaced by the canonical,
  ownership-indistinguishable `not_found` envelope.
