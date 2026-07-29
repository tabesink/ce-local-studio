# P12-05 Deployed Ingress SSE / Stream Drain Inventory

Date: 2026-07-29

Owner: P12-05

Status: FROZEN — live AE1–AE4 proven; see evidence

Plan: `docs/plans/2026-07-28-013-feat-p12-05-deployed-ingress-sse-drain-plan.md`

Evidence: `docs/_scratch/p12-05-deployed-ingress-evidence.md`

Altitude: Compose TLS + live LightRAG overlay; scripted HTTPS clients (not Playwright).
Evidence-owned (like P5-04 / P10 live) — not a default `scripts/verify.sh` gate.

Prerequisites (DONE — cite, do not hard-wait):

| Prerequisite | Evidence |
| --- | --- |
| P5-04 real LightRAG | `docs/_scratch/p5-04-lightrag-real-runtime-evidence.md` |
| P7-04 SSE producer / disconnect≠cancel | `docs/_scratch/p7-04-sse-pipeline-evidence.md` |
| P7-06 synthesis isolation + heartbeat | `docs/_scratch/p7-06-synthesis-isolation-heartbeat-evidence.md` |
| P9-05 BFF strip/emit / abort | `docs/_scratch/p9-05-ci-validators-evidence.md` |
| P10-01 Compose dual origin/peer | `docs/_scratch/p10-01-compose-config-evidence.md` |
| P10-02 BFF/API/SSE smoke | `docs/_scratch/p10-02-stack-smoke-evidence.md` |
| P10-03 worker stop-claim | `docs/_scratch/p10-03-worker-lifecycle-evidence.md` |
| P12-02 suite/contract convergence | `docs/_scratch/p12-02-suite-contract-convergence-evidence.md` |

Peer residuals (live owners after this slice):

| Residual | Owner |
| --- | --- |
| Deployed PDF byte-range through ingress | P12-07 |
| Ingress adversarial deletion | P12-07 |
| Playwright / browser CSRF product / two-user cache | P12-07 |
| Hard provider-I/O abort beyond cooperative drain | P12-08 |
| HA / multi-region / production digests | P12-08 |

## Disposition legend

| Disposition | Meaning |
| --- | --- |
| credit | Existing real-boundary proof cited; no new work required for that seam |
| gap-fill | Add topology, product seam, script, or test in this slice |
| live-proven | Gap-fill completed and green at live TLS Compose altitude |
| defer | Named live residual owner (not this slice DONE) |
| out-of-scope | Outside product identity or wrong phase |

---

## Lane A — Topology / TLS / trust

| Surface | Existing proof | Disposition | Cases |
| --- | --- | --- | --- |
| Compose dual `CE_STACK_PUBLIC_ORIGIN` + peer pin | P10-01 evidence; `compose.stack.yml` | credit | C-05 |
| HTTP + `testing=true` stack smoke | P10-02; runbook non-claim | credit (non-deployment) | — |
| TLS overlay + `testing=false` HTTPS public origin | `compose.stack.tls.yml` + AE4 | live-proven | AE4 |
| Public origin = Next only; API private | unpublished compose evidence in AE4 | live-proven | AE4 |
| Host / Origin / CSRF through TLS edge | AE4 trust proof | live-proven | AE4, C-05 |
| Direct FastAPI denial | AE4 unpublished + denial path | live-proven | AE4 |
| Forged `X-CE-Public-*` / identity headers | P9-05 local + AE4 through TLS | live-proven | AE4 |
| Ingress idle timeout > heartbeat + reconnect margin | Topology / Caddy overlay | live-proven (config) | F2 |
| Certificates outside app images | `app/.stack-tls/` gitignored | live-proven | R3 |

---

## Lane B — SSE incremental / reconnect / replay

| Surface | Existing proof | Disposition | Cases |
| --- | --- | --- | --- |
| Versioned SSE producer live/resume/replay | P7-04; fixtures; HTTP contract | credit | M-03, C-01 |
| Disconnect ≠ cancel (PG) | `test_c01_disconnect_without_cancel_*` | credit | C-01 |
| BFF pass-through body + `X-Accel-Buffering` | P9-05; `bff-proxy.ts` | credit local | M-03 |
| Compose smoke CSRF→SSE terminal | P10-02/03 `stack_smoke_*.py` | credit (buffered body) | — |
| ≥2 timed `answer.delta` through public origin | AE1 live digest | live-proven | AE1, M-03 |
| Inter-arrival gate `SSE_DELTA_INTER_ARRIVAL_EPSILON_MS` | span > ε (buffered blob fails) | live-proven | AE1 |
| Mid-stream disconnect + resume through ingress | AE2 live digest | live-proven | AE2, C-01 |
| Terminal replay through ingress | AE2 `replay:true` | live-proven | AE2 |
| Credential-gated live OpenAI for ≥2 deltas | AE1 `credentials present=true` | live-proven | AE1, R8 |
| Real LightRAG domain-RAG path | P5-04 + AE1 three-file | live-proven | AE1 |
| `CE_INLINE_TURN_WORKERS=false` worker matrix | live env + drain proof | live-proven | AE1–AE3 |
| Browser reducer / Playwright SSE | P9-02 | defer | P12-07 |

---

## Lane C — Drain / shutdown

| Surface | Existing proof | Disposition | Cases |
| --- | --- | --- | --- |
| Worker SIGTERM `stack_worker.stop_claim` | P10-03; AE3 live | live-proven | AE3 |
| Turn lease heartbeat | P7-06 | credit | AE3 |
| API stop-new-turns on drain-hold | `SIGUSR1` + live `503 capacity_unavailable` | live-proven | AE3, R9 |
| Ingress stop-new-traffic | AE3 through public origin | live-proven | AE3 |
| Resume/tail of accepted turns during grace | AE3 resume/tail reachable | live-proven | AE3 |
| Hard abort blocking provider I/O | P7-06 residual | defer | P12-08 |
| HA multi-replica drain | — | defer | P12-08 |

---

## Lane D — Privacy / non-claims

| Surface | Existing proof | Disposition | Cases |
| --- | --- | --- | --- |
| No secrets in evidence/logs | P8 privacy suite; this evidence checklist | credit + enforced | FR-09 |
| No runtime URLs / prompts in captures | P7/P8 privacy | credit + checklist | FR-09 |
| WebSockets / second stream protocol | Forbidden | out-of-scope | — |
| Default `verify.sh` live TLS/OpenAI | Explicitly not required | out-of-scope | P12-02 |

---

## Gap-fill worklist (this slice) — closed

| ID | Work | Unit | Outcome |
| --- | --- | --- | --- |
| G1 | `compose.stack.tls.yml` + env knobs + compose contract tests | U2 | live-proven |
| G2 | Trust proof script (HTTPS CSRF happy + Origin/CSRF/direct-API negatives) | U2 | AE4 green |
| G3 | Chunked SSE proof + helper unit tests (`SSE_DELTA_INTER_ARRIVAL_EPSILON_MS`) | U3 | live-proven |
| G4 | Live LightRAG + credential-gated OpenAI domain-RAG AE1/AE2 | U3 | AE1/AE2 green |
| G5 | API stop-new-turns seam + unit/service tests (`503 capacity_unavailable`) | U4 | live-proven |
| G6 | Topology drain proof script (stop-claim + resume/tail + reclaim) | U4 | AE3 green |
| G7 | Evidence + tracker + residual owner rewrites (P12-07 / P12-08) | U5 | this revision |

---

## Explicit non-claims

- HTTP + `testing=true` P10 smokes are **not** deployment evidence.
- Whole-body SSE `response.read()` is **not** AE1 credit.
- Worker `stop_claim` alone is **not** AE3 credit (requires live `503` during drain-hold).
- Playwright, deployed byte-range, ingress adversarial deletion, HA, and hard provider-I/O abort are **not** this slice.
