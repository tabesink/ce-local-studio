# P10-01 Compose Config Evidence

Date: 2026-07-27  
Status: DONE (config/image/wiring half; smoke residual explicit)  
Plan: `docs/plans/2026-07-27-013-feat-p10-01-compose-production-like-config-plan.md`  
Branch: `feat/p10-01-compose-config`

## What landed

| Item | Result |
| --- | --- |
| Inventory | `docs/_scratch/p10-01-compose-config-inventory.md` |
| Backend image `COPY migrations ./migrations` | `app/Dockerfile` |
| Pinned `ce_stack` network `172.30.55.0/24` + frontend `172.30.55.10` | `app/compose.stack.yml` |
| Shared `CE_STACK_PUBLIC_ORIGIN` → API `CE_PUBLIC_ORIGIN` + BFF `CONTEXT_ENGINE_PUBLIC_ORIGIN` | compose + `.env.stack.example` |
| Ingress-wired HTTP primary example (`testing=true` + full CE_*; not P12 evidence) | `.env.stack.example` |
| Secondary empty-CE_* bypass documented | `.env.stack.example` |
| Verify compose placeholders include ingress dummies | `scripts/verify.sh` |
| Contract tests | `app/tests/test_compose_stack_config.py` |
| E2E operator note for public origin / port coupling | `app/client/tests/e2e/README.md` |

## Commands and results

```text
cd app && uv run --frozen --python 3.12 --extra test pytest tests/test_compose_stack_config.py -q
# ........ [100%] PASS (8 tests)

cd app && docker compose -f compose.stack.yml config --quiet
# (with verify-style placeholders) PASS

cd app && docker build --target runtime -t context-engine-p10-01-verify .
# PASS — image contains /app/migrations/{env.py,versions,...}

cd app/client && npm test
# bff-proxy: fails closed when production public origin is absent — ok
# node tests 113 pass; vitest 32 pass
```

## Residuals

| Residual | Owner |
| --- | --- |
| BFF/API/SSE core-path smoke + admin bootstrap job | P10-02 |
| Object-store readiness composition (DRIFT-15) | P10-02 |
| Worker SIGTERM stop-claim / drain runbook (DRIFT-31) | P10-03 |
| TLS / `testing=false` HTTPS / direct public API denial | P12 |
| Frontend `/login` health ≠ trust-path proof | P10-02 |
| Optional `compose.stack.live.yml` LightRAG overlay | later fidelity |

## Tracker updates

- `docs/master-build-plan.md` P10-01 → DONE with residuals above.
- DRIFT-08: migrations/config/image wiring advanced; API/worker/web **smoke remains open** for P10-02 (not full DONE).
- DRIFT-05: Compose dual-origin / CE_* example wiring advanced; local BFF half remains P9-05 DONE; deployed-ingress / direct-API denial remain P12. Not marked DONE.
