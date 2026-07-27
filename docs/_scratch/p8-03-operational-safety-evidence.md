# P8-03 Health Privacy Resilience Operational Safety Evidence

Date: 2026-07-27

Slice: P8-03

Status: DONE (focused unit + opted-in PostgreSQL 16 proofs)

Plan: `docs/plans/2026-07-27-008-feat-health-privacy-resilience-gate-plan.md`

Inventory: `docs/_scratch/p8-03-operational-safety-inventory.md`

## What landed

- Inventory froze health surfaces, four-sink privacy union, resilience cite
  matrix, `DisabledTracingPort` retain-absence, as-built bootstrap semantics,
  and P10-02 / P12 / configured-username residuals.
- Health re-proof extended `test_health_contract.py`: live stays OK when ready
  fails; schema edges share safe `503`; ready stays OK with a stopped domain
  present; no diagnostic leakage in failure bodies.
- Combined cross-sink privacy scan
  (`tests/test_cross_sink_privacy_scan.py`) plants once and asserts absence
  across audit rows, JsonLogFormatter JSON, metric dumps, and health
  live/ready success + safe `503` bodies/headers.
- Focused resilience matrix (`tests/test_resilience_load_shed.py`) executes
  Content-Length `413 content_rejected` gate + oversize upload rejection;
  evidence selection also executed capacity `503` mapping, login-throttle
  `429`+Retry-After (PostgreSQL), and turn-lease reclaim (PostgreSQL).

## Commands

### Unit / contract (no disposable PG)

```text
cd app
python -m pytest tests/test_resilience_load_shed.py \
  tests/test_source_upload_validation.py::test_oversize_upload_is_content_rejected \
  tests/test_evidence_http_contract.py::test_m02_stateless_evidence_http_exhaustively_maps_safe_failures \
  tests/test_health_contract.py \
  tests/test_cross_sink_privacy_scan.py \
  tests/test_phase_one_observability_scope.py \
  tests/test_service_metrics.py::test_no_metrics_scrape_routes_registered -q
```

Result: 17 passed.

### Opted-in PostgreSQL 16

```text
cd app
$env:CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS='1'
$env:CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres'
python -m pytest \
  tests/test_postgres_ingress_security.py::test_p1_05_csrf_origin_peer_rotation_logout_and_throttle_on_postgresql_16 \
  tests/test_postgres_turn_leases.py::test_ae1_expired_lease_reclaim_fails_closed_after_answer_delta_on_postgresql_16 \
  tests/test_postgres_foundation.py::test_p1_04_readiness_requires_exact_schema_and_bootstrap_on_postgresql_16 -q
```

Result: 3 passed.

Changed-file Ruff: `tests/test_health_contract.py`,
`tests/test_cross_sink_privacy_scan.py`,
`tests/test_resilience_load_shed.py` clean.

## Residuals

- P10-02 / DRIFT-15: governed object-store readiness composition.
- Configured-`admin_username` readiness tightening (as-built remains any
  enabled administrator).
- Concurrent-stream `429` (A-13 / P12) — not claimed Operability-complete.
- SIGTERM / stream-drain / deployed load (P10-03 / P12).
- Phase 2: product Logs/Usage/Server/audit-browser surfaces.
- `DisabledTracingPort` remains retain-absence (no exporter).
