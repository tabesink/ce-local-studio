# Compose Stack Operator Runbook (Development Matrix)

**Altitude:** local Compose / development matrix only.  
**Not** TLS, `testing=false` HTTPS, production HA, production object-store, or P12-05 stream-drain evidence.  
Production incident/HA recovery: P12-04 / P12-08.

## Boot order

1. `postgres` healthy  
2. `migrate` (`alembic upgrade head`) completed  
3. `bootstrap` (insert-only admin; `CE_ADMIN_*` only here) completed  
4. `api` `/health/ready` → `{status:ready}`  
5. `worker` internal readiness (DB + exact Alembic head + filesystem object-store) then claim loop; Compose `healthy` = heartbeat after ready  
6. `frontend` `/login` healthy (not BFF trust proof)

```bash
cd app
docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d
```

Recreate `.env.stack.local` from `.env.stack.example` for the ingress-wired HTTP profile (`CONTEXT_ENGINE_TESTING=true` + full `CE_*`).

## Readiness probes

| Probe | Meaning |
| --- | --- |
| `GET /health/live` | Process up only |
| `GET /health/ready` | DB + schema head + enabled admin + filesystem store |
| Worker Compose `healthy` | Heartbeat file fresh **after** internal worker readiness |
| Worker claim-ready | In-process gate before first claim (not the heartbeat alone) |

## Smokes

**Core path (P10-02; default may inline turns under testing):**

```bash
python app/scripts/stack_smoke_core.py --env-file app/.env.stack.local
```

**Worker path (P10-03; Compose-leased turns):**

1. Set `CE_INLINE_TURN_WORKERS=false` in `.env.stack.local`  
2. Recreate `api` (and keep `worker` up)  
3. Run:

```bash
python app/scripts/stack_smoke_worker.py --env-file app/.env.stack.local
```

Green bar: BFF SSE allowed terminal **and** `execution_generation >= 1` **and** worker logs mention the smoke `clientRequestId`.  
Lease owner is cleared on terminal by product design — do not require post-terminal `lease_owner`.

Restore `CE_INLINE_TURN_WORKERS` unset/true when returning to default inline testing helpers.

## Graceful stop / drain

```bash
cd app
docker compose --env-file .env.stack.local -f compose.stack.yml stop -t 60 worker
```

Expect log event `stack_worker.stop_claim`, then process exit within `stop_grace_period` (60s).  
Busy drain finishes the current `run_once_pass` only; hung work may be SIGKILLed by Docker and recovered via lease expiry (do not force-complete).

## Kill + single-worker turn-lease reclaim

1. With a claimable/running leased turn (or after citing PG reclaim suites), `docker kill` the worker container.  
2. Wait at least `CE_TURN_LEASE_SECONDS` (shorten only in smoke-only env).  
3. `docker compose ... start worker` (or `up -d worker`).  
4. Confirm a new worker claims/reclaims work; stale generation completions are no-ops.

Algorithm authority: PostgreSQL suites `test_postgres_turn_leases.py`, domain/index reclaim tests.  
This drill is single-worker Compose-matrix reclaim — not P12-04 HA/incident recovery.

## Residuals (do not claim from this runbook)

| Concern | Owner |
| --- | --- |
| TLS / `testing=false` HTTPS / deployed API denial | P12 |
| Deployed ingress stream-drain | P12-05 |
| Production / S3 object-store readiness | P12 |
| Production HA / backup / incident drills | P12-04 / P12-08 |
| Browser CSRF product fix | P9-05 residual |
| Completed synthesis without live provider | needs credentials / later proof |
