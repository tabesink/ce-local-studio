# P8-02 Safe JSON Logs Correlation Bounded Metrics Inventory

Date: 2026-07-27

Owner: P8-02

Status: DONE — inventory frozen; U2–U4 emitters and privacy proofs evidenced 2026-07-27

Requirements: FR-09; Operability NFR; DRIFT-20 / DRIFT-29 log/metric half

Plan: `docs/plans/2026-07-27-007-feat-safe-json-logs-metrics-plan.md`

## Scope

Inventory every production `safe_log` event, freeze the closed metric
name/label catalog, and record correlation dispositions before emitters land.
P8-02 owns allowlisted JSON logs, request/trace correlation proofs, process-local
bounded metrics, and adversarial privacy scans of **log + metric sinks only**.

Out of scope: P8-03 health/readiness and cross-sink privacy/resilience; Phase 2
Logs/Usage/Server/audit-browser; scrape/OpenMetrics routes; enabling
`DisabledTracingPort` exporters; schema migration to persist HTTP `request_id`
on `conversation_turns`.

## Session decisions

| Decision | Choice |
| --- | --- |
| Chat terminal `request_id` plumbing | **(b)** Join claim↔terminal via `trace_id` when HTTP `request_id` is absent; optionally thread `request_id` from `TurnStartResult` into finalize helpers when present — **no** turn-row schema migration |
| Metrics visibility | Process-local registry + test snapshot/reset only |
| Logging posture | Extend `safe_log` family; sibling metrics helper |

## Disposition classes

| Class | Meaning |
| --- | --- |
| `retain` | Already correct; re-verify in tests |
| `correlate-fix` | Add missing allowlisted correlation fields (option b) |
| `emit-metric-peer` | Keep log; add bounded metric increment beside it |
| `retain-absence` | Keep Phase 1 absence (no scrape / no observability read) |
| `out-of-scope` | Explicit non-goal for this slice |

## Closed log field allowlist (retain)

From `SAFE_LOG_FIELDS` in `app/context_engine/services/structured_logging.py`:

`event`, `request_id`, `trace_id`, `actor_kind`, `domain_id`, `source_id`,
`conversation_turn_id`, `operation_id`, `client_request_id`, `index_request_id`,
`safe_error_code`, `elapsed_ms`, `http_method`, `http_route`, `http_status`,
`outcome`, `replay`

Formatter structural keys (always present): `timestamp`, `level`, `logger`.

No expansion in P8-02.

## Closed metric catalog (freeze)

### Metric names

| Name | Kind | Emission peers |
| --- | --- | --- |
| `http_request` | counter (+ elapsed observed via log; optional timer later) | `app.py` `http_request` safe_log |
| `chat_turn_terminal` | counter | `chat.turn_persisted` / `chat.turn_failed` |
| `worker_operation` | counter | prep/index/delete/domain claim or fail peers |

### Label keys (strict)

| Key | Allowed values |
| --- | --- |
| `http_method` | Closed HTTP verbs observed (`GET`, `POST`, `PATCH`, `PUT`, `DELETE`, `HEAD`, `OPTIONS`) or `OTHER` |
| `http_route` | FastAPI route **template** only (e.g. `/api/v1/conversations/{conversation_id}`); never concrete path IDs |
| `outcome` | Closed: `succeeded`, `failed`, `denied`, `running` (chat claim only if ever metered — terminals use succeeded/failed) |
| `actor_kind` | Closed: `public`, `member`, `administrator`, `worker` |
| `status_class` | Closed: `2xx`, `3xx`, `4xx`, `5xx` |
| `safe_error_code` | Closed product ErrorCode strings already used in envelopes; omit when absent |
| `chat_route_kind` | Closed: `direct_llm`, `domain_rag`, `unknown` |
| `operation_type` | Closed: `source_preparation`, `source_index`, `source_delete`, `domain_delete`, `stack_worker` |

### Forbidden as metric labels (keys or values)

Identity-bearing `private_operational` and content: `domain_id`, `source_id`,
`conversation_turn_id`, `operation_id`, `request_id`, `trace_id`,
`client_request_id`, `index_request_id`, user ids, usernames, emails, filenames,
titles, prompts, answers, excerpts, paths, runtime URLs, stack traces, concrete
URL paths with resource IDs.

## `safe_log` event register

| Event | Surface | Fields today | Disposition | P8-02 action |
| --- | --- | --- | --- | --- |
| `http_request` | `app.py` middleware | request_id, actor_kind, elapsed_ms, http_*, outcome, optional safe_error_code | `retain` + `emit-metric-peer` | Metric `http_request`; optionally attach safe_error_code on 4xx when available without reading bodies |
| `chat.turn_replayed` | `chat_turns.py` | request_id, trace_id, domain_id, conversation_turn_id, client_request_id, outcome, replay | `retain` | Correlation already good |
| `chat.turn_claimed` | `chat_turns.py` | request_id, trace_id, … | `retain` | Correlation already good |
| `chat.turn_persisted` | `_complete_turn` | trace_id, domain_id, conversation_turn_id, client_request_id, outcome — **no request_id** | `correlate-fix` + `emit-metric-peer` | Option (b): add optional `request_id` kwarg when caller has `TurnStartResult.request_id`; join via `trace_id` always; metric `chat_turn_terminal` |
| `chat.turn_failed` | `_fail_turn` | same gap | `correlate-fix` + `emit-metric-peer` | Same as persisted |
| `source_preparation_worker.claimed` | `sources.py` | request_id, domain_id, source_id, operation_id, outcome | `retain` | Log-only at claim; metric peers live on succeed/fail terminals |
| `source_preparation_worker.failed` / succeed terminals | `sources.py` | + safe_error_code on fail | `retain` + `emit-metric-peer` | Metric `worker_operation` operation_type=`source_preparation` |
| `source_preparation_worker.image_cleanup_deferred` | `sources.py` | request_id, domain/source/op ids, outcome | `retain` | No metric (deferred cleanup noise) |
| `source_delete_worker.claimed` | `sources.py` | request_id, ids, outcome | `retain` | Log-only at claim |
| `source_delete_worker.failed` / succeed terminals | `sources.py` | outcome[, safe_error_code] | `retain` + `emit-metric-peer` | operation_type=`source_delete` |
| `source_index_worker.claimed` | `indexing.py` | domain_id, source_id, index_request_id, outcome — no op request_id | `retain` | Log-only at claim; leave request_id gap as deferred follow-up |
| `source_index_worker` succeed/fail terminals | `indexing.py` | outcome[, safe_error_code] | `retain` + `emit-metric-peer` | operation_type=`source_index` |
| `domain_delete_worker.claimed` | `domains.py` | request_id, domain_id, operation_id, outcome | `retain` | Log-only at claim |
| `domain_delete_worker` succeed/fail terminals | `domains.py` | outcome[, safe_error_code] | `retain` + `emit-metric-peer` | operation_type=`domain_delete` |
| `stack_worker.started` / `.iteration_failed` / `.heartbeat_failed` | `worker.py` | outcome[, safe_error_code] | `retain` + `emit-metric-peer` (fail only) | Metric on fail paths; started may stay log-only |
| `tracing.outage` | `tracing.py` | trace_id, safe_error_code | `retain` | Keep DisabledTracingPort; no exporter |

## Correlation decision (option b)

- **HTTP:** Server-owned `request_id` on header + `http_request` log (already P0-03/P1-04). No `trace_id` on HTTP logs.
- **Chat:** Claim/replay already log `request_id` + `trace_id`. Terminals must always log `trace_id`. When `TurnStartResult.request_id` is available on the finalize path, pass it into `_complete_turn` / `_fail_turn` safe_log. Worker-reconstructed starts may omit `request_id`; ops join claim↔terminal via `trace_id`.
- **TracingPort:** Remain disabled. Phase 1 correlation = allowlisted logs + persisted `trace_id`.

## Out of scope / absence

| Surface | Disposition |
| --- | --- |
| `/metrics`, `/prometheus`, OpenMetrics routes | `retain-absence` |
| Phase 2 audit/log/diagnostic read APIs | `retain-absence` |
| Health/readiness expansion | `out-of-scope` → P8-03 |
| Cross-sink privacy (audit+log+metric+health together) | `out-of-scope` → P8-03 |
| CLI `print` / dead `getLogger` leftovers | `out-of-scope` (not JSON sink) |

## Evidence design

1. Unit: metrics allowlist key/value rejection + snapshot/reset + best-effort.
2. Unit/integration: chat claim+terminal share `trace_id`; optional `request_id` when start carries it.
3. Adversarial: JsonLogFormatter capture + metric dump sentinel absence (R11 classes).
4. Absence: no scrape routes; observability-scope green.
5. Scratch evidence + DRIFT-20/29 log/metric half + master-build-plan P8-02 DONE after green.
