# Future Feature Brief: Wiki Layer

Status: deferred to release Phase 3, after Phase 2 observability acceptance.

Planned implementation branch: `feature/wiki-layer` (create when Phase 3 is approved; no wiki work belongs in the Phase 1 or Phase 2 branch).

## Scope boundary

This brief preserves product intent without authorizing implementation. It is non-normative for Phases 1 and 2 and must not be used as an input to either phase's estimates, migrations, API generation, frontend routing, fixtures, tests, Definition of Done, or production release gates.

Phases 1 and 2 must not include partial or dormant wiki scaffolding. In particular, they have no wiki tables, enums, DTOs, endpoints, composer-ref kind, service module, navigation item, route, UI component, seed data, browser scenario, deletion hook, backup assertion, or release dependency.

## Retained future intent

The future branch may introduce a governed knowledge-publication layer with:

- member browsing of published pages and immutable revision history;
- member-owned contribution drafts with version/ETag conflict handling;
- evidence-backed contribution submission;
- administrator review, publish, and reject transitions;
- atomic, monotonically increasing immutable revisions;
- invalidation that blocks unpublished contributions when supporting evidence is deleted and marks affected published pages for review;
- a dedicated browser/review workspace and optional wiki references in governed context assembly.

## Candidate contract inventory

The following inventory captures the removed design so the future branch can reassess it. Names and shapes are not reserved Phase 1 or Phase 2 contract surface.

Candidate relational model:

- `wiki_pages` with published/needs-review/archive state and a current immutable revision pointer;
- `wiki_revisions` with a unique positive revision number per page and no update path after insertion;
- `wiki_contributions` with owner, optional target page, reviewer, version, and draft/submitted/published/rejected/blocked states;
- `wiki_contribution_evidence_refs` with ordered evidence linkage and active/invalidated state;
- optional wiki targets on composer-ref tokens and accepted turn refs.

Candidate member API:

- published page list, page detail, and revision-history reads;
- owner-scoped contribution list/create/read/update and submit;
- wiki targets in governed reference discovery after authorization and state checks.

Candidate administrator API:

- reviewable contribution list/detail;
- publish and reject transitions guarded by version/ETag and idempotency rules;
- atomic next-revision allocation during publish.

Candidate frontend surface:

- `/wiki` page browsing, member contribution editing/status, and administrator review views;
- a page viewer, contribution editor, review panel, responsive list/detail behavior, safe URL refs, accessibility flows, and visual baselines;
- optional Wiki tabs in the governed reference picker and turn inspector.

## Future branch delivery slices

1. Contract and threat-model slice: approve PRD requirements, roles, case IDs, privacy classification, API/DTO vocabulary, audit events, and an ADR.
2. Persistence and service slice: add migrations, constraints, ownership queries, immutable revision behavior, state transitions, and transaction/concurrency tests.
3. Member API slice: implement published reads and owner contribution workflow with ETag conflict handling and contract tests.
4. Administrator API slice: implement review/publish/reject, exactly-once revision allocation, auditing, and competing-review tests.
5. Lifecycle integration slice: integrate source/domain deletion, evidence invalidation, page review state, backup/restore, and reconciliation.
6. Frontend slice: add routes, generated clients, browsing/edit/review UI, responsive behavior, accessibility, copy, URL state, and cache isolation.
7. Release slice: add deterministic fixtures, browser/visual/concurrency/failure evidence, migration/rollback proof, observability, runbooks, and a later-release gate.

## Re-entry criteria

Start the feature branch only after Phase 2 is production-accepted and a Phase 3 contract change is approved. The branch must then:

1. define new PRD requirements and member/admin interaction cases;
2. add versioned schema migrations, DTOs, HTTP routes, and any SSE changes as one coherent contract;
3. define authorization, ownership, concurrency, deletion, audit, backup/restore, and privacy behavior;
4. add deterministic fixtures, service/contract/concurrency/browser tests, accessibility coverage, and visual baselines;
5. update the master plan and production release dependency graph only when the feature is intentionally targeted for a later release.

Until those criteria are met, the Phase 1 and Phase 2 behavior for any wiki route or API request is absence from the product contract, not a placeholder or disabled implementation.
