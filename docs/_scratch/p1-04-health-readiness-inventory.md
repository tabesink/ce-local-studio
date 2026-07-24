# P1-04 Health, Error, and Logging Brownfield Inventory

Date: 2026-07-24

Owner: P1-04

Status: DONE

Requirements: FR-09, FR-11, A-13

## Scope boundary

P1-04 owns request-ID/error/logging re-verification, process-only liveness, and
the currently implementable readiness aggregate: configuration validity,
database reachability, exact supported Alembic head, and explicit administrator
bootstrap viability. P4 owns the governed object-storage port/capability. P10-02
owns deployment wiring for indispensable storage readiness and final aggregate
proof. Provider and individual domain/runtime outages never fail global
readiness.

## Disposition register

| Surface | Current evidence | Disposition | P1-04 action and proof |
| --- | --- | --- | --- |
| Request ID middleware | P0-03 generates a server-owned UUID, ignores caller authority, emits exactly `X-Request-ID`, correlates errors, and records bounded request completion/failure logs | retain-and-reverify | Run malformed, failure, live, and ready HTTP cases; prove header/body/log correlation without caller control |
| Error translation | P0-03 provides the closed four-field envelope and safe exception fallback | retain-and-reverify | Prove readiness failures expose only `dependency_unavailable`, safe message, request ID, and empty fields |
| Structured logging | `safe_log` accepts a closed field set and JSON logging is configured at API/worker entry points | retain-and-reverify | Prove request logs contain only allowlisted dimensions and omit URL query/body, credentials, usernames, stack traces, and raw exceptions |
| Liveness | `/health/live` returns the closed `live` projection without dependencies | retain-and-reverify | Prove it remains successful when readiness dependencies fail and performs no database/storage/provider/runtime probe |
| Database readiness | `/health/ready` currently executes only `SELECT 1` | modify | Add one safe aggregate service that verifies connectivity and exact Alembic head |
| Schema compatibility | Alembic has one proven head `d07141ac7d95`, but readiness does not compare the deployed database revision | add | Fail safe when `alembic_version` is absent, behind, ahead, malformed, or unreachable; do not migrate from the API |
| Bootstrap viability | Administrator bootstrap is explicit and insert-only, but readiness does not verify its configured enabled administrator exists with the administrator role | add | Fail safe for missing bootstrap configuration or absent/disabled/downgraded configured administrator |
| Configuration validity | App construction already fails closed on required encryption configuration; later trusted Host/cookie validation remains P1-05 | retain-and-reverify | Keep startup validation authoritative and include only readiness-relevant bootstrap settings here |
| Object-store readiness | No approved governed storage readiness port exists yet; filesystem storage is development-only | defer to P4/P10-02 | Do not invent a provider or count local path existence as production object-store evidence |
| Cache policy | SSE had an explicit private no-store policy while canonical JSON errors lacked it; personalized success/byte/BFF classification remains cross-layer | modify | Canonical errors now carry private no-store; two-user/BFF/browser cache isolation remains P9-05 |

## Completed evidence strategy

Add a pure readiness service with closed internal reason codes that never cross
the HTTP boundary. Start with PostgreSQL HTTP characterization showing the
current false-ready result for missing bootstrap and schema mismatch. Then prove
exact-head plus enabled configured administrator returns `200`, all other
implemented dependency states return the same safe correlated `503`, liveness
stays `200`, and allowlisted logs contain no forbidden fixture markers.

P1-04 may close when this bounded aggregate passes and its deferred storage
boundary is explicit. DRIFT-15 remains `IN_PROGRESS` until P10-02 composes the
governed object-store capability.
