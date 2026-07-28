# P7-06 Synthesis Isolation and Turn Lease Heartbeat Inventory

Date: 2026-07-28

Owner: P7-06

Status: DONE - inventory complete before behavior changes

Requirements and decisions: R1–R6; KTD1–KTD5; AE1–AE4;
`docs/plans/2026-07-28-009-feat-p7-06-synthesis-isolation-heartbeat-plan.md`.

## Scope

- Inventory retain/modify/add for synthesis message assembly, turn lease claim,
  and prep/index heartbeat patterns before U2–U3 behavior changes.
- Pin threat-model trust fields and lease-validation residual.

## Threat model / trust-field table

| Field in synthesis messages | Trust | Isolation disposition |
| --- | --- | --- |
| Fixed system preamble / grounded instructions | trusted | outside envelope |
| Section headers `Evidence:` / `Approved context:` | trusted structure | outside envelope |
| Server-owned assembly `kind` enum token | trusted | outside envelope (prefix only) |
| Evidence `citation_label` + `source_label` + `excerpt` | untrusted (corpus) | **full-line wrap** inside delimiters |
| Assembly `label` + `body` | untrusted (composer refs) | **full-line wrap** inside delimiters |
| Current user `message` / prior user questions | member-authored; separate `user` role | deferred (Open Question) |

Adversary for this slice: corpus/composer-ref content injected into system
message via Evidence or assembly — not member self-prompting via user role.

## Disposition register

| Surface / call site | Prior evidence | Disposition | P7-06 result |
| --- | --- | --- | --- |
| `adapters/synthesis.py::_build_messages` | Flat join of Evidence/assembly into system string; no delimiters | modify | Per-call random delimiter envelope; full-line wrap; fail closed pre-provider |
| `OpenAISynthesisAdapter.stream` | Delegates to transport; injected transport skips `_build_messages` | modify | Build/validate messages before dispatch; pass prebuilt messages into transport |
| `PromptAssemblyService` | Caps + `_evidence_body`; no provider shape | retain | Unchanged; isolation at adapter boundary |
| `TurnOrchestrator` | Passes Evidence/assembly DTOs to synthesis facade | retain | Must not assemble wire format |
| `ConversationTurnWorker._claim_next_turn` | Sets lease_owner/expires; bumps execution_generation | retain | Claim fence unchanged |
| Turn mid-execution heartbeat | Absent (P10-03 residual) | add | Daemon-thread + generation-gated compare-and-extend + liveness |
| `_execution_fence_open` | status + generation only | retain | Continues to stop stale writers; not replaced by heartbeat |
| Prep/index `_lease_heartbeat_seconds` + thread wrapper | Proven pattern | retain-and-mirror | Copy structure; turn heartbeat adds `execution_generation` predicate |
| Settings `turn_lease_seconds > synthesis_timeout_seconds` | Present | retain | KTD5 residual: does not require `> retrieval + synthesis`; document only |
| Public API/DTO/SSE | Closed | retain | No contract changes (KTD3) |
| Prior-user delimiter wrap | Open Question | defer | Follow-up if bypass proven |
| Dedup `_lease_heartbeat_seconds` across services | Three copies | defer | Follow-up cleanup |

## Credit vs gap

| Area | Credit | Gap (this slice) |
| --- | --- | --- |
| Synthesis port / registry | P7-03 adapter + tests | Delimiter isolation + transport contract |
| Composer assembly | P11-03 caps / privacy plants | Apply wrap at synthesis boundary |
| Turn leases | P7-04 claim + generation + PG races | Mid-turn heartbeat + liveness |
| Heartbeat precedent | Prep/index/domain thread+session | Turn-specific wrapper + generation gate |
| Reclaim fail-closed after answer.delta | `test_postgres_turn_leases.py` `test_ae1_*` | Do not duplicate; AE3/AE4 are new |

## Minimum safe lease residual (documented, not expanded)

Defaults: `turn_lease_seconds=180`, `synthesis_timeout_seconds=60`,
`retrieval_timeout_seconds=30`. Current validation requires only
`turn_lease_seconds > synthesis_timeout_seconds`. Heartbeat is mandatory
compensation for long outbound brackets. Absurdly short leases remain
unsupported; tightening to `retrieval + synthesis` is deferred (KTD5).

## Production call graph (relevant)

```text
ConversationTurnWorker.run_once
  → claim lease
  → [U3] heartbeat thread around:
      TurnOrchestrator.stream_turn
        → retrieve (domain_rag) and/or synthesis
            → RegistrySynthesisStreamAdapter
                → OpenAISynthesisAdapter.stream
                    → [U2] _build_messages (delimiter envelope)
                    → transport(prebuilt messages)
```

## Test artifacts planned

| File | Role |
| --- | --- |
| `app/tests/test_synthesis_prompt_isolation.py` | U2 builder + AE1/AE2 |
| `app/tests/test_postgres_turn_lease_heartbeat.py` | U3 AE3/AE4 barriers |
| Credit `app/tests/test_postgres_turn_leases.py` | Existing reclaim fail-closed |

## Stop conditions checked

- No prompt persistence paths required
- No browser-visible fields
- P12-05 hard stream-drain remains out of scope
