# P12-07 Phase 1 Graph Adaptation Inventory

Date: 2026-07-28

Owner: P12-07 U7

Status: DONE — authority contract + adaptation boundary recorded before U8–U10 product code

Requirements and decisions: R10–R14; KTD9–KTD13; M-14–M-21;
FR-05a / FR-10; DRIFT-04;
`docs/plans/2026-07-28-015-feat-p12-07-browser-e2e-capacity-plan.md` U7.

## Scope

- Inventory reuse / adapt / reject for legacy graph surfaces under
  `.references/code/context_engine/client` and related LightRAG graph API
  helpers before private runtime, API, and workbench implementation (U8–U10).
- Pin KTD9 (Phase 1 read-only `/database-visualize`), KTD10 (adapt
  Sigma/Graphology interaction; reject legacy trust model), KTD11
  (immutable extraction binding — detail U8), KTD12 (opaque
  `CE_GRAPH_REF_KEY` refs), KTD13 (bounded snapshot + label search;
  coordinates are presentation state).
- Confirm U7 freezes endpoints, closed Graph* DTOs, admission/truncation
  semantics, and bans browser→LightRAG, mutation APIs, and raw vendor IDs.
- Flag blockers for later units: private extraction stub replacement (U8),
  generated contract registration (U9), gallery `graph-unavailable` retirement
  (U10).

## Disposition register

| Surface | Prior evidence | Disposition | P12-07 target |
| --- | --- | --- | --- |
| Authority “graph unavailable / no request” language | AGENTS, PRD, catalogs, frontend route/a11y/visual contracts | replace | U7 coordinated read-only graph contract |
| `GET /domains/{domainId}/graph` (+ labels) | Absent from catalogs; legacy used direct `/graphs` | add | U9 thin handlers → `services/graphs.py`; closed Graph* DTOs |
| Immutable graph-extraction profile binding | Domain freeze covered embedding only | add | U8 schema/service; PRD/architecture documented in U7 |
| Private LightRAG graph extract/snapshot port | Runtime shim / constant extraction stub | modify | U8 generation-fenced bounded private operation |
| `/database-visualize` workbench | Deliberate unavailable / no-request (P9-03) | replace | U10 read-only canvas + list/detail |
| Sigma / Graphology pan/zoom/layout/select | Legacy `GraphViewer` / `GraphControl` / layout helpers | adapt | CE-owned feature under generated client only |
| Bounded label-search concepts | Legacy MiniSearch + `/graph/labels/search` | adapt | Server `.../graph/labels`; client presentation search of current snapshot only |
| Direct LightRAG `/graphs` + port selection | `api/lightrag.ts`, `useLightragGraph`, domain port store | reject | Same-origin BFF → FastAPI only |
| Raw node/edge property bags / vendor IDs | `stores/graph.ts` `RawNodeType.properties` | reject | Opaque refs + allowlisted Graph* fields |
| Handwritten graph/admin API types | `knowledge-graph-admin.ts`, local LightRAG types | reject | Generated client from OpenAPI |
| Entity/relation mutation UI/API | Legacy admin/mutation affordances | reject | Out of Phase 1 scope |
| Broad Zustand settings persistence for graph | `useSettingsStore` depth/maxNodes/queryLabel persistence | reject | Server-owned bounds; tab-memory presentation only |
| `graph-unavailable` parity trio | P9-06 FACTORY_READY | replace | U10 enabled workbench target(s) |
| DRIFT-04 graph-unavailable disposition | DONE no-request half | modify | P12-07 enabled residual after U7–U10 + E2E |
| Seeded pump / relief-valve graph keys | Evidence fixtures only | add | `seeded-demo-and-test-data.md` graph fixture keys (U2 materializes) |

## Module inventory

Legacy paths are read-only reference evidence under
`.references/code/context_engine/client`.

| Path | Role | Disposition | Notes |
| --- | --- | --- | --- |
| `src/features/graph/GraphViewer.tsx` | Sigma container, refresh, theme-aware settings | adapt | Keep pan/zoom/select composition; strip Settings mutation chrome and direct hook→LightRAG load |
| `src/components/graph/GraphControl.tsx` | Pointer/touch select, highlight, edge events | adapt | Presentation selection only; bind to opaque node refs |
| `src/components/graph/ZoomControl.tsx` | Zoom controls | adapt | Tokenized CE controls |
| `src/components/graph/LayoutsControl.tsx` | Layout switching | adapt | Local layout only; no server layout authority |
| `src/components/graph/FocusOnNode.tsx` | Camera focus on selection | adapt | Driven by URL/`node` selection |
| `src/components/graph/FullScreenControl.tsx` | Fullscreen chrome | adapt or omit | Only if a11y/focus contracts remain intact |
| `src/components/graph/Legend.tsx` / `LegendButton.tsx` | Kind legend | adapt | Safe kinds only; no raw type catalogs from runtime |
| `src/components/graph/PropertiesView.tsx` | Node/edge property inspector | reject | Raw property bags forbidden; replace with closed detail (label/kind/degree/neighbors) |
| `src/components/graph/Settings.tsx` / `SettingsDisplay.tsx` | Browser-owned depth/maxNodes/labels toggles | reject | Depth/caps are server-owned; presentation toggles only if non-authoritative |
| `src/hooks/useLightragGraph.tsx` | Loads graph via LightRAG client + MiniSearch | reject data path; adapt concepts | Replace fetch with generated graph client; retain local search-over-snapshot idea only as presentation aid |
| `src/api/lightrag.ts` (`queryGraphs`, label helpers) | Direct `/graphs` and `/graph/labels/*` | reject | No browser LightRAG API |
| `src/lib/api/knowledge-graph-admin.ts` | Admin domain create with `host_port`, retrieval knobs | reject | Violates runtime/port privacy and closed DTOs |
| `src/stores/graph.ts` | Zustand raw graph, selection, search engine | adapt narrowly | Selection/focus/layout memory OK; reject persisted raw graphs, properties, vendor ids |
| `src/utils/graphColor.ts` | Kind→color mapping | adapt | Tokenized colors; kinds from safe DTO fields only |
| `src/lib/graph/visualizationModes.ts` | Layout/visualization modes | adapt | Client presentation |
| `src/components/settings/panels/KnowledgeGraphSettingsPanel.tsx` | Broad KG settings / runtime surface | reject | No browser-selected runtime or mutation settings |

## Closed contract freeze (U7)

Endpoints:

- `GET /api/v1/domains/{domainId}/graph` — optional bounded `label` focus; server-owned depth=3, max 500 nodes, 2000 edges, 2 MiB upstream, 10 s deadline
- `GET /api/v1/domains/{domainId}/graph/labels` — trimmed `q` 2–160, `limit` 1–50

DTOs: `GraphDomainDto`, `GraphNodeDto`, `GraphEdgeDto`, `GraphLabelDto`, `GraphLabelSearchDto`, `GraphSnapshotDto` exactly as in `docs/contracts/dto-schema-catalog.md`.

Kept bans: browser→LightRAG/runtime; graph mutation APIs; raw vendor IDs/properties; reuse of tombstoned M-12/M-13 (new cases are M-14+).

## Traceability

| Interaction / E2E | Owning unit after U7 |
| --- | --- |
| M-14 / E2E-M14 | U9 + U10 |
| M-15 / E2E-M15 | U9 + U10 |
| M-16 / E2E-M16 | U9 + U10 |
| M-17 / E2E-M17 | U8 + U9 + U10 |
| M-18 / E2E-M18 | U8 + U9 + U10 |
| M-19 / E2E-M19 | U9 (+ capacity harness) |
| M-20 / E2E-M20 | U8 + U9 |
| M-21 / E2E-M21 | U10 |

## Explicit non-claims

- U7 does not register OpenAPI routes, implement Python/TS handlers, or replace `GraphPage` behavior.
- Legacy Sigma visual fidelity is not acceptance by itself; generated contracts, authorization, and a11y list/detail parity are mandatory.
- M-12/M-13 remain phase-3 wiki tombstones and are not reused.
