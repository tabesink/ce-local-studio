# P7-04 Sealed SSE Live Resume Replay Pipeline Evidence

Date: 2026-07-27

Owner: P7-04

Status: DONE

Requirements and cases: FR-06; M-03; M-10; C-01; C-04; R1–R13; AE1–AE8;
KTD1–KTD9; DRIFT-23/24/25 (producer ownership).

## Implemented boundary

- Inventory pinned retain/modify/defer in
  `docs/_scratch/p7-04-sse-pipeline-inventory.md` before behavior edits.
- Turn execution leases land in migration `e9f2a1b83c70` with ORM +
  `docs/database-schema.txt` private fields (`lease_owner`,
  `lease_expires_at`, `execution_generation`, `events_retained_after`,
  `claimable_at`). Supported Alembic head is `e9f2a1b83c70`.
- HTTP `POST turns:stream` / `GET .../events` authorize and live-tail the
  durable ledger only. `ConversationTurnWorker` owns retrieval/synthesis after
  accept and is registered beside prep/index/delete workers.
- Cooperative cancel CAS-seals `cancelled` + `turn.cancelled`, clears lease
  fields, and stops further non-terminal appends via `_execution_fence_open`
  between synthesis tokens and after retrieval.
- Terminal attach/GET reconstructs terminal payloads with emit-time
  `replay:true` from safe turn/evidence/ref state. Live first emission keeps
  stored `replay:false`.
- Unreconstructable cursors (`after < events_retained_after`) return
  `410 cursor_expired` with authorized `terminalSnapshot`
  (`turnId`, `status`, `answer`, `evidence`, `citations`).
- Producer SSE fixtures added for no-grounded-context, evidence-only,
  terminal-replay, and disconnect-resume (plus existing cancel / gap /
  duplicate / direct-success / redacted).

## Verification

### Focused non-PostgreSQL suite

```text
cd app
.\.venv\Scripts\python.exe -m pytest `
  tests\test_turn_execution_leases.py `
  tests\test_chat_sse_http_contract.py `
  tests\test_generated_sse_contract.py `
  tests\test_chat_orchestration.py `
  tests\test_canonical_turn_event_behavior.py `
  tests\test_chat_turn_route_http_contract.py -q
```

Expected: PASS (leases, cooperative cancel, terminal replay, cursor expiry,
orchestration regressions, SSE schema fixtures, turn-route HTTP).

### PostgreSQL 16 race suite (opt-in)

```text
cd app
$env:CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS='1'
$env:CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://...'
.\.venv\Scripts\python.exe -m pytest tests\test_postgres_turn_leases.py -q
```

Covers identical attach once, fingerprint conflict, cancel-vs-worker single
terminal, answer-delta reclaim fail-closed, and disconnect-without-cancel
completion. Skips unless the disposable-database opt-in is set.

Local run (2026-07-27) against `127.0.0.1:5438` disposable PostgreSQL 16:
`6 passed` after seeding TrustedRuntimeResolver credentials in worker races
and sealing cancel while the worker is blocked between answer deltas.

### Contract generation

```text
app/.venv/Scripts/python.exe scripts/generate_openapi.py
cd app/client && npm run generate:api
```

OpenAPI registers `CursorExpiredEnvelope` / `TerminalSnapshotDto` on
`GET .../turns/{turnId}/events` `410`. SSE JSON Schema intentionally unchanged
(no new event types).

### Privacy scan

Focused assertions prove:

- lease fields never appear in `safe_turn_summary` / public DTOs
- cancel/cross-owner returns identical `404` masking
- cursor-expired snapshot uses only authorized public fields
- orchestration privacy sentinels remain absent from public projections

## Residuals

- P7-05: source/domain delete redaction append / `turn.redacted` ownership.
- P8: system-wide privacy/audit sink scanning.
- P9 / DRIFT-03 / DRIFT-06 consumer half: browser canonical reducer, chunking
  parser, and `/chat` UI states. Producer fixtures are schema-valid inputs only.
- DRIFT-24 residual: incremental parser + reducer tests remain P9-02; producer
  sealing is closed in this slice.
- P11: deeper composer-ref assembly beyond current turn fencing.
- P12: deployed-ingress unbuffered SSE / stream-drain evidence.
- Synthesis/retrieval blocked-call hard abort beyond cooperative
  between-chunk fences remains best-effort via timeouts.

This slice does not claim the closed Phase 1 chat capability manifest complete
and does not claim browser reducer DoD.
