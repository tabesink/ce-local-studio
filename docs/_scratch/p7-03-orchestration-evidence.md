# P7-03 Bounded Plan Retrieve Repair Synthesize Orchestration Evidence

Date: 2026-07-27

Owner: P7-03

Status: DONE

Requirements and cases: FR-06; M-03; M-07; R1–R11; AE1–AE8; KTD1–KTD8;
DRIFT-22 (synthesis half).

## Implemented boundary

- Inventory pinned retain/modify/defer in
  `docs/_scratch/p7-03-orchestration-inventory.md` before behavior edits.
- Deterministic synthesis stand-in is no longer the production default.
  `adapters/synthesis.py` provides a typed synthesis port, OpenAI concrete
  adapter with injectable transport, fail-closed Bedrock/Ollama registry
  entries, and privacy-safe error surfaces.
- `Settings` adds positive `synthesis_timeout_seconds` /
  `synthesis_max_output_tokens` (env `CE_SYNTHESIS_*`).
- Optional extra `synthesis = ["openai>=1.40.0"]` mirrors the parsers pattern;
  CI proves behavior with injected transports and no network.
- `TurnOrchestrator` uses the registry facade unless tests inject
  `app.state.synthesis_stream_adapter`. Domain path: private one-shot plan →
  `retrieval.started` `1/1` → `P6RetrievalPort` once → empty mapped Evidence
  completes `no_grounded_context`; mapped Evidence persists before synthesis;
  Evidence events precede answer deltas; budgets `1/1/0`.
- `evidence_only` only when no `answer.delta` was persisted; after any answer
  delta, provider failure/empty completes safe `turn.failed` /
  `provider_failure` (KTD5).
- Direct path keeps zero retrieval events and budget `0/0/0`.
- Compatible `_persist_event` / `_complete_turn` / `_fail_turn` emission is
  retained; sealed SSE attach/replay/cancel and terminal DTO sealing remain
  P7-04. Redaction remains P7-05.

## Verification

### Focused orchestration + synthesis + compatibility

```text
cd app
.\.venv\Scripts\python.exe -m pytest tests\test_chat_orchestration.py tests\test_synthesis_adapters.py tests\test_chat_sse_http_contract.py tests\test_chat_turn_route_http_contract.py -q
```

Result: PASS, 30 tests (10 orchestration + 9 synthesis adapter + 2 SSE + 9
turn-route HTTP) after review follow-up.

Coverage includes M-03 AE1 grounded one-shot budget, AE2 empty-corpus
`no_grounded_context`, AE3 evidence_only before answer, AE4 post-answer
`turn.failed`, AE5/M-07 direct `0/0/0`, AE6 privacy sentinels, AE7 unsupported
provider fail-closed (direct + domain evidence_only), AE8 single retrieval /
`repairAttemptCount:0`, plus adapter timeout/auth/malformed/empty/privacy
fixtures and SSE compatibility. Answer-token substring denylisting was removed
in review follow-up so legitimate grounded URLs/words are not rejected.

### Static quality

Changed-file Ruff over `adapters/synthesis.py`, `config.py`, `chat_turns.py`,
and the new focused tests: PASS.

### Contract generation

OpenAPI / public schema / generated TypeScript: intentionally untouched (no new
ErrorCode, request field, or public DTO). On this Windows working tree,
`test_openapi_generator_check_accepts_committed_artifact` can fail with
“generated OpenAPI is stale” solely because committed `openapi.json` bytes are
CRLF while the generator emits LF; `json.loads` equality is True. Same
P7-02 residual — not a P7-03 contract change.

### Privacy scan

Focused orchestration/adapter assertions prove:

- provider failure surfaces use only the safe message
  (`The answer could not be completed.`)
- timeout/auth/malformed/unavailable adapter errors omit credentials, URLs,
  job IDs, and prompt-like exception text
- unsupported provider kinds never emit deterministic stand-in success copy
- private `source-` / `block-` IDs and injected provider sentinels are absent
  from failed-turn public projections in the AE6 orchestration proof
- empty-corpus path never synthesizes and never rewrites to `direct_llm`

## Residuals

- P7-04: sealed SSE live/resume/replay, attach races, cancel semantics,
  grounded-refusal/evidence-only terminal projection sealing.
- P7-05: source/domain delete redaction.
- P8: system-wide privacy/audit breadth across all sinks.
- P9: chat UI.
- P11: deeper composer-ref assembly correctness beyond current turn fencing.
- Multi-attempt query-rewrite repair remains deferred until contracted.
- Bedrock/Ollama concrete synthesis adapters remain fail-closed registry
  entries until separately proven.
- Live OpenAI SDK path requires the optional `synthesis` extra; CI does not
  require network.

This slice does not claim the closed Phase 1 chat capability manifest complete.
