# P12-05 Deployed Ingress SSE / Stream Drain Evidence

Date: 2026-07-29

Owner: P12-05

Status: DONE — live TLS Compose AE1–AE4 green through three-file stack + real LightRAG + credential-gated OpenAI; unit/config altitude credited

Plan: `docs/plans/2026-07-28-013-feat-p12-05-deployed-ingress-sse-drain-plan.md`

Inventory: `docs/_scratch/p12-05-deployed-ingress-inventory.md`

Runbook: `docs/operations/compose-stack-runbook.md` § TLS ingress (P12-05)

Artifact revision at evidence write: commit on `feat/p12-05-deployed-ingress-sse-drain` closing live AE1–AE4 (see git history for this evidence file)

## Prerequisites cited (DONE — do not re-prove)

| Prerequisite | Evidence |
| --- | --- |
| P5-04 | `docs/_scratch/p5-04-lightrag-real-runtime-evidence.md` |
| P7-04 | `docs/_scratch/p7-04-sse-pipeline-evidence.md` |
| P7-06 | `docs/_scratch/p7-06-synthesis-isolation-heartbeat-evidence.md` |
| P9-05 | `docs/_scratch/p9-05-ci-validators-evidence.md` |
| P10-01..03 | `docs/_scratch/p10-01-compose-config-evidence.md`, `p10-02-stack-smoke-evidence.md`, `p10-03-worker-lifecycle-evidence.md` |
| P12-02 | `docs/_scratch/p12-02-suite-contract-convergence-evidence.md` |

## What landed

| Deliverable | Path / proof |
| --- | --- |
| TLS overlay + Caddy `default_sni` | `app/compose.stack.tls.yml`, `app/stack-tls/Caddyfile` |
| Live overlay (domain controller command; egress for embeddings) | `app/compose.stack.live.yml`; `domain_runtime_controller._ensure_network` non-internal |
| Drain-hold seam (`SIGUSR1` + `enter_drain_hold`) | `app/context_engine/app.py`; unit `tests/test_api_shutdown_drain.py` |
| Trust / SSE / drain proof scripts | `app/scripts/stack_ingress_{trust,sse,drain}_proof.py` |
| AE1 inter-arrival helper (span > ε rejects one buffered blob) | `app/context_engine/dev/ingress_sse_proof.py`; `tests/test_stack_ingress_sse_helpers.py` |
| Live domain preflight helper | `app/scripts/_p12_05_live_domain_preflight.py` (operator; not a verify gate) |
| Parser packaging (`libxcb1` for Docling/OpenCV) | `app/Dockerfile` when `CE_STACK_PARSERS_IMAGE=1`; packaging test |
| Upload multipart typing | `app/context_engine/api/routes.py` (Starlette `UploadFile`) |
| Runbook three-file boot + SIGUSR1 drain | `docs/operations/compose-stack-runbook.md` |

## Commands / results (unit altitude)

```bash
cd app
python -m pytest tests/test_api_shutdown_drain.py tests/test_stack_ingress_sse_helpers.py -q
# 9 passed (includes span-based inter-arrival + clustered-token acceptance)
python scripts/generate_stack_tls_certs.py
# OK: wrote cert.pem and key.pem under app/.stack-tls
```

## Live topology (2026-07-29)

Three-file stack from `app/`:

```bash
docker compose --env-file .env.stack.local \
  -f compose.stack.yml -f compose.stack.live.yml -f compose.stack.tls.yml \
  up --build -d
```

Env names only (values in gitignored `app/.env.stack.local`): `CE_STACK_PUBLIC_ORIGIN=https://127.0.0.1:8443`, `CONTEXT_ENGINE_TESTING=false`, secure session cookies, `CE_INLINE_TURN_WORKERS=false`, `CE_STACK_TLS_CERT_DIR`, `CE_STACK_LIVE_RUNTIME_ROOT`, `OPENAI_API_KEY`, CSRF/graph keys. Host Postgres publish used loopback **5439** in this capture (5438 occupied).

Domain preflight (sealed OpenAI synthesis + start + fixture upload/prepare/index):

```bash
cd app
python -u scripts/_p12_05_live_domain_preflight.py --env-file .env.stack.local
# DOMAIN_ID=p12-05-sse-live (public opaque slug; query-eligible / index ready)
```

## AE matrix (live digests)

| AE | Status | Digest (safe) |
| --- | --- | --- |
| AE4 trust/TLS | **pass** | `ca=yes`; compose unpublished `api`/`frontend`; HTTPS CSRF login+mutation; hostile Origin; CSRF missing+mismatch 403; forged trust/identity headers; no vacuous `--api-publish` pass |
| AE1 incremental SSE | **pass** | credentials present=true; ≥2 timed `answer.delta` on contiguous stream; inter-arrival span > 25ms (not one buffered blob) |
| AE2 disconnect/resume/replay | **pass** | disconnect ≠ cancel; resume continued; terminal replay `replay:true` |
| AE3 drain | **pass** | SIGUSR1 drain-hold; new turns `503 capacity_unavailable`; resume/tail reachable; `stack_worker.stop_claim`; api/worker restarted |

### AE4

```text
P12-05 trust proof -> https://127.0.0.1:8443 (user present=True; ca=yes)
OK: compose config shows api/frontend ports unpublished
OK: HTTPS CSRF login + mutation through public origin
OK: hostile Origin rejected
OK: CSRF missing fail-closed HTTP 403
OK: CSRF mismatch fail-closed HTTP 403
OK: forged trust/identity headers did not break authorized mutation
OK: AE4 unpublished evidence from compose config (no --api-publish vacuous pass)
```

### AE1 / AE2

```bash
cd app
python -u scripts/stack_ingress_sse_proof.py --env-file .env.stack.local --domain-id p12-05-sse-live
```

```text
P12-05 SSE proof -> https://127.0.0.1:8443 (credentials present=true; ca=yes; epsilon_ms=25.0)
OK: AE1 ≥2 timed answer.delta on contiguous stream (epsilon_ms=25.0)
OK: AE2 disconnect ≠ cancel; resume continued
OK: AE2 terminal replay marked replay:true
```

AE1 gate note: consecutive LLM tokens may arrive &lt;ε within a chunk; the helper requires first-to-last `answer.delta` span &gt; `SSE_DELTA_INTER_ARRIVAL_EPSILON_MS` so a single buffered blob still fails (KTD3/R4).

### AE3

```bash
cd app
python -u scripts/stack_ingress_drain_proof.py --env-file .env.stack.local
```

```text
P12-05 drain proof -> https://127.0.0.1:8443 (ca=yes; live_overlay=True)
OK: AE3 new turns rejected with 503 capacity_unavailable
OK: AE3 resume/tail path still reachable during drain-hold (HTTP 404)
OK: observed stack_worker.stop_claim
OK: AE3 drain-hold + stop_claim completed; api/worker restarted for recovery
```

## Privacy checklist

- No API keys, CSRF secrets, passwords, cookies, prompts, or runtime URLs in this evidence file
- Cert private key stays under gitignored `app/.stack-tls/`
- Scripts report `credentials present=true/false` and `ca=yes` only
- Do not paste unredacted `docker compose config` env into digests
- Operator PDFs used for indexing are not committed as product fixtures from this capture

## Residuals (named owners — not this slice DONE blockers)

| Residual | Owner |
| --- | --- |
| Deployed PDF byte-range through ingress | P12-07 |
| Ingress adversarial deletion | P12-07 |
| Playwright / browser CSRF product / two-user cache | P12-07 |
| Hard provider-I/O abort beyond cooperative drain | P12-08 |
| HA / multi-region / production digests | P12-08 |

## Tracker

`docs/master-build-plan.md` P12-05 → **DONE** with this evidence revision. DRIFT-05/24/25 deployed halves advanced in `docs/brownfield-refactor-register.md`.
