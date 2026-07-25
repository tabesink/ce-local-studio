# P5-01 Index State / Generation Fields and Worker Claim Loop Inventory

Date: 2026-07-25

Owner: P5-01

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-05; A-08 race half (lease/generation fence);
DRIFT-28 claim/lease half; `docs/database-schema.txt` source_documents index
fields; brownfield generation/lease foundation reverify (index half).

## Scope

- Inventory and prove `source_documents` index state/generation/lease/request
  identity fields against the approved schema (internal CHECK vocabulary).
- Harden `SourceIndexWorker._claim_next_source` so every claim path assigns a
  lease owner/expiry under `FOR UPDATE SKIP LOCKED`: queued→submitting,
  expired submitting reclaim, and accepted readiness poll when lease is absent
  or expired.
- Prove generation-fenced completion helpers reject stale
  generation/request_id completions.
- Record retain/modify dispositions before changing the claim loop.

## Out of scope

- Versioned canonical-block renderer and vendored/native LightRAG adapter
  (P5-02).
- Admin index submit/poll/retry/cancel/delete HTTP envelopes and query
  eligibility service closure (P5-03).
- Persisted readiness backoff / fair queue scheduling beyond lease gating
  (DRIFT-28 remainder → P5-03).
- Uncertain remote outcome reconciliation for index submit (DRIFT-32 index
  half → P5-03).
- Collapsing private index_state CHECK values to public DTO vocabulary
  (`processing`/`deleting`). Schema authority keeps
  `submitting`/`accepted`/`cancelling`; public projection remains P4-01.

## Disposition register

| Surface | Current evidence | Disposition | P5-01 action |
| --- | --- | --- | --- |
| Baseline `index_state` CHECK + `index_generation` | Present in baseline migration + ORM | retain-and-reverify | PG schema proof of CHECK/default/index |
| `index_request_id` / `index_content_hash` / remote id / errors / timestamps | Present | retain-and-reverify | Include in schema column proof |
| `index_lease_owner` / `index_lease_expires_at` | Present; claim under-uses them | modify | Assign lease on every claim path |
| Public IndexState mapping | P4-01 `_public_index_state` | retain-and-reverify | No CHECK collapse; mapping stays |
| `SourceIndexWorker._claim_next_source` | Claims accepted without lease; reclaim omits lease reassignment | modify | Lease all claimable states; skip unexpired accepted leases |
| `mark_index_*_if_current` generation fence | Present; no PG proof | retain-and-reverify | Prove stale generation no-op |
| LightRAG client / renderer | Lifted pilot | defer | P5-02 |
| Index HTTP APIs / eligibility | Lifted pilot | defer | P5-03 |

## Retained invariants

- Internal index states remain
  `not_requested|queued|submitting|accepted|ready|failed|cancelling|cancelled`.
- Public DTOs continue to map `submitting|accepted→processing` and
  `cancelling→deleting`.
- Workers claim with PostgreSQL locking; stale generation/request completions
  are no-ops.
- Claimed index work carries lease owner/expiry; expired leases are reclaimable.
- Object keys, remote IDs, request IDs, and rendered prompts stay private.

## Gaps closed by task-owned evidence

1. Disposable PostgreSQL 16 schema proof for index columns, CHECK, and
   `(domain_id, index_state)` index.
2. PostgreSQL claim proof: queued→submitting lease assign; expired submitting
   reclaim by a second worker; accepted skipped while lease unexpired then
   reclaimable after expiry.
3. Generation fence: `mark_index_ready_if_current` / `mark_index_accepted_if_current`
   reject advanced generation or mismatched request id.
