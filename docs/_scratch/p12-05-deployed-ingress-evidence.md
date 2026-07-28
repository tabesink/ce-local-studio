# P12-05 Deployed Ingress SSE / Stream Drain Evidence

Date: 2026-07-28

Owner: P12-05

Status: PARTIAL — unit/config altitude landed; live TLS Compose AE1–AE4 remain operator-run for DONE

Plan: `docs/plans/2026-07-28-013-feat-p12-05-deployed-ingress-sse-drain-plan.md`

Inventory: `docs/_scratch/p12-05-deployed-ingress-inventory.md`

## Prerequisites cited

| Prerequisite | Evidence |
| --- | --- |
| P5-04 | `docs/_scratch/p5-04-lightrag-real-runtime-evidence.md` |
| P7-04 | `docs/_scratch/p7-04-sse-pipeline-evidence.md` |
| P7-06 | `docs/_scratch/p7-06-synthesis-isolation-heartbeat-evidence.md` |
| P9-05 | `docs/_scratch/p9-05-ci-validators-evidence.md` |
| P10-01..03 | `docs/_scratch/p10-01-compose-config-evidence.md`, `p10-02-stack-smoke-evidence.md`, `p10-03-worker-lifecycle-evidence.md` |
| P12-02 | `docs/_scratch/p12-02-suite-contract-convergence-evidence.md` |

## What landed (this revision)

| Deliverable | Path / proof |
| --- | --- |
| Inventory | `docs/_scratch/p12-05-deployed-ingress-inventory.md` |
| TLS overlay + Caddy unbuffered proxy | `app/compose.stack.tls.yml`, `app/stack-tls/Caddyfile` |
| Cert generator (gitignored output) | `app/scripts/generate_stack_tls_certs.py` → `app/.stack-tls/` |
| Trust proof script (AE4) | `app/scripts/stack_ingress_trust_proof.py` |
| Chunked SSE proof script (AE1/AE2) | `app/scripts/stack_ingress_sse_proof.py` |
| Drain proof script (AE3) | `app/scripts/stack_ingress_drain_proof.py` |
| Inter-arrival helper + constant | `context_engine/dev/ingress_sse_proof.py` (`SSE_DELTA_INTER_ARRIVAL_EPSILON_MS=25`) |
| API stop-new-turns | `app.state.accepting_new_turns`; `503 capacity_unavailable` on `turns:stream` |
| Unit/config tests | `test_stack_ingress_sse_helpers.py`, `test_api_shutdown_drain.py`, TLS compose contract tests |
| Runbook / env example | `docs/operations/compose-stack-runbook.md`, `app/.env.stack.example` |

## Commands run (unit altitude)

```bash
cd app
python -m pytest tests/test_stack_ingress_sse_helpers.py tests/test_api_shutdown_drain.py \
  tests/test_compose_stack_config.py::test_tls_overlay_exists_and_documents_unbuffered_ingress \
  tests/test_compose_stack_config.py::test_compose_tls_overlay_config_resolves_https_and_ingress -q
# 9 passed
python scripts/generate_stack_tls_certs.py
```

## AE matrix

| AE | Status | Notes |
| --- | --- | --- |
| AE1 ≥2 timed deltas | NOT YET (live) | Script ready; needs TLS+live stack + `OPENAI_API_KEY`/`CE_OPENAI_API_KEY` (env only; never logged) |
| AE2 disconnect/resume | NOT YET (live) | Script ready |
| AE3 drain | PARTIAL | Unit: `503 capacity_unavailable` + lifespan flag; Compose stop_claim script ready, not executed this revision |
| AE4 trust/TLS denial | NOT YET (live) | Script + overlay ready; `docker compose … config` resolves HTTPS/ingress |

## Privacy checklist

- No API keys, CSRF secrets, or passwords in this evidence file
- Cert private key stays under gitignored `app/.stack-tls/`
- Scripts report `credentials present=true/false` only

## Residuals for DONE / peers

| Residual | Owner |
| --- | --- |
| Live TLS AE1–AE4 operator digests | P12-05 (before tracker DONE) |
| Deployed PDF byte-range | P12-07 |
| Ingress adversarial deletion | P12-07 |
| Playwright / browser CSRF / two-user cache | P12-07 |
| Hard provider-I/O abort | P12-08 |
| HA / production digests | P12-08 |

## Tracker

`docs/master-build-plan.md` P12-05 remains **NOT_STARTED → in-progress at unit altitude** until live AE1–AE4 commands are captured. Do not claim DONE from this evidence alone.
