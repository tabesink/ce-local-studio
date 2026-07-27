# P8-02 Safe JSON Logs Correlation Bounded Metrics Evidence

Date: 2026-07-27

Slice: P8-02

Status: DONE (focused unit proofs)

Plan: `docs/plans/2026-07-27-007-feat-safe-json-logs-metrics-plan.md`

Inventory: `docs/_scratch/p8-02-telemetry-inventory.md`

## What landed

- Process-local metrics helper `app/context_engine/services/metrics.py` with closed
  metric names/labels, identity key/value rejection, nested best-effort emit, and
  `metrics.outage` safe_log on failure (outage logging cannot break callers).
- HTTP middleware increments `http_request` beside allowlisted JSON logs and
  swallows emit failures so responses always return.
- Chat terminals optionally log `request_id` when available (option b — no schema
  migration); worker path omits `request_id` and joins claim↔terminal via
  `trace_id`; emit `chat_turn_terminal`.
- Worker succeed/fail terminals emit `worker_operation` with bounded
  `operation_type` (claim logs stay log-only).
- Adversarial privacy scans cover formatted JSON logs + metric dumps, including
  mutation windows on real logger sinks and worker-path correlation.
- No scrape/read observability routes; Phase 1 absence retained.

## Commands

```text
cd app
python -m pytest tests/test_service_metrics.py \
  tests/test_log_metric_privacy_scan.py \
  tests/test_structured_logging.py \
  tests/test_phase_one_observability_scope.py -q
```

Result: 18 passed (post-review hardening).

## Residuals

- P8-03: liveness/readiness re-proof, cross-sink privacy/resilience gate evidence.
- Phase 2: product Logs/Usage/Server/audit-browser surfaces.
- P12: deployed-ingress adversarial breadth.
- Optional follow-up: persist HTTP `request_id` on turns (option a) if ops need
  request_id on worker-finalized terminals without relying on `trace_id`.
- Optional follow-up: mechanical lint forbidding raw `logger.*` outside `safe_log`.
