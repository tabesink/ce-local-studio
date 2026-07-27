# P8-03 Health Privacy Resilience Operational Safety Inventory

Date: 2026-07-27

Owner: P8-03

Status: DONE — inventory frozen; U2–U4 proofs evidenced 2026-07-27

Requirements: FR-09; Operability/Resilience/Privacy NFRs; DRIFT-20 / DRIFT-29
cross-sink/health; DRIFT-15 residual (storage)

Plan: `docs/plans/2026-07-27-008-feat-health-privacy-resilience-gate-plan.md`

## Scope

Freeze health/live/ready surfaces, the four-sink privacy union, the focused
resilience cite matrix, and honest residuals before new tests land. P8-03 owns
re-proof of the P1-04 readiness aggregate (DB + exact Alembic head + any enabled
administrator), one combined cross-sink adversarial privacy scan (audit + JSON
logs + metrics + health), and focused local 413 / login-429 / capacity-503 +
lease recovery evidence — with no observability read API/UI.

Out of scope: object-store readiness (P10-02 / DRIFT-15); Phase 2
Logs/Usage/Server/audit-browser; scrape/OpenMetrics; enabling
`DisabledTracingPort`; concurrent-stream `429`; SIGTERM/stream-drain / full
deployed load (P12); configured-`admin_username` readiness tightening (product
decision residual).

## Disposition classes

| Class | Meaning |
| --- | --- |
| `retain-and-reverify` | Already correct; re-run / keep green |
| `extend-proof` | Behavior exists; add thin fixture/coverage |
| `cite-evidence` | Prove by executing existing suite in evidence selection |
| `retain-absence` | Keep Phase 1 absence (no product surface / disabled port) |
| `out-of-scope` | Explicit non-goal for this slice |

## Frozen head pin

`SUPPORTED_ALEMBIC_HEAD` / PG `HEAD_REVISION` = `e9f2a1b83c70`

## Bootstrap semantics (as-built)

`check_readiness` requires **any** enabled administrator
(`ROLE_ADMINISTRATOR` + `is_disabled=false`), not specifically
`Settings.admin_username`. P1-04 inventory wording said “configured
administrator”; this slice re-proves as-built and leaves configured-username
tightening as an explicit residual (not closed).

## Health register

| Surface | Evidence today | Disposition | P8-03 action |
| --- | --- | --- | --- |
| `GET /health/live` → `{status:live}` | `test_health_contract.py`, P1-04 PG | `retain-and-reverify` | Prove live stays 200 when ready deps fail; no DB probe |
| `GET /health/ready` success `{status:ready}` | same | `retain-and-reverify` | Exact head + enabled admin |
| Ready fail → `503 dependency_unavailable` + `X-Request-ID` + `private, no-store` | same | `retain-and-reverify` | Identical safe envelope; empty `fields` |
| Internal reasons `database_unavailable` / `schema_incompatible` / `bootstrap_incomplete` | `readiness.py` | `retain-and-reverify` | Never serialize reasons |
| Alembic ahead / malformed / absent | partial PG coverage | `extend-proof` | Same safe 503 shape where gaps remain |
| Provider/domain outage must not fail ready | claimed in P1-04; under-proven | `extend-proof` | Thin ready=200 with stopped domain / unready provider |
| Object-store readiness | deferred P4/P10-02 | `out-of-scope` | Do not invent probe; DRIFT-15 stays open |
| Worker SIGTERM / claim drain | `should_continue` hook unwired | `out-of-scope` | P10-03 / P12-05 residual |

## Privacy sink union

| Sink | Existing proof | Disposition | P8-03 action |
| --- | --- | --- | --- |
| `audit_events` rows | `test_audit_privacy_scan.py` | `cite-evidence` + join | Plant once; assert in combined scan |
| `JsonLogFormatter` JSON | `test_log_metric_privacy_scan.py` | `cite-evidence` + join | Same |
| Process-local metrics dump | same + `snapshot_metrics` | `cite-evidence` + join | Same |
| Health live/ready bodies + headers | not sentinel-scanned | `extend-proof` | Include in combined scan |
| Combined four-sink window | **absent** | `extend-proof` | Create `test_cross_sink_privacy_scan.py` |
| `DisabledTracingPort` / traces | disabled; no exporter | `retain-absence` | Inventory only; do not enable |
| Test snapshots / fixtures | suite hygiene | `cite-evidence` | Note in evidence; not a product sink |

### Unified forbidden sentinel set (superset)

`SECRET_PROMPT_SENTINEL`, `SECRET_ANSWER_SENTINEL`, `SECRET_EXCERPT_SENTINEL`,
`SECRET_CREDENTIAL_SENTINEL`, `SECRET_TITLE_SENTINEL`, `SECRET_FILENAME_SENTINEL`,
`SECRET_BODY_SENTINEL`, `PRIVATE-STACK-SENTINEL`

## Resilience cite matrix

| Path | Handler / code | Existing tests | Disposition | P8-03 action |
| --- | --- | --- | --- | --- |
| Upload / Content-Length `413 content_rejected` | `source_upload.py`; `_content_length_too_large` in `routes.py` | `test_source_upload_validation.py` (unit); HTTP early gate thin | `cite-evidence` + optional `extend-proof` | Execute unit; add thin HTTP if still missing |
| Login throttle `429 rate_limited` + `Retry-After` | `login_throttle.py` → login route | `test_postgres_ingress_security.py` | `cite-evidence` | Execute in evidence selection |
| Retrieval `503 capacity_unavailable` | `evidence.py` saturation → routes map | `test_scoped_retrieval.py`, `test_evidence_http_contract.py` | `cite-evidence` | Execute in evidence selection |
| Domain delete lease reclaim | `domains.py` / workers | `test_postgres_domain_leases.py` | `cite-evidence` | Execute ≥1 reclaim/recovery case |
| Index claim / reclaim | indexing workers | `test_postgres_source_index_claim.py` | `cite-evidence` | Execute ≥1 case |
| Turn lease reclaim / disconnect≠cancel | chat turns | `test_postgres_turn_leases.py`, `test_turn_execution_leases.py` | `cite-evidence` | Execute ≥1 case |
| Concurrent-stream `429` | not invented | — | `out-of-scope` | A-13 / P12 residual |
| Deployed load / SIGTERM drain | — | — | `out-of-scope` | P12 residual |

## Absence / observability

| Surface | Disposition | Proof |
| --- | --- | --- |
| `/metrics`, `/prometheus`, OpenMetrics | `retain-absence` | `test_service_metrics.py` |
| Phase 2 audit/log/diagnostic read | `retain-absence` | `test_phase_one_observability_scope.py`, route/production scope |
| Health diagnostic/topology payload | `retain-and-reverify` | closed DTOs + privacy scan |

## Evidence design

1. Inventory (this doc) frozen before U2–U4 code.
2. U2: health contract + PG readiness re-proof; provider/domain isolation; Alembic edges.
3. U3: one combined adversarial scan over four sinks + absence green.
4. U4: execute selected 413/429/503 + named lease tests; write evidence; advance DRIFT-20/29; mark P8-03/P8 DONE without overclaiming DRIFT-15, configured-bootstrap, concurrent-stream 429, or P12 shutdown/load.
