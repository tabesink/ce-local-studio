# P5-04 Real Per-Domain LightRAG Runtime Inventory

Date: 2026-07-28

Owner: P5-04

Status: DONE — inventory frozen; U2–U7 implemented; evidence `docs/_scratch/p5-04-lightrag-real-runtime-evidence.md`

Requirements and cases: FR-05; A-03/A-04/A-08/A-09/C-01; DRIFT-27 concurrency
residual; `docs/master-build-plan.md` P5-04 reopen (2026-07-28);
`docs/architecture/deployment-topology.md` private per-domain LightRAG
endpoints; plan `docs/plans/2026-07-28-006-feat-p5-04-real-lightrag-runtime-plan.md`
(KTD1–KTD8).

## Scope

- Replace Alpine sleep Docker placeholder with one private vendored LightRAG
  1.4.16 runtime per Knowledge Domain (Compose live lane DONE altitude).
- Inject immutable domain embedding profile + sealed credentials
  (`TrustedRuntimeResolver`); remove synthetic 8-dim / stub LLM from the
  production `native`+`docker` path.
- Preserve schema-v2 handoff, `LightRAGClientProtocol`, scoped retrieval, and
  P6 provenance mapper; close DRIFT-27 concurrency via per-container isolation.
- Dual lane: default Compose/CI stay `local`/`local`; live overlay uses
  `CE_DOMAIN_RUNTIME_CONTROLLER_KIND=docker` + `CE_LIGHTRAG_CLIENT_KIND=native`.
- Prove submit→ready→mapped Evidence→delete/absence, uncertain recovery,
  restart, and two-domain parallel isolation on the live lane.

## Out of scope

- P12-04 backup/restore rebuild drills (consumes this runtime).
- P12-05 deployed-ingress SSE through real runtime.
- P12-06 SBOM / immutable release digests (may pin local/dev image for proof).
- P12-07 browser E2E and capacity stress beyond two-domain isolation.
- JSON domain registry, Redis/RQ, Celery/broker, public/browser-visible runtime
  URLs, vendor-owned source upload, heuristic Evidence mapping.
- Making live providers or live Docker mandatory in root `scripts/verify.sh`.
- New public HTTP/DTO fields for runtime internals.

## Transport feasibility (KTD2 / OQ1)

| Check | Result |
| --- | --- |
| Vendored package | `app/vendor/lightrag/` pin `1.4.16` via `lightrag_runtime.py` |
| HTTP server | `app/vendor/lightrag/api/lightrag_server.py` — FastAPI + uvicorn |
| Document insert | `api/routers/document_routes.py` text insert routes |
| Query / data | `api/routers/query_routes.py` includes `/query/data` |
| Private HTTP | **Feasible** — bind container-internal listen on Compose/private Docker network; **no host publish** |
| Stop condition | If live wiring cannot preserve schema-v2 chunk content through insert/query → stop (no heuristic mapper) |
| Forbidden fallback | Shared in-process module state / process-wide lock as production model |

Exact listen port/path is an implementation detail for U2; acceptance gate is not deferred.

## Disposition register

| Surface | Current evidence | Disposition | P5-04 action |
| --- | --- | --- | --- |
| `tools/domain_runtime_controller.py` Alpine sleep + `--network none` | P3-02 placeholder | **replace** | Real LightRAG image/entrypoint; private Docker network; no host ports; health = labels + private-endpoint probe (KTD6) |
| `DockerDomainRuntimeController` | Typed uncertain/timeout (P3-02) | **modify** | Payload/health semantics for private endpoint + sealed bootstrap path; keep Protocol |
| `LocalDomainRuntimeController` | CI/Compose default | **retain-and-reverify** | Unchanged for default CI |
| `LocalLightRAGIndexClient` | Filesystem JSON index (P5-02/P5-03) | **retain-and-reverify** | CI/default Compose only |
| `LightRAGClient` synthetic embed/LLM + `_NATIVE_LIGHTRAG_LIFECYCLE_LOCK` | P5-02 timeout half; DRIFT-27 concurrency open | **replace** (production path) | Private HTTP client to per-domain container; resolver injection; lock not production model |
| `index_client_from_settings` kinds `local`/`native` | Factory | **retain-and-reverify** | Live lane pins `native`+`docker` (KTD3); no third kind vocabulary |
| `render_blocks_to_lightrag_handoff` schema v2 | P6-01 | **credit** | Do not rewrite |
| `SourceIndexWorker` lease/uncertain/backoff | P5-03; DRIFT-28/32 DONE | **modify** | Add running+healthy gate for new submits (R12); preserve uncertain probe |
| `TrustedRuntimeResolver.resolve_embedding_profile` | Domain create freeze (P2/P3) | **credit** + **extend use** | Call at submit/retrieve; sealed mode-600 bootstrap (KTD5) |
| Schema-v2 + P6 `parse_ce_block_marker` / scoped retrieval | P6-01/P6-02 | **credit** | Real chunks must retain markers or stop |
| `compose.stack.yml` `local`/`local` | P10-01 deliberate | **retain** | Do not flip defaults |
| `compose.stack.live.yml` | Documented in `.env.stack.example`; **missing** | **add** | U5 overlay |
| Process-wide native lock | P5-02/P5-03 residual | **replace** (prod) / **defer residual** | Closed by per-container isolation; OQ2 for any non-production native leftover |
| Legacy JSON registry / Redis/RQ / public URLs / heuristic Evidence | `.references/` | **reject** | Do not restore |
| P12-04/05/06/07 | Depend on P5-04 | **defer** | Residual consumers |

## Disposition legend

| Disposition | Meaning |
| --- | --- |
| credit | Prior slice owns proof; do not reimplement |
| retain / retain-and-reverify | Keep behavior; re-prove if touched |
| modify | Change in place behind existing ports |
| replace | Remove placeholder/synthetic production path |
| add | New artifact for live lane |
| defer | Out of this slice; named owner |
| reject | Explicitly forbidden |

## Dual-lane matrix

| Lane | Controller | Client | Proves | Gate |
| --- | --- | --- | --- | --- |
| Default CI / `compose.stack.yml` | `local` | `local` | Packaging, PG state machines, contracts | Root verify |
| Live overlay `compose.stack.live.yml` | `docker` | `native` | Real runtime, isolation, uncertain, delete | Opt-in evidence / markers |

## Retained invariants

- PostgreSQL authoritative; runtime dirs ephemeral rebuildable derivatives.
- Schema-v2 handoff and P6 marker-only mapping — no heuristic parsing.
- Adapters never authorize or mutate product `index_state` / domain state.
- No public DTO/SSE/log leakage of runtime URLs, paths, credentials, handoff text, or block IDs as LightRAG IDs.
- P5-03 timeout→uncertain→readiness-probe and DRIFT-28 backoff preserved.
- Embedding profile id frozen at domain create; credentials resolved at call time via sealed bootstrap.

## Reject list (explicit)

1. JSON domain registry / `domains.json` manifest.
2. Redis/RQ (or Celery/broker) locking or job queues for domain runtime.
3. Browser-visible or host-published runtime URLs.
4. Vendor-owned source upload authority.
5. Heuristic Evidence mapping from provider paths/UUIDs.
6. Crediting Alpine sleep or synthetic 8-dim native as production DONE.

## Gaps closed by task-owned evidence (planned)

| Unit | Gap |
| --- | --- |
| U2 | Real container lifecycle + private-endpoint health; sealed mount layout |
| U3 | `native` production client over private HTTP + embedding injection |
| U4 | Worker domain running/healthy gate; uncertain path against real outcomes |
| U5 | `compose.stack.live.yml` + env example + config tests |
| U6 | Live AE proofs + two-domain isolation; evidence doc |
| U7 | Master-build-plan DONE + DRIFT-27 concurrency closure language |

## Mapping to plan U-IDs

| Inventory seam | Unit |
| --- | --- |
| This document | U1 (this file) |
| Controller tool + Docker adapter health | U2 |
| LightRAGClient / factory / resolver injection | U3 |
| SourceIndexWorker gate | U4 |
| Compose live overlay | U5 |
| Dual-lane tests + evidence | U6 |
| Tracker / DRIFT-27 | U7 |
