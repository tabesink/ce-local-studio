# P7-04 Sealed SSE Live Resume Replay Pipeline Inventory

Date: 2026-07-27

Owner: P7-04

Status: DONE - inventory complete before behavior changes

Requirements and decisions: R1–R13; KTD1–KTD9; M-03; M-10; C-01; C-04;
FR-06; DRIFT-23/24/25;
`docs/plans/2026-07-27-004-feat-sealed-sse-replay-pipeline-plan.md`.

## Scope

- Inventory retain/modify/defer for the request-coupled stream producer,
  event ledger helpers, cancel path, resume projector, idempotent
  start/attach, and worker registry before U2–U6 behavior edits.
- Pin KTD1 (durable worker/lease), KTD2 (turn lease columns + claim fence),
  KTD3 (cooperative cancel), and KTD8 (browser reducer / redaction defer).
- Enumerate production callers of `stream_turn_events`,
  `stream_turn_events_by_turn`, `cancel_turn`, `_persist_event`, and
  `build_workers`.
- Record review-time implementation constraints (execution generation fence,
  atomic accept, abort-aware outbound ports, retained-sequence floor) without
  inventing public fields.

## Disposition register

| Surface / call site | Prior evidence | Disposition | P7-04 target |
| --- | --- | --- | --- |
| `stream_turn_events` | `start_or_replay_turn` then `TurnOrchestrator.stream_turn` in request generator | modify | Accept/attach only; open ledger tail; never own retrieval/synthesis |
| `TurnOrchestrator.stream_turn` | Runs direct/RAG synchronously; replay dumps `_stored_events` | modify | Worker-owned execute path under lease; cancel/lease checks around persist |
| `_streaming_sse_response` (`routes.py`) | `finally` closes work generator on disconnect (DRIFT-25) | modify | Close only the tail iterator; must not cancel turn work |
| `stream_turn_events_by_turn` / `_stored_events` | Finite historical dump `sequence > after`; no live tail | modify | Live-tail while `running`; terminal end; owner path-bound resolver |
| `start_or_replay_turn` | Fingerprint match returns existing; mismatch `client_request_conflict` → `idempotency_conflict` | retain-and-modify | Atomic accept (turn + refs + accepted/route) before claimable; running identical → attach/tail not one-shot dump |
| `_persist_event` | `max(sequence)+1` without turn lock; commit before yield | modify | Turn-row lock / claim-generation fence; refuse appends after terminal / stale claim |
| `_complete_turn` / `_fail_turn` / `_cancel_running_turn` | Terminal state + terminal event in one transaction | retain-and-extend | Single-terminal CAS; cooperative cancel fence; reclaim fail-closed after answer deltas |
| `cancel_turn` | Owner `get_owned_turn` then `_cancel_running_turn`; no outbound abort | modify | Keep owner 404 masking; signal worker; abort-aware synthesis/retrieval |
| Terminal payload `replay` | Stored/served as `replay:false` even on GET/attach of terminals | modify | Emit-time `replay:true` for terminal attach/GET; reconstruct from safe state |
| Turn-event `cursor_expired` | ErrorCode exists; only conversation-list uses 410 today | add | Durable retained-sequence floor / reconstructability check + `terminalSnapshot` |
| `ConversationTurn` lease fields | Absent in ORM and `docs/database-schema.txt` | add | `lease_owner`, `lease_expires_at`, `execution_generation`, `events_retained_after`, `claimable_at` |
| `worker.py` `build_workers` / `run_once_pass` | prep → index → delete only | modify | Register turn worker; claim order includes turns without starving prep/index/delete |
| Synthesis / retrieval ports | No cancel/abort token; blocked I/O ignores DB cancel | modify | Internal cancel/lease-lost signal between chunks + blocked-call abort/timeout path |
| Redaction helpers | Present in `chat_turns.py` | defer | P7-05 ownership; do not claim |
| Browser reducer / DRIFT-03/06 consumer | Fixtures schema-only | defer | P9-02; ship producer transcripts only |
| DRIFT-23 | Identical running retry not live-attach | modify → close in U6 | Unique-conflict attach + fingerprint conflict PG proof |
| DRIFT-24 | Retired buffered stream semantics | modify → producer half in U6 | Producer sealed; parser/reducer residual stays P9-02 |
| DRIFT-25 | Socket-coupled execution | replace → close in U6 | Durable worker disconnect-survives proof |

## Production call graph (target after U3)

```text
POST /conversations/{conversationId}/turns:stream
  → stream_turn_events
      → start_or_replay_turn          # atomic accept → claimable_at
      → [testing] run_turn_workers_until_idle
      → _tail_turn_events             # durable ledger only

GET /conversations/{conversationId}/turns/{turnId}/events?after=N
  → stream_turn_events_by_turn
      → get_owned_turn
      → _tail_turn_events

worker process
  → build_workers → prep / index / turn / delete
  → ConversationTurnWorker.run_once
      → claim lease + execution_generation++
      → TurnOrchestrator.stream_turn under lease
```

## Implementation constraints pinned from plan + review

1. **KTD1:** HTTP only tails; worker owns retrieval/synthesis.
2. **KTD2:** Lease fields + `execution_generation` fence on append/finalize.
3. **KTD3:** Cooperative cancel — status fence plus abort-aware synthesis/retrieval; disconnect ≠ cancel.
4. **KTD7 / AE9:** Reclaim with existing `answer.delta` and no terminal → safe `turn.failed`.
5. **Atomic accept:** Turn row, accepted-ref linkage, and `turn.accepted`/`route.selected` commit before `claimable_at`.
6. **Owner path binding:** Resume/attach/cancel/snapshot resolve `(conversationId, turnId, owner)` together.
7. **Cursor expiry:** Durable `events_retained_after` floor — do not treat “no later events” as `410`.
8. **KTD8:** Browser reducer deferred to P9; redaction deferred to P7-05.

## Explicit deferrals

| Surface | Owner |
| --- | --- |
| Canonical browser reducer / chunk parser / `/chat` UI | P9-02 |
| Source/domain delete `turn.redacted` ownership | P7-05 |
| System-wide privacy/audit sink scanning | P8 |
| Deployed-ingress stream-drain evidence | P12 |
