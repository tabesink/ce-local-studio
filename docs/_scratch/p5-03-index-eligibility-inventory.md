# P5-03 Index Submit/Poll/Retry/Cancel/Delete and Query-Eligibility Inventory

Date: 2026-07-25

Owner: P5-03

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-05; A-08; A-09 index cleanup half; DRIFT-27
cancel/recovery half; DRIFT-28 persisted backoff/fairness remainder;
DRIFT-32 index uncertain reconcile; `docs/contracts/http-api-catalog.md`
index retry/cancel; `docs/architecture/data-and-lifecycle.md` LightRAG
index port + uncertain non-terminal rule.

## Scope

- Close admin index retry/cancel HTTP envelopes on closed `AdminSourceDto`
  (`202`/`200` `{source}`) with approved ErrorCode mapping.
- Harden `SourceIndexWorker` submit→poll→ready: lease heartbeat during
  external work, persisted readiness backoff via lease-expiry gating, and
  timeout→uncertain→readiness-probe reconcile before re-submit (DRIFT-28 /
  DRIFT-32 index halves).
- Prove query-eligibility: prepared + `ready` + current request identity +
  domain available; `processing` never eligible (A-08).
- Prove index remote cleanup under source delete does not restore eligibility
  (A-09 half already owned by P4-04 cleanup call; reverify from indexing).
- Add advisory `indexRetry` / `indexCancel` source `allowedActions`.

## Out of scope

- Removing the process-wide native LightRAG lifecycle lock before per-domain
  concurrency is separately proven (DRIFT-27 concurrency residual).
- Idempotency-Key transport persistence (catalog residual shared with P4-04;
  no approved idempotency store for index mutations yet).
- Member Library / Evidence document routes (P6 / P9).
- Worker graceful stop-claim drain (P10-03 / DRIFT-31).
- Collapsing private index CHECK vocabulary to public DTO names.
- New `index_operations` table / `OperationDto.targetKind=index` rows —
  index lifecycle remains on `source_documents` per schema authority.

## Disposition register

| Surface | Current evidence | Disposition | P5-03 action |
| --- | --- | --- | --- |
| `retry_source_index` / `cancel_source_index` | Lifted services + routes without response_model | modify | Closed envelopes; approved ErrorCode map |
| `SourceIndexWorker.run_once` | Submit/poll; timeout→fail; no heartbeat/backoff | modify | Heartbeat; uncertain leave-non-terminal; backoff poll |
| Claim accepted poll gating | Lease only (P5-01) | modify | After not-ready poll, schedule lease-expiry backoff |
| `source_is_query_eligible` | Helper present; dead deleting branch; no focused proof | modify | Harden + unit/PG eligibility proof |
| `_source_allowed_actions` | Prep retry/cancel/delete only | modify | Add `indexRetry` / `indexCancel` |
| Local/native adapters + renderer | P5-02 proven | retain-and-reverify | Reuse for submit/poll/delete proofs |
| Claim lease assignment | P5-01 proven | retain-and-reverify | Keep SKIP LOCKED + lease assign |
| Schema index columns | No `next_poll_at` in authority | retain-and-reverify | Backoff via `index_lease_expires_at` (no migration) |
| Process-wide native lock | P5-02 residual | defer | Keep; document residual |

## Adapter / worker decisions

1. **Timeout on submit** maps to non-terminal `submitting` with private
   `index_error_code=source_index_uncertain` and short lease-expiry backoff.
   Next claim probes readiness before re-submit.
2. **Not-ready poll** clears lease owner and sets
   `index_lease_expires_at = now + CE_SOURCE_INDEX_POLL_BACKOFF_SECONDS`
   so peers are not starved by a spinning accepted row (DRIFT-28).
3. **HTTP codes** map private service codes onto the closed source/index /
   dependency ErrorCode set (`operation_conflict`, `dependency_unavailable`,
   `not_found`, `validation_error`, `domain_state_conflict`).
4. **Delete** remains source-delete-owned via `cleanup_index_before_source_delete`;
   P5-03 proves eligibility stays false after fence/cancel.

## Retained invariants

- Internal index states and public `processing`/`deleting` projection unchanged.
- Generation/request fences reject stale completions and cancel races.
- Adapters never authorize or mutate product `index_state`.
- Private request ids, remote ids, rendered handoff, and block IDs stay private.
- Query eligibility requires domain_available + prepared + ready + current
  request identity.

## Gaps closed by task-owned evidence

1. Unit: eligibility matrix; HTTP error mapping; poll backoff scheduling;
   timeout→uncertain (mocked client).
2. PostgreSQL 16: retry→worker submit/poll→ready→eligible; cancel remote
   absence; in-progress conflict; processing not eligible; backoff skips
   recently polled accepted; uncertain reclaim probes before re-submit.
