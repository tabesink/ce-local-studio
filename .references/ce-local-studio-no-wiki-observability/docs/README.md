# Context Engine Reconstruction Package

This package captures the product and engineering attributes needed for a coding agent to rebuild the reviewed Context Engine application.

## Package map

- `master-build-plan.md` - phased implementation tracker, dependencies, gates, and status.
- `prd.md` - product purpose, actors, capabilities, rules, and acceptance outcomes.
- `interaction-behavior-prd.md` - atomic member/admin role-play cases, UI outcomes, failure behavior, and concurrent-user rules.
- `tech-stack.md` - languages, frameworks, dependencies, infrastructure, and external systems.
- `database-schema.txt` - rebuild-oriented relational schema and persistence invariants.
- `architecture/overview.md` - system shape and authoritative boundaries.
- `architecture/components.md` - backend and frontend component responsibilities.
- `architecture/data-and-lifecycle.md` - ingestion, retrieval, chat, redaction, and governed-context state transitions.
- `architecture/api-and-integration-flows.md` - HTTP/SSE surface and major sequences.
- `architecture/security-operations-and-quality.md` - trust boundaries, operational safety, and verification.
- `architecture/as-built-gaps-and-decisions.md` - reviewed implementation gaps and decisions that must not be guessed.
- `architecture/production-adaptation-blueprint.md` - production target and explicit reuse/adapt/reject decisions derived from Local Studio's backend and frontend.

### Frontend implementation contract

- `frontend/ui-parity-spec.md` - measurable Local Studio visual-parity rules and reference viewports.
- `frontend/design-token-contract.md` - Context Engine token vocabulary and Local Studio token adaptation.
- `frontend/component-contracts.md` - approved primitives, compositions, variants, states, and ownership.
- `frontend/route-and-workspace-spec.md` - route-by-route information architecture and workspace composition.
- `frontend/chat-and-evidence-workbench.md` - three-region chat, streaming, composer, evidence, and governed-context behavior.
- `frontend/document-viewer-spec.md` - authorized PDF viewing, semantic anchors, highlights, and evidence deep links.
- `frontend/responsive-and-desktop-matrix.md` - viewport, zoom, density, and pane-to-drawer transformations.
- `frontend/interaction-state-catalog.md` - canonical loading, empty, ready, stale, failure, conflict, redacted, and recovery states.
- `frontend/navigation-and-url-state.md` - safe route state, deep links, history, restoration, and invalid-link recovery.
- `frontend/frontend-state-ownership.md` - server, URL, store, component, and cache ownership boundaries.
- `frontend/api-client-and-stream-runtime.md` - typed clients, fetch streaming, reducer, resume, retry, and cancellation algorithms.
- `frontend/accessibility-contract.md` - keyboard, focus, live-region, citation, drawer, contrast, and reduced-motion requirements.
- `frontend/motion-and-feedback-spec.md` - transition, progress, toast, optimistic feedback, and destructive-confirmation rules.
- `frontend/content-and-microcopy.md` - canonical product language, labels, status text, empty states, and safe errors.
- `frontend/visual-regression-plan.md` - deterministic screenshot fixtures, viewport matrix, diff policy, and baseline governance.
- `frontend/browser-e2e-scenarios.md` - browser and multi-user scenarios mapped to behavioral case IDs.
- `frontend/source-adaptation-map.md` - exact Local Studio source patterns to fork, adapt, replace, or reject.
- `frontend/implementation-slices.md` - coding-agent-sized vertical frontend slices and exit evidence.

### Architecture and transport contracts

- `architecture/frontend-security-boundary.md` - ingress, BFF, cookie, CSRF, cache, CSP, and document-delivery boundary.
- `architecture/deployment-topology.md` - development through production processes, scaling, health, migrations, and SSE ingress.
- `contracts/http-api-catalog.md` - endpoint authorization, request/response, idempotency, errors, pagination, and cache policy.
- `contracts/dto-schema-catalog.md` - closed public DTO fields, enums, request/query schemas, and capability error sets.
- `contracts/sse-event-catalog.md` - event envelopes, payloads, ordering, replay, terminal behavior, and examples.
- `contracts/document-and-evidence-contract.md` - safe document refs, content delivery, anchors, figures/tables, and redaction.

### Quality and fixtures

- `quality/definition-of-done.md` - mandatory implementation, contract, accessibility, parity, concurrency, privacy, and operations gates.
- `quality/seeded-demo-and-test-data.md` - deterministic actors, domains, sources, evidence, conversations, composer references, and operations.

### Future feature briefs

- `future/README.md` - release sequence: Phase 1 core product, Phase 2 observability, then Phase 3 wiki.
- `future/observability-layer.md` - non-normative Logs, Usage, and Server plan retained for the Phase 2 `feature/observability-layer` branch.
- `future/wiki-layer.md` - non-normative wiki plan retained for the Phase 3 `feature/wiki-layer` branch.

## Evidence and precedence

Review basis: `local-studio-dev-notes/_references/local-studio-ce-v1/local-studio` at Git `HEAD`, including files retrievable from Git that are deleted in the current dirty worktree.

When sources disagree, rebuild in this order:

1. repository `AGENTS.md` and governance constitution;
2. approved feature specifications and acceptance criteria;
3. versioned API, SSE, data, and AI contracts;
4. architecture and quality specifications;
5. feature plans and task lists;
6. code, migrations, tests, and runtime observations;
7. read-only reference implementations.

The explicit Phase 1 exclusions in `prd.md` control over lower-precedence implementation evidence. Code or migrations for a deferred feature must not be ported, scaffolded, or added to Phase 1 contracts merely because they exist in the reviewed checkout. Future briefs preserve intent only and create no Phase 1 estimate, dependency, acceptance case, or release gate.

The reviewed checkout has extensive pre-existing deletions. This package therefore distinguishes intended behavior in specifications from implementation evidence in surviving source and Git `HEAD`. A rebuild should restore the versioned manifests, migrations, tests, and delivery files before treating the current filesystem as complete.

Local Studio is a pattern source, not a product or code dependency. Its dependency composition, middleware ordering, contracts, streaming reducer, UI layering, design system, deployment lessons, and quality gates may be adapted. Its local-first persistence, agent tools, filesystem access, inference-controller authority, plugins, and desktop assumptions are outside Context Engine v1.
