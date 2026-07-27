# P7-03 Bounded Plan Retrieve Repair Synthesize Orchestration Inventory

Date: 2026-07-27

Owner: P7-03

Status: DONE - inventory complete before behavior changes

Requirements and decisions: R1–R11; KTD1–KTD8; M-03; M-07; FR-06;
`docs/plans/2026-07-27-002-feat-bounded-rag-orchestration-plan.md`.

## Scope

- Inventory retain/modify/defer for `TurnOrchestrator`, the deterministic
  synthesis stand-in, `P6RetrievalPort`, event emission vs P7-04/P7-05,
  DRIFT-22 synthesis half, and single-shot budget/exit criteria before
  U2–U4 behavior changes.
- Capture the SSE compatibility baseline and pin KTD4 (single-shot) and
  KTD5 (`evidence_only` vs post-answer failure) as implementation
  constraints.
- Enumerate production callers of `TurnOrchestrator.stream_turn`,
  `SynthesisStreamAdapter`, and `P6RetrievalPort.retrieve`.

## Disposition register

| Surface / call site | Prior evidence | Disposition | P7-03 result |
| --- | --- | --- | --- |
| `TurnOrchestrator.stream_turn` | Replay stored events; require synthesis; branch on persisted route | retain-and-modify | Keep compatibility entry; wire typed synthesis; no sealed SSE claim |
| `_stream_direct` | Stand-in tokens → `answer.delta*` → `direct_llm` `0/0/0`; fail/empty → `turn.failed` | modify | Typed provider port; keep fail-on-empty for direct |
| `_stream_domain_rag` | Plan → retrieval `1/1` → empty refuse / evidence → grounded or `evidence_only` | modify | Enforce KTD5 sequencing; keep post-start empty refusal |
| `SynthesisStreamAdapter` | Deterministic success strings; ignores runtime config | replace | DRIFT-22 synthesis half; parser-style typed port + OpenAI adapter |
| `SynthesisProviderError` | Empty exception class; unused by stand-in | retain-and-extend | Typed safe failures from new adapter |
| `P6RetrievalPort` | Wraps `retrieve_internal_scoped_evidence`; empty eligible → `[]` | retain | Never use public Evidence HTTP projector |
| `operation_for_message` / `intent_for_operation` | Keyword → operation → intent; private | retain-and-refine | Closed one-shot plan value; never browser-visible |
| Budget counters | Hardcoded `0/0/0` or `1/1/0`; `repairAttemptCount` never >0 | retain-and-verify | Single-shot fence (KTD4); no multi-attempt repair |
| `_persist_event` / `_complete_turn` / `_fail_turn` | Durable ledger + CAS finalize | retain | Compatibility seam only; sealing deferred to P7-04 |
| Cancel / redaction helpers (same file) | Present | defer | P7-04 cancel; P7-05 redaction |
| Sealed SSE attach/replay/cancel | HTTP baselines exist | defer | P7-04 ownership; compatibility-only in this slice |
| DRIFT-22 | Parser half DONE; synthesis stand-ins remain | modify-note → close in U5 | Status stays IN_PROGRESS until synthesis proven |
| Synthesis timeout / max-output settings | Absent from `Settings` | add | U2; mirror parser/retrieval timeout fail-closed validation |

## Production call graph

```text
POST /conversations/{conversationId}/turns:stream
  → stream_turn_events
      → start_or_replay_turn          # P7-02 (classification/eligibility)
      → TurnOrchestrator(
            synthesis_adapter=app.state.synthesis_stream_adapter or default,
            retrieval_port=app.state.retrieval_port or default,
        )
          → stream_turn
              → [replay] _stored_events
              → direct_llm  → _stream_direct
                  → SynthesisStreamAdapter.stream_direct
              → domain_rag  → _stream_domain_rag
                  → operation_for_message → intent_for_operation
                  → P6RetrievalPort.retrieve
                      → retrieve_internal_scoped_evidence
                  → SynthesisStreamAdapter.stream_grounded
```

### Callers of orchestration helpers

| Symbol | Production callers | Test/scaffolding callers | Disposition |
| --- | --- | --- | --- |
| `TurnOrchestrator.stream_turn` | Only via `stream_turn_events` ← HTTP turn stream | Indirect via SSE HTTP suites | sole production orchestration entry |
| `SynthesisStreamAdapter` | Default when `app.state.synthesis_stream_adapter` unset | Subclassed as `DeterministicSynthesis` in SSE/route HTTP tests | replace production default; preserve injection seam |
| `P6RetrievalPort.retrieve` | Only `TurnOrchestrator._stream_domain_rag` | Direct call in `test_canonical_turn_event_behavior.py` | retain internal seam |

`create_app` does not register a production synthesis adapter; the live path
uses the deterministic stand-in unless tests inject
`app.state.synthesis_stream_adapter`.

## Current observed orchestration outcomes (pre-U2)

| Scenario | Observed outcome |
| --- | --- |
| Direct success | Stand-in `"I can help with that."` → deltas → `completed` / `direct_llm` / `0/0/0` |
| Direct fail/empty | `turn.failed` / `provider_failure` |
| Domain, no eligible sources | Post-start: retrieval started → completed `no_grounded_context` → `completed` / `no_grounded_context` / `1/1/0`, null answer |
| Domain, eligible, zero mapped Evidence | Same as empty (`[]` from port) |
| Domain, evidence + stand-in success | evidence → grounded stand-in → `grounded` / `1/1/0` |
| Domain, evidence + provider error after answer deltas | **`evidence_only`** — contradicts SSE legal sequence / KTD5 |
| Public Evidence HTTP empty corpus | Pre-stream `409 domain_no_eligible_sources` (different seam — do not reuse) |

### Empty-corpus post-start path (modify item)

`P6RetrievalPort` maps `had_eligible_sources=False` and empty mapped Evidence
to `[]`. Orchestrator treats both as post-start `no_grounded_context` on an
already-created turn. Turn-start eligibility still excludes the
no-eligible-sources predicate (P7-02 / KTD3). Public Evidence HTTP converting
empty corpus to pre-stream denial must not be used by orchestration.

### Answer-delta / `evidence_only` contradiction (modify item)

In `_stream_domain_rag`, a `SynthesisProviderError` (or empty answer handling)
completes `evidence_only` even when one or more `answer.delta` events were
already persisted. Target (KTD5 / R6): `evidence_only` only when no answer
delta has been persisted; after any answer delta, later empty/error outcomes
use safe `turn.failed` / provider-failure.

## Single-shot budget and plan constraints (implementation pins)

- **KTD4:** Private plan selects one retrieval operation; emit
  `retrieval.started` with `attempt:1` / `maxAttempts:1`; persist budgets
  `domain 1/1/0` or `direct 0/0/0`; never increment `repairAttemptCount`.
  No second retrieval attempt in Phase 1.
- **KTD8:** “Plan” means private closed control-flow selection via
  `operation_for_message` / `intent_for_operation`, not an agent plan.
  Never emit plan text, tool calls, or browser-visible reasoning.
- Note: retrieval `intent` is validated against `RETRIEVAL_INTENTS` but is
  not currently passed into `retrieve_internal_scoped_evidence` (ornamental
  for retrieve behavior). Do not invent multi-attempt rewrite repair.

## DRIFT-22 note (status flips in U5)

Current brownfield row: **IN_PROGRESS** — P4-03 closed parser half;
synthesis stand-ins remain P7-03. This inventory does not flip status.
U5 closes DRIFT-22 only when the typed OpenAI synthesis adapter +
fail-closed registry are proven with no-network fixtures.

## SSE compatibility baseline (2026-07-27)

Pre-change baseline:

```text
cd app && .venv/Scripts/python.exe -m pytest tests/test_chat_sse_http_contract.py -q --tb=no
```

Result: `2 passed`

Post-U3/U4 compatibility re-check (same command): `2 passed` alongside
`tests/test_chat_orchestration.py` + `tests/test_synthesis_adapters.py`.

| Test | Role for P7-03 |
| --- | --- |
| `test_m06_live_and_cursor_replay_use_canonical_sse_envelopes` | Post-start SSE order/replay — compatibility only; sealed claims deferred to P7-04 |
| `test_c01_cancel_http_state_and_replay_terminal_are_consistent` | Cancel/terminal — deferred P7-04; compatibility only |

New SSE failures caused by orchestration/adapter edits block closure;
otherwise cite this baseline as non-applicable for sealed attach/replay/
cancel ownership.

## Explicit exclusions

- No sealed SSE sequence validation, attach races, cursor expiry, or
  terminal DTO sealing (P7-04).
- No source/domain redaction (P7-05).
- No multi-attempt query-rewrite repair or `turn_budget_exhausted` for
  this single-shot posture.
- No client-visible plan/reasoning text; no ungrounded domain fallback.
- No new public fields or ErrorCodes.
- No Bedrock/Ollama concrete synthesis adapters (fail-closed registry only).

## Residual owners

- P7-04: sealed SSE live/resume/replay, attach races, cancel semantics,
  grounded-refusal/evidence-only terminal projection sealing.
- P7-05: source/domain delete redaction.
- P8: system-wide privacy/audit breadth.
- P9: chat UI.
- P11: deeper composer-ref assembly correctness beyond current turn fencing.
