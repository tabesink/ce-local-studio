# P12-05 Deployed Ingress SSE / Stream Drain Evidence

Date: 2026-07-28

Owner: P12-05

Status: PARTIAL — drain-hold + proof-script honesty landed at unit altitude; live TLS AE1–AE4 blocked this session on Docker Desktop image unpack (`lchown … read-only file system`)

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
| Drain-hold seam (`SIGUSR1` + `enter_drain_hold`) | `app/context_engine/app.py` — flag false while listen may still serve; lifespan teardown backstop |
| Drain unit tests | `app/tests/test_api_shutdown_drain.py` (incl. drain-hold still-serving 503) |
| Trust proof honesty (AE4) | `app/scripts/stack_ingress_trust_proof.py` — require `ca=yes`; missing+mismatch CSRF; compose unpublished `api`/`frontend` ports |
| SSE proof honesty (AE1/AE2) | `app/scripts/stack_ingress_sse_proof.py` — env-file merge before credential gate; contiguous AE1; `replay:true` AE2 |
| Drain proof honesty (AE3) | `app/scripts/stack_ingress_drain_proof.py` — three-file compose; SIGUSR1 drain-hold; live 503; resume/tail; fail closed without `stop_claim` |
| Runbook | `docs/operations/compose-stack-runbook.md` — three-file boot primary; synthesis/`--domain-id` preflight; SIGUSR1 drain |
| Plan resume | `docs/plans/2026-07-28-013-feat-p12-05-deployed-ingress-sse-drain-plan.md` — U6→U5 remaining HOW |

## Commands run (unit altitude)

```bash
cd app
python -m pytest tests/test_api_shutdown_drain.py tests/test_stack_ingress_sse_helpers.py -q
# 8 passed
python scripts/generate_stack_tls_certs.py
# OK: wrote cert.pem and key.pem under app/.stack-tls
```

## Live attempt (blocked)

```text
# Docker Desktop started; three-file up --build pulled Caddy and built live image extras.
# Parallel api/worker export raced: image "context-engine-live:local": already exists
# Serial api rebuild then failed unpack:
#   failed to Lchown ".../xlsxwriter/chart.py" ... read-only file system
# Operator action: repair Docker Desktop disk/WSL, then re-run three-file boot + AE1–AE4 scripts.
```

## AE matrix

| AE | Status | Notes |
| --- | --- | --- |
| AE1 ≥2 timed deltas | NOT YET (live) | Script hardened; needs healthy three-file stack + sealed synthesis + `--domain-id` |
| AE2 disconnect/resume/replay | NOT YET (live) | Script asserts `replay:true` |
| AE3 drain | PARTIAL | Unit drain-hold 503 green; live SIGUSR1 digest blocked on Docker |
| AE4 trust/TLS denial | NOT YET (live) | Script requires `ca=yes` + unpublished compose evidence |

## Privacy checklist

- No API keys, CSRF secrets, or passwords in this evidence file
- Cert private key stays under gitignored `app/.stack-tls/`
- Scripts report `credentials present=true/false` and `ca=yes` only
- Do not paste unredacted `docker compose config` env into digests

## Residuals for DONE / peers

| Residual | Owner |
| --- | --- |
| Live TLS AE1–AE4 operator digests (Docker Desktop repair + three-file boot) | P12-05 (before tracker DONE) |
| Deployed PDF byte-range | P12-07 |
| Ingress adversarial deletion | P12-07 |
| Playwright / browser CSRF / two-user cache | P12-07 |
| Hard provider-I/O abort | P12-08 |
| HA / production digests | P12-08 |

## Tracker

`docs/master-build-plan.md` P12-05 remains **IN_PROGRESS**. Do not claim DONE until live AE1–AE4 digests are captured.
