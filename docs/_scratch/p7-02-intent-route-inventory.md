# P7-02 Server Intent Gate and Turn-Start Route Inventory

Date: 2026-07-27

Owner: P7-02

Status: DONE - inventory complete before behavior changes

Requirements and decisions: R1–R9; KTD1–KTD6; M-02; M-07; FR-06;
`docs/plans/2026-07-27-001-feat-server-intent-gate-plan.md`.

## Scope

- Inventory retain/modify/defer for the pattern classifier, turn-start
  classification entry, eligibility check, HTTP error projection, and
  non-authoritative helpers before U2/U3 behavior changes.
- Enumerate every pre-insert `ChatTurnError` code reachable from
  `start_or_replay_turn` so U3 can allowlist-project without inventing
  public behavior.
- Capture the SSE compatibility baseline and the empty-corpus eligibility
  exit criterion.

## Disposition register

| Surface / call site | Prior evidence | Disposition | P7-02 result |
| --- | --- | --- | --- |
| `services/chat_intent.py` `DOMAIN_REQUIRED_PATTERNS` / `requires_domain` | Closed Phase 1 pattern list matches PRD examples for the AE6 matrix | retain-and-reverify | Keep pattern family; pin AE6 fixtures; no NLU/LLM classifier. |
| `classify_turn_route` | Domain present → `domain_rag`; else pattern gate → `domain_required` or `direct_llm` | retain-and-reverify | Sole pure decision function; prove classify table and fail-closed pairs. |
| `normalize_optional_domain_id` | Strips/length-bounds only; does not enforce `DOMAIN_ID_PATTERN` | modify | Align optional body `domainId` with `domains.DOMAIN_ID_PATTERN` before classification success. |
| `_validate_effective_route` | Rejects unknown route, `domain_rag` without domain, `direct_llm` with domain | retain-and-reverify | Keep as pre-persist invariant fence. |
| `start_or_replay_turn` | Production HTTP path via `stream_turn_events`; classifies then validates eligibility before insert | retain-and-modify | Only production classification entry; harden domain-id normalize + eligibility mapping; leave orchestrator body untouched. |
| `_validate_domain_for_new_turn` / `resolve_available_domain` | Lifecycle/runtime availability only; does **not** call `eligible_sources_for_domain` | retain-and-reverify | Turn-start eligibility = available-domain resolver only (KTD6). |
| `claim_turn` | Accepts caller-supplied `route`; production callers: **none** | retain-non-authoritative | Test/scaffolding only (`test_conversations_service.py`, `test_postgres_conversations.py`). New route proof must use `classify_turn_route` / `start_or_replay_turn`. Optionally hard-guard later if needed. |
| `TurnStreamRequest` | `extra="forbid"`; fields `clientRequestId`, `message`, `domainId?`, `composerRefTokens?`; no `route` | retain-and-reverify | Prove unknown `route` → `422 validation_error` (AE5). |
| `_chat_turn_api_error` | Passthrough of `ChatTurnError.status_code` / `.code` / `.message` | modify | Replace with Evidence-parity allowlisted projector for inventory-listed pre-insert codes (KTD5). |
| `TurnOrchestrator` / retrieval / SSE emit / cancel / redaction | Shared file `chat_turns.py` | defer | P7-03 orchestration; P7-04 SSE/replay/cancel; P7-05 redaction. |
| Browser draft-preserve / domain prompt UX | Not present | defer | P9. |
| Empty-corpus / no-eligible-sources at submit | Not in `resolve_available_domain`; Evidence endpoint applies that predicate separately | defer | Exit criterion below; grounded refusal timing stays P7-03. |
| Brownfield DRIFT rows | No intent-gate-specific DRIFT row requires disposition update | retain | No `brownfield-refactor-register.md` edit in this slice. |

## Production call graph

```text
POST .../turns:stream
  → TurnStreamRequest (extra forbid)
  → stream_turn_events
      → start_or_replay_turn          # sole production classification entry
          → classify_turn_route
              → requires_domain       # only when domainId absent
          → _validate_effective_route
          → (domain_rag) _validate_domain_for_new_turn
              → resolve_available_domain
          → insert running turn
      → TurnOrchestrator.stream_turn  # deferred P7-03/P7-04
```

### Callers of classification helpers

| Symbol | Production callers | Test/scaffolding callers | Disposition |
| --- | --- | --- | --- |
| `requires_domain` | `classify_turn_route` only | none yet | retain |
| `classify_turn_route` | `start_or_replay_turn` only | none yet (U2 adds) | retain |
| `claim_turn` | **none** | `test_conversations_service.py`, `test_postgres_conversations.py` | non-authoritative; do not use for route proof |
| `start_or_replay_turn` | `stream_turn_events` (HTTP turn-start) | existing SSE/conversation suites | sole production authority |

Zero unexplained production `claim_turn` callers.

## Pre-insert failure codes from `start_or_replay_turn`

Codes raised as `ChatTurnError` before the first turn insert (or on replay mismatch before new insert). Conversation ownership denials raise `ConversationError` and use `_conversation_api_error` (already ownership-safe `not_found`); listed here for HTTP seam completeness.

| Internal / current code | When | Current HTTP escape (passthrough) | U3 projector target |
| --- | --- | --- | --- |
| `validation_error` | Bad `clientRequestId`, empty/overlong message, bad optional domain length/pattern, impossible route/domain pair | `422 validation_error` | retain `422 validation_error` + safe message |
| `domain_required` | No domain + domain-seeking message | `422 domain_required` | retain `422 domain_required` + Evidence-parity safe message |
| `domain_not_found` (via eligibility wrap) | Unknown selected domain | `404 domain_not_found` (**unapproved**) | map → `404 not_found` / "Domain not found." |
| `domain_state_conflict` | Stopped / transitioning / active domain op | `409 domain_state_conflict` | map → `409 domain_not_query_eligible` + Evidence safe message |
| `domain_runtime_unavailable` | Runtime health unhealthy | `502 domain_runtime_unavailable` (**unapproved**) | map → `409 domain_not_query_eligible` + Evidence safe message |
| `domain_runtime_dependency_unavailable` | Health probe exception | `503 domain_runtime_dependency_unavailable` (**unapproved**) | map → `503 dependency_unavailable` + Evidence safe message |
| `client_request_conflict` | Same `clientRequestId`, different fingerprint | `409 client_request_conflict` (**unapproved**) | map → `409 idempotency_conflict` |
| `conversation_turn_in_progress` | One-running-turn fence | `409 conversation_turn_in_progress` (**unapproved**) | map → `409 operation_conflict` |
| `composer_ref_unavailable` (via ComposerRefError) | Invalid/expired/incompatible composer refs at start | `409 composer_ref_unavailable` (**unapproved**) | map → approved union member (`validation_error` or `operation_conflict` per catalog parity) or pin if catalog lacks a dedicated chat code — **must not passthrough** |
| `synthesis_profile_not_ready` | Trusted synthesis profile missing | `409 synthesis_profile_not_ready` (**unapproved**) | map → `409 dependency_unavailable` or `503 dependency_unavailable` (approved); no new ErrorCode |
| `unauthenticated` | Mutation actor revalidation failure | `401 unauthenticated` | retain |
| Conversation `not_found` | Unknown/unauthorized `conv_…` | via `_conversation_api_error` | retain ownership-safe `404 not_found` (AE8) |

Pydantic unknown-field failures (`route` in body) never reach the service; FastAPI emits `422 validation_error` at the transport boundary.

### Empty-corpus eligibility exit criterion (Open Questions)

`resolve_available_domain` checks domain existence, `running` lifecycle, absence of active domain operations, and runtime health. It does **not** invoke `eligible_sources_for_domain` / `domain_no_eligible_sources`. Therefore turn-start eligibility excludes the no-eligible-sources predicate. Empty-corpus grounded refusal remains P7-03.

## Current observed turn-start public outcomes (pre-U3)

Characterization before projector hardening:

- No domain + domain-seeking → `422 domain_required` (code already approved; message OK).
- Unknown domain → risk of unapproved `domain_not_found` via passthrough.
- Stopped domain → risk of unapproved `domain_state_conflict` via passthrough (contract wants `domain_not_query_eligible`).
- Fingerprint conflict / running-turn conflict → unapproved internal codes via passthrough.

## SSE compatibility baseline (2026-07-27)

Command:

```text
cd app && .venv/Scripts/python.exe -m pytest tests/test_chat_sse_http_contract.py -q --tb=no
```

Result: `2 passed`

| Test | Role for P7-02 |
| --- | --- |
| `test_m06_live_and_cursor_replay_use_canonical_sse_envelopes` | Post-start SSE order/replay — compatibility only; not claimed by P7-02 |
| `test_c01_cancel_http_state_and_replay_terminal_are_consistent` | Cancel/terminal — deferred P7-04; compatibility only |

New SSE failures caused by turn-start edits block closure; otherwise cite this baseline as non-applicable for post-start orchestration claims.

## Explicit exclusions

- No client-supplied `route`, silent domain auto-selection, or ungrounded fallback.
- No ML/LLM intent classifier; pattern family retained (KTD1).
- No orchestration body, SSE sealing, attach/replay races, or redaction changes.
- No new public fields or ErrorCodes; no OpenAPI amendment unless an already-approved mapping forces regeneration (plan forbids new codes).
- No browser UX for `domain_required` (P9).

## Residual owners

- P7-03: bounded plan/retrieve/repair/synthesize; empty-corpus grounded refusal.
- P7-04: sealed SSE live/resume/replay, attach races, terminal persistence, cancel semantics breadth.
- P7-05: source/domain delete redaction.
- P8: system-wide privacy/audit breadth.
- P9: draft-preserve and domain-prompt UX after `domain_required`.
- P11: composer-ref consume/fingerprint correctness beyond turn-start fencing.
