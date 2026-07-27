# P7-02 Server Intent Gate and Turn-Start Route Evidence

Date: 2026-07-27

Owner: P7-02

Status: DONE

Requirements and cases: FR-06; M-02; M-07; R1–R10; AE1–AE8; KTD1–KTD6.

## Implemented boundary

- Retained the closed Phase 1 pattern classifier in `chat_intent.py` and proved
  the AE6 fixture matrix (`requires_domain`).
- `classify_turn_route` remains the sole production route decision; explicit
  `domainId` always yields `domain_rag`; no-domain domain-seeking raises
  `domain_required`; narrow general yields `direct_llm`.
- Optional body `domainId` normalizes against `DOMAIN_ID_PATTERN` before
  classification success.
- `_validate_effective_route` fails closed for impossible route/domain pairs.
- `claim_turn` has zero production callers and remains non-authoritative test
  scaffolding.
- Turn-start eligibility reuses `resolve_available_domain` (lifecycle/runtime
  only). Empty-corpus / no-eligible-sources remains deferred to P7-03.
- `_chat_turn_api_error` is an Evidence-parity allowlisted projector: unknown
  domain → `404 not_found`; stopped/runtime-not-ready →
  `409 domain_not_query_eligible`; fingerprint mismatch →
  `409 idempotency_conflict`; one-running-turn → `409 operation_conflict`;
  unlisted codes fail closed to `503 dependency_unavailable`. No new ErrorCode.
- Pre-stream denials are private no-store JSON with request ID and create no
  turn row. Success persistence of `direct_llm` / `domain_rag` is proved at
  `start_or_replay_turn` without claiming orchestration/SSE completion.

## Verification

### Focused intent / route / HTTP gate

```text
cd app
.\.venv\Scripts\python.exe -m pytest tests\test_chat_intent.py tests\test_chat_turn_route.py tests\test_chat_turn_route_http_contract.py tests\test_chat_sse_http_contract.py tests\test_generated_contract_gate.py tests\test_phase_one_route_scope.py -q
```

Result: PASS, 46 tests.

Coverage includes M-07 AE6 pattern matrix, classify table, malformed domain id,
impossible route/domain pairs, zero production `claim_turn` callers, HTTP
`domain_required` / stopped-domain / unknown-domain / cross-owner / unknown
`route` field / fingerprint `idempotency_conflict`, service-level direct and
domain_rag persistence, SSE compatibility baseline (2 tests), generated-contract
snapshots, and phase-one route scope.

### Static quality

Changed-file Ruff over `chat_intent.py`, `chat_turns.py`, `routes.py`, and the
new focused tests: PASS.

OpenAPI / public schema / generated TypeScript: untouched by this slice (no new
ErrorCode or request field). Regenerated OpenAPI check accepts the committed
artifact (ensure LF working-tree bytes on Windows before `--check`).

### Privacy scan

Focused HTTP denial assertions prove:

- `Cache-Control: private, no-store, no-transform`
- request ID present and mirrored in the error envelope
- approved ErrorCode only (`domain_required`, `domain_not_query_eligible`,
  `not_found`, `validation_error`, `idempotency_conflict`)
- Evidence-parity safe messages for domain eligibility failures
- no turn-row creation on gate failure
- cross-owner conversation denial uses ownership-safe
  `Conversation not found.` without turn disclosure

No private conversation/turn UUIDs, raw provider/retrieval payloads, or
unapproved ErrorCodes appear in the focused denial paths.

## Residuals

- P7-03: bounded plan/retrieve/repair/synthesize; empty-corpus grounded refusal.
- P7-04: sealed SSE live/resume/replay, attach/replay races, terminal persistence;
  extend `_chat_turn_api_error` when new pre-stream codes are introduced.
- P7-05: source/domain delete redaction.
- P8: system-wide privacy/audit breadth across all sinks.
- P9: browser draft-preserve and domain-prompt UX after `domain_required`.
- P11: composer-ref consume/fingerprint correctness beyond turn-start fencing.
- Review residuals (non-blocking): HTTP proof for `operation_conflict` and
  runtime-unavailable projector branches; M-02 barrier/latch race beyond static
  stopped-domain denial; transport-level malformed `domainId` (service-side
  pattern proof already exists).

This slice does not claim the closed Phase 1 chat capability manifest complete.
