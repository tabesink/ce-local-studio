# P10-03 Worker Lifecycle Inventory

Date: 2026-07-27  
Status: complete for U1 inventory only.  
Plan: `docs/plans/2026-07-27-015-feat-p10-03-worker-lifecycle-runbook-plan.md`  
Authority: `docs/master-build-plan.md` P10-03; `docs/architecture/deployment-topology.md` Boot/health/shutdown; DRIFT-31 / DRIFT-08 / DRIFT-15; P10-02 evidence residuals.

## Disposition legend

| Value | Meaning |
| --- | --- |
| `retain` | Already correct; keep |
| `modify` | Change in this slice |
| `add` | New wiring/test/script/doc in this slice |
| `defer-P12` | TLS / stream-drain / HA / production store |
| `defer-follow-up` | Mid-turn DB heartbeat; queue-class split deploys |

## Worker entrypoint (`app/context_engine/worker.py`)

| Unit | Fact | Disposition |
| --- | --- | --- |
| `main()` | Validates encryption; creates engine; enters `run_loop` immediately | `modify` — call worker readiness before loop |
| `run_loop(should_continue=...)` | Hook exists; default `lambda: True` | `retain` hook; `modify` wire SIGTERM/SIGINT |
| Signal handlers | **absent** (DRIFT-31) | `add` |
| Idle sleep | `time.sleep(idle_seconds)` blocks shutdown | `modify` — interruptible Event.wait |
| Heartbeat | Touched every loop iteration under `CE_DOMAIN_RUNTIME_ROOT` | `modify` — clear at start; touch only after ready |
| Queue classes | Monolithic prep→index→turn→delete via `build_workers` | `retain` — topology “queue class configured” satisfied by construction for Compose monolith |

## Readiness

| Check | API `/health/ready` | Worker internal | Disposition |
| --- | --- | --- | --- |
| DB `SELECT 1` | yes | **absent** | `add` via shared helper |
| Exact Alembic head | yes | **absent** | `add` |
| Enabled administrator | yes | must **omit** | `retain` omit on worker (KTD1) |
| Object-store probe | yes (`probe_object_store`) | **absent** | `add` reuse |
| Encryption key | N/A (API settings) | `validate_config_encryption_key` | `retain` |

## Inline vs leased seam (`chat_turns.stream_turn_events`)

| Fact | Disposition |
| --- | --- |
| `if settings.testing: run_turn_workers_until_idle(...)` | `modify` — gate on effective inline helper |
| Testing tail idle 0.5s assumes in-process completion | `modify` — use normal tail idle when inline off |
| `CONTEXT_ENGINE_TESTING=true` required for Compose HTTP cookies | `retain` for matrix |
| Public DTO/SSE lease_owner | none (private) | `retain` — smoke uses private Postgres claim proof |

## Compose (`app/compose.stack.yml`)

| Unit | Fact | Disposition |
| --- | --- | --- |
| `worker` depends_on | postgres + migrate only | `modify` — add bootstrap completed |
| `worker` healthcheck | heartbeat mtime &lt;30s | `retain` semantics; document ≠ claim-ready until post-ready |
| `stop_grace_period` | **absent** | `add` 60s for matrix |
| `CE_TURN_WORKER_ID` on worker | unset (defaults) | `modify` — set distinct id for smoke assert |
| Default `CE_TURN_LEASE_SECONDS` | 180 | `retain` — shorten only in smoke-only env |
| Inline env | absent | `add` document `CE_INLINE_TURN_WORKERS` in `.env.stack.example` |

## Reclaim proofs

| Suite | Fact | Disposition |
| --- | --- | --- |
| `test_postgres_turn_leases.py` | expired lease reclaim | `retain` cite |
| Domain / index claim reclaim | present | `retain` cite |
| Compose kill+reclaim smoke | **absent** | `add` (U5) |

## Smoke / runbook

| Item | Fact | Disposition |
| --- | --- | --- |
| `stack_smoke_core.py` | BFF CSRF→SSE; requires testing; inline path | `retain` for R19 regression |
| Worker-path smoke | **absent** | `add` `stack_smoke_worker.py` |
| Operator runbook | **absent** | `add` `docs/operations/compose-stack-runbook.md` |

## Residuals (non-claims)

| Concern | Owner |
| --- | --- |
| API/ingress stream-drain | `defer-P12` (P12-05) |
| TLS / `testing=false` HTTPS | `defer-P12` |
| Production / S3 object-store readiness | `defer-P12` / not Compose FS matrix |
| HA / production incident runbooks | `defer-P12` (P12-04/08) |
| Browser CSRF product fix | residual (P9-05) |
| Mid-turn turn-worker DB heartbeat | `defer-follow-up` |
| Separate queue-class deployments | `defer-follow-up` |
| Provider-failure terminal ≠ completed synthesis | named residual if green bar uses allowed failure |
