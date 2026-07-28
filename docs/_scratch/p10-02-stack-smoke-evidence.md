# P10-02 Stack Smoke Evidence

Date: 2026-07-27  
Status: DONE (with explicit residuals)  
Plan: `docs/plans/2026-07-27-014-feat-p10-02-stack-smoke-bootstrap-plan.md`  
Branch: `feat/p10-02-stack-smoke-bootstrap`  
Inventory: `docs/_scratch/p10-02-stack-smoke-inventory.md`

## What landed

| Item | Result |
| --- | --- |
| Inventory | `docs/_scratch/p10-02-stack-smoke-inventory.md` |
| Compose `bootstrap` one-shot after migrate, before api | `app/compose.stack.yml` |
| `CE_ADMIN_*` only on bootstrap (removed from api/worker) | compose + contract test |
| Object-store readiness via `object_store_from_root` put+delete | `app/context_engine/services/readiness.py` |
| BFF core-path smoke script | `app/scripts/stack_smoke_core.py` |
| Env example + E2E README pointers | `.env.stack.example`, `app/client/tests/e2e/README.md` |
| Contract tests | `app/tests/test_compose_stack_config.py`, `app/tests/test_health_contract.py` |

## Commands and results

```text
cd app && uv run --frozen --python 3.12 --extra test pytest tests/test_compose_stack_config.py tests/test_health_contract.py -q
# ....................... [100%] PASS

cd app && docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d
# migrate: Running upgrade … -> e9f2a1b83c70, turn execution leases (exit 0)
# bootstrap: Administrator bootstrap complete. (exit 0)
# api: healthy (/health/ready)
# frontend: healthy (/login) — not trust proof

cd app && python scripts/stack_smoke_core.py --env-file .env.stack.local
# CONTEXT_ENGINE_TESTING=true; ingress-wired CE_*; testing-mode inline workers
# OK: BFF sealed turn failed closed with allowed code=synthesis_profile_not_ready
#     (3 events: turn.accepted, route.selected, turn.failed; not completed-synthesis proof)
# OK: published API host call fail-closed HTTP 403
# OK: AE6 trust negatives passed (Origin localhost mismatch → 403)
# exit 0

# R6 missing-credential fail-closed:
docker compose --env-file .env.stack.local -f compose.stack.yml run --rm \
  -e CE_ADMIN_USERNAME= -e CE_ADMIN_PASSWORD= bootstrap
# RuntimeError: ADMIN_USERNAME and ADMIN_PASSWORD are required… (exit 1)

curl -s http://127.0.0.1:8000/health/ready
# {"status":"ready"}
curl -s http://127.0.0.1:8000/health/live
# {"status":"live"}
```

## Residuals (honest non-claims)

| Residual | Owner |
| --- | --- |
| Worker-path smoke / SIGTERM stop-claim drain (DRIFT-31) | P10-03 |
| DRIFT-15 worker readiness half | P10-03 |
| Production / S3 object-store readiness | not Compose filesystem matrix |
| TLS / `testing=false` HTTPS / deployed direct-API denial | P12 |
| Browser CSRF product fix (P9-05) | residual — scripted smoke only |
| Provider/profile-failure terminal ≠ completed synthesis / worker-leased turn | named residual |

## Tracker updates

- `docs/master-build-plan.md` P10-02 → DONE with residuals above.
- DRIFT-08: half-closed for migrate/bootstrap + BFF/API/SSE scripted smoke; **worker-path smoke remains open** (P10-03).
- DRIFT-15: half-closed for Compose/filesystem API readiness; **worker readiness + production store remain open**.
