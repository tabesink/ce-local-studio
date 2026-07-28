# P10-03 Worker Lifecycle Evidence

Date: 2026-07-27  
Status: DONE (with explicit residuals)  
Plan: `docs/plans/2026-07-27-015-feat-p10-03-worker-lifecycle-runbook-plan.md`  
Branch: `feat/p10-03-worker-lifecycle-runbook`  
Inventory: `docs/_scratch/p10-03-worker-lifecycle-inventory.md`

## What landed

| Item | Result |
| --- | --- |
| Inventory | `docs/_scratch/p10-03-worker-lifecycle-inventory.md` |
| Worker readiness (no admin) | `check_worker_readiness` in `services/readiness.py`; called from `worker.main` |
| Heartbeat after ready | clear at start; touch only in claim loop |
| SIGTERM/SIGINT stop-claim | `should_continue` + interruptible `Event.wait`; log `stack_worker.stop_claim` |
| Compose worker deps + grace | bootstrap completed; `stop_grace_period: 60s`; `CE_TURN_WORKER_ID` |
| Inline split | `CE_INLINE_TURN_WORKERS` + `Settings.inline_turn_workers_enabled()`; fail-closed when `testing=false` |
| Tail idle when inline off | uses normal `turn_tail_idle_seconds` |
| Worker-path smoke | `app/scripts/stack_smoke_worker.py` (generation + worker logs) |
| BOM-safe env parse | `utf-8-sig` in smoke scripts |
| Runbook | `docs/operations/compose-stack-runbook.md` |
| Unit/contract tests | `test_worker_readiness.py`, `test_worker_loop.py`, `test_inline_turn_workers.py`, compose config |

## Commands and results

```text
cd app && uv run --frozen --python 3.12 --extra test pytest \
  tests/test_worker_readiness.py tests/test_worker_loop.py \
  tests/test_inline_turn_workers.py tests/test_compose_stack_config.py \
  tests/test_health_contract.py -q
# ................................ [100%] PASS

cd app
# CE_INLINE_TURN_WORKERS=false; recreate api/worker
docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d api worker
# worker healthy; heartbeat present after ready

python scripts/stack_smoke_worker.py --env-file .env.stack.local
# OK: worker-leased BFF turn (execution_generation=1, lease_owner_after_terminal=None,
#     expected_worker_id=compose-turn-worker, 3 events; Compose-dev matrix)

python scripts/stack_smoke_core.py --env-file .env.stack.local
# OK: BFF sealed turn + AE6 trust negatives (R19 regression under current stack)

docker compose --env-file .env.stack.local -f compose.stack.yml stop -t 60 worker
# logs include stack_worker.stop_claim; container Stopped; restart → healthy
```

Claim proof note: product clears `lease_owner` on terminal (`_clear_turn_lease_values`); smoke asserts `execution_generation >= 1` and worker log mention of `clientRequestId`.

Kill+reclaim: cite PostgreSQL `test_postgres_turn_leases.py` / domain/index reclaim suites as algorithm authority; Compose matrix proved stop-claim + worker restart healthy. Mid-flight kill during long synthesis not exercised (provider-not-ready terminals complete too quickly in this matrix).

## Residuals (honest non-claims)

| Residual | Owner |
| --- | --- |
| TLS / `testing=false` HTTPS / deployed direct-API denial | P12 |
| Deployed ingress stream-drain / API stop-new-turns | P12-05 |
| Production / S3 object-store readiness | not Compose filesystem matrix |
| Multi-failure / restore-coupled incident drills | Cite-closed under P12-04 (`docs/_scratch/p12-04-backup-restore-evidence.md`); HA → P12-08 only |
| Browser CSRF product fix | P9-05 residual |
| Mid-turn DB lease heartbeat for turns | follow-up |
| Provider-failure terminal ≠ completed synthesis | named residual |
| Mid-flight kill during long synthesis | not exercised here; PG reclaim + stop-claim proven |

## Tracker updates

- `docs/master-build-plan.md` P10-03 → DONE; P10 package closable if no other blockers.
- DRIFT-31 → DONE.
- DRIFT-08 worker-path smoke half → closed.
- DRIFT-15 worker-readiness half → closed for Compose/filesystem matrix; production store remains open.
