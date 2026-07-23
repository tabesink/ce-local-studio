# Future Feature Brief: Observability Layer

Status: deferred to release Phase 2, after Phase 1 production acceptance.

Planned implementation branch: `feature/observability-layer` (create only when Phase 2 is approved; no observability product work belongs in the Phase 1 branch).

Local evidence sources: `.references/ce-local-studio-no-wiki-observability/docs/future/observability-layer.md`, `.references/ce-local-studio-trim-feature-review.md`, and the deferred seams recorded in `docs/_scratch/code-docs-drift-review.md`.

## Scope boundary

This brief preserves the Logs and Usage plans without authorizing their implementation. It is non-normative for Phase 1 and must not be used as an input to Phase 1 estimates, migrations, public API generation, frontend routing, fixtures, browser tests, or release gates.

Phase 1 retains only the minimum operational-safety baseline required to run the core product: server-side allowlisted structured logs, request/trace correlation, append-only transactional audit writes, liveness/readiness, bounded-cardinality service metrics, privacy scans, and deployment runbooks. That baseline has no product-facing log store, audit browser, diagnostics browser, usage analytics, dashboard, live log stream, export, deletion controls, or `/logs`, `/usage`, or `/server` route. These prerequisites must not grow into partial or dormant Phase 2 scaffolding.

## Retained Phase 2 product intent

Phase 2 may add three read-heavy, server-authorized operator surfaces:

- **Logs:** discover log sessions, inspect bounded recent lines, search/filter content, follow live output, download an authorized session, and apply approved retention/deletion policy;
- **Usage:** inspect inference and coding-agent activity, token/request/session volume, latency and time-to-first-token, cache behavior, model performance, hourly/daily activity, and clearly labelled observed versus benchmark metrics;
- **Server:** view safe controller reachability, inference/runtime state, health, lease, and contract/version status without exposing arbitrary infrastructure targets.

The browser remains a projection. It cannot choose a controller URL, Docker target, filesystem path, provider endpoint, credential, or authorization scope.

## Candidate product contracts

The following names capture the reference plan and are not reserved Phase 1 surface.

Candidate frontend routes and feature boundaries:

- `/logs` backed by a dedicated `features/logs/*` module;
- `/usage` backed by a dedicated usage/analytics module;
- `/server` as the safe operational-status companion to Logs;
- a node selector only where the server returns authorized nodes; compact table/list layouts on desktop and a session slide-over on mobile.

Candidate Logs capabilities and APIs:

- list and search authorized log sessions;
- load a bounded tail, with a candidate default of 2,000 lines and a hard browser cap of 20,000 lines;
- content search, explicit local-filter indication, auto-scroll, and live connected/reconnecting state;
- authenticated server-controlled SSE for live output, with no secrets in query strings;
- server-scoped downloads carrying safe source/time/node metadata;
- policy-driven retention and clear-old/delete controls; controller or other protected sessions cannot be deleted as ordinary files;
- candidate endpoints: `GET /logs`, `GET /logs/{sessionId}`, and `GET /logs/{sessionId}/stream`.

Candidate Usage capabilities and APIs:

- canonical analytics responses for totals, time buckets, model rows, latency, TTFT, cache metrics, and peak metrics;
- sortable model table, expandable peak metrics, explicit empty/error/unavailable states, last-updated time, and stale-data indication;
- filters for time range, node, workspace/organization, actor, model, provider, recipe, and session when authorized;
- server-scoped export rather than exporting an untrusted browser aggregation;
- candidate endpoints: `GET /usage`, `GET /peak-metrics`, and `GET /usage/pi-sessions`.

API names, limits, polling intervals, retention periods, and whether audit review belongs in the same operator workspace require a Phase 2 contract decision. The branch must not simply expose existing runtime files or controller payloads.

## Candidate event and analytics dimensions

Phase 2 should define one server-owned normalized event model before implementing UI. Candidate dimensions are:

```text
node_id
actor_id
organization_id or workspace_id
recipe_id
model_id
provider_id
session_id
occurred_at
outcome
token, latency, and TTFT measures
source and visibility classification
```

Do not claim meaningful multi-user counts until authenticated `actor_id` is persisted at the event boundary. Missing or unavailable data renders as unavailable, never as a fabricated zero. Start with lightweight bounded storage and aggregation; an analytics warehouse is not a default requirement.

## Authorization and privacy rules

- Raw runtime/controller/Docker-backed logs are operator or administrator data, not ordinary member data.
- A member may see only their own approved request/session history if Phase 2 explicitly adds that capability.
- Workspace managers may see approved workspace aggregates; node operators may see their nodes; system administrators may receive cross-node views; auditors receive only approved aggregates or audit projections.
- Every query, export, stream, and delete is scoped server-side. Browser filters never create authority.
- Log records and stream frames carry a server-defined node, timestamp, source, and visibility classification.
- Runtime logs remain separate from security audit events; one must not be presented as the other.
- Redaction occurs before persistence/transport where possible and always before browser delivery. The UI discloses the redaction policy without revealing removed content.
- Retention and deletion are administrator policy operations, not arbitrary filesystem deletion.
- Live logs use authenticated SSE; usage uses polling, refresh, or another bounded read pattern unless a later contract justifies streaming.

## Phase 2 delivery slices

1. Contract and threat-model slice: approve actors, scopes, data classifications, normalized events, retention, redaction, exports, deletion semantics, API/DTO vocabulary, and an ADR.
2. Telemetry-ingestion slice: attach authenticated actor/node/workspace dimensions, normalize allowed sources, enforce redaction, and prove bounded storage/cardinality.
3. Logs backend slice: add authorized session discovery, bounded tail/search, authenticated SSE, download, retention, and protected-session rules.
4. Usage backend slice: add server-scoped aggregation, peak/model/session metrics, observed-versus-benchmark labelling, freshness, and unavailable-data behavior.
5. Operator frontend slice: add `/logs`, `/usage`, and `/server` with URL-backed safe filters, responsive session selection, live/reconnecting states, accessibility, and thin typed clients.
6. Security and lifecycle slice: prove cross-user/workspace/node isolation, redaction, retention, stream revocation, export authorization, deletion policy, backup/restore, and failure recovery.
7. Release slice: add deterministic telemetry fixtures, contract/concurrency/browser/visual/load evidence, migration and rollback proof, runbooks, alert ownership, and the Phase 2 release gate.

## Re-entry criteria

Start the branch only after Phase 1 is production-accepted and a Phase 2 contract change is approved. The branch must then:

1. decide the deployment/tenant vocabulary and authorization matrix before exposing node, actor, or workspace filters;
2. add its schema, DTOs, APIs, streams, routes, fixtures, and tests as one coherent versioned contract;
3. prove actor identity is propagated before enabling user counts or user-scoped analytics;
4. define retention, redaction, export, deletion, audit separation, backup/restore, and incident behavior;
5. update the master plan and release dependency graph only when Phase 2 is intentionally activated.

Until those criteria are met, the Phase 1 behavior for Logs, Usage, Server status, audit browsing, and diagnostics browsing is absence from the product contract, not a placeholder or disabled implementation.
