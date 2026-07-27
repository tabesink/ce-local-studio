# P7-05 Source and Domain Delete Redaction Inventory

Date: 2026-07-27

Owner: P7-05

Status: DONE - inventory complete before behavior changes

Requirements and decisions: R1–R11; KTD1–KTD7; M-11 (chat/detail/SSE half);
A-09; A-10; FR-08; DRIFT-29 chat-redaction half;
`docs/plans/2026-07-27-005-feat-delete-redaction-omission-plan.md`.

## Scope

- Inventory retain/modify/defer for redaction helpers, source/domain delete
  enqueue fences, worker/purge re-redact, P7-04 event fences, and public
  omission surfaces before U2–U4 behavior edits.
- Pin KTD2 (domain enqueue parity + token expiry), KTD4 (durable live-tail),
  and KTD5 (running-turn mid-delete fence).
- Forbid inventing public fields, ErrorCodes, SSE event types, or a second
  fanout channel.
- Explicit residual: evidence/document location/content route denial (P9-03);
  browser panel/cache half of M-11 (P9); privacy/audit breadth (P8).

## Disposition register

| Surface / call site | Prior evidence | Disposition | P7-05 target |
| --- | --- | --- | --- |
| `_redact_turns` / `_sanitize_turn_events_for_redaction` | Clears answer/evidence fields; appends `turn.redacted`; `commit=` flag | retain-and-prove | Keep unit redaction + sanitize; prove delete-driven omission |
| `redact_turns_for_source` | Used by `enqueue_delete_source` with `commit=False` | retain | Source fence path stays; U4 owns delete-driven proof |
| `redact_turns_for_domain` | Selects only `domain_rag`+`domain_id`; always commits | modify | Add `commit=`; expand dependent-turn union (evidence/composer-linked) |
| Domain dependent-turn selection | Missing as a single composable helper | add | Union domain_rag + per-source evidence/composer turns, deduped |
| `enqueue_delete_source` | Fence+redact+token expiry+queue in protected mutation | retain-and-prove | Code pattern retained; PostgreSQL omission proof in U4 |
| `enqueue_delete_domain` | Fence+queue only; no redact/token expiry | modify | Redact dependent turns + expire tokens per source in mutate() |
| `DomainDeleteWorker` + `purge_domain_sources_local` | Worker-time redact + per-source re-redact | retain | Idempotent safety net only after enqueue authority |
| `_expire_composer_tokens_for_source` | Source delete/purge only | retain-and-reuse | Call from domain enqueue for every domain source |
| `_finalize_turn_if_running` / `_persist_event` / `_execution_fence_open` | P7-04 CAS; redacted accepts only `turn.redacted` | retain-and-prove | Running-turn late worker cannot un-redact (U4 barrier) |
| `_project_turn_dto` / terminalSnapshot | Redacted DTO omission exists for hand-seeded turns | retain-and-prove | Delete-driven detail/SSE/terminalSnapshot omission |
| SSE live-tail / resume | P7-04 durable ledger | retain-and-prove | Observe `turn.redacted` via ledger only (no fanout) |
| Evidence/document location/content routes | Catalog-allowed missing | defer | P9-03; do not invent routes |
| Browser redaction UI / reducer | Not started | defer | P9 |
| System-wide privacy/audit sink scan | Not started | defer | P8; DRIFT-29 audit half remains |
| Composer assembly depth | Token expiry on delete; deeper rules later | defer | P11 |
| DRIFT-29 chat-redaction half | Source fence code; domain enqueue gap; omission unproven | modify → close chat half in U4 | Do not mark full DRIFT-29 or full M-11 closed |

## Implementation constraints pinned from plan

1. **KTD1:** Extend existing helpers; no parallel redaction service or event protocol.
2. **KTD2:** Domain delete redacts + expires tokens at enqueue inside `commit_protected_mutation`.
3. **KTD3:** Dependent turns = `domain_rag` by domain_id ∪ evidence/composer-linked turns for domain sources.
4. **KTD4:** Live observation = durable ledger append + P7-04 live-tail only.
5. **KTD5:** Running-turn redaction in scope; prove with PostgreSQL barriers.
6. **KTD6:** Public omission on existing conversation/SSE routes; location denial residual P9-03.
7. **KTD7:** Cleanup retry must never undo redaction, token invalidation, or retrieval fencing.

## Explicit deferrals

| Surface | Owner |
| --- | --- |
| Browser redaction UI / open Evidence panel close | P9 |
| Evidence/document location and content HTTP denial | P9-03 |
| System-wide privacy/audit sink scanning; DRIFT-29 audit breadth | P8 |
| Deeper composer-ref assembly / fingerprint invalidation | P11 |
| Deployed-ingress adversarial deletion review | P12-03 |
| New public fields / ErrorCodes / SSE event types | Forbidden |
| Separate SSE fanout channel | Forbidden |
