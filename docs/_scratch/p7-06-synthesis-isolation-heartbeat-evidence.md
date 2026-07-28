# P7-06 Synthesis Isolation and Turn Lease Heartbeat Evidence

Date: 2026-07-28

Owner: P7-06

Plan: `docs/plans/2026-07-28-009-feat-p7-06-synthesis-isolation-heartbeat-plan.md`

Inventory: `docs/_scratch/p7-06-synthesis-isolation-heartbeat-inventory.md`

## Boundary proven

1. **Delimiter isolation (U2):** `adapters/synthesis.py` wraps full untrusted Evidence lines (label+excerpt) and assembly lines (label+body) with per-call random delimiters; collision regenerates then fails closed pre-provider; transport receives prebuilt messages so injected transports cannot bypass isolation.
2. **Turn lease heartbeat (U3):** `ConversationTurnWorker.run_once` wraps `stream_turn` with a daemon-thread heartbeat (separate session), generation-gated compare-and-extend, and liveness miss detection (`_TURN_HEARTBEAT_LIVENESS_MISSES`).
3. **No public contract changes:** OpenAPI/SSE untouched (KTD3).
4. **No prompt persistence:** Isolation is transport-only; persisted Evidence excerpts unchanged.

## Commands

```bash
cd app
.venv/bin/python -m pytest \
  tests/test_synthesis_prompt_isolation.py \
  tests/test_turn_lease_heartbeat_unit.py \
  tests/test_synthesis_adapters.py \
  tests/test_chat_orchestration.py \
  tests/test_turn_execution_leases.py -q
# Result: 37 passed

.venv/bin/ruff check \
  context_engine/adapters/synthesis.py \
  context_engine/services/chat_turns.py \
  tests/test_synthesis_prompt_isolation.py \
  tests/test_turn_lease_heartbeat_unit.py \
  tests/test_postgres_turn_lease_heartbeat.py
# Result: All checks passed

# Opt-in PostgreSQL (AE3/AE4) — skipped in this environment (no
# CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS / admin URL):
.venv/bin/python -m pytest tests/test_postgres_turn_lease_heartbeat.py -q
# Result: 2 skipped
```

## Privacy non-claims

- Assembled prompts / delimiter tokens are not written to turn columns or SSE by design.
- Heartbeat failure logging uses allowlisted `safe_log` fields only (`conversation_turn_id`, `outcome`).
- AE1/AE2 covered by `test_synthesis_prompt_isolation.py`.

## Residuals

| Residual | Owner |
| --- | --- |
| Opt-in PostgreSQL AE3/AE4 barrier green on disposable PG 16 | Operator re-run with `CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1` |
| Hard stream-drain / mid-call abort of blocking provider I/O | P12-05 |
| Prior-user-question delimiter wrapping | Deferred Open Question |
| `turn_lease_seconds > retrieval + synthesis` validation tighten | KTD5 deferred |
| Dedup `_lease_heartbeat_seconds` across services | Follow-up |

## Tracker

Mark P7-06 DONE; P7 phase DONE (P7-01..P7-06 complete). P10-03 mid-turn heartbeat residual closed by this slice.
