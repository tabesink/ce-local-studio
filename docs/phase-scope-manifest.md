# Phase Scope Manifest

This is the machine-read D0 boundary. The table is sorted bytewise by record class and subject. Notes are non-authoritative.

| recordClass | subject | value | notes |
| --- | --- | --- | --- |
| active-route | /chat | phase-1 | durable grounded chat workbench |
| active-route | /database-visualize | phase-1 | deliberate unavailable state only |
| active-route | /documents | phase-1 | governed source library and viewer |
| active-route | /login | phase-1 | authentication entry |
| active-route | /settings | phase-1 | member and administrator settings |
| case-tombstone | A-11 | phase-2 | removed without renumbering A-13 |
| case-tombstone | A-12 | phase-2 | removed without renumbering A-13 |
| case-tombstone | M-12 | phase-3 | removed without renumbering survivors |
| case-tombstone | M-13 | phase-3 | removed without renumbering survivors |
| child-ceiling | docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md#phase-boundary-override | prohibited | child remains phase-1 subordinate |
| child-ceiling | docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md#public-http-dto-sse-ref-persistence-authority | prohibited | public contracts remain higher authority |
| child-ceiling | docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md#d0-application-completion | prohibited | D0 is documentation only |
| child-ceiling | docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md#live-stub-product-state | prohibited | live acceptance requires server DTOs |
| child-ceiling | docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md#new-route-authority | prohibited | routes remain product-contract owned |
| child-ceiling | docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md#uncontracted-shared-primitive | prohibited | catalog gaps cannot invent primitives |
| governed-ref-kind | evidence | phase-1 | authorized turn Evidence |
| governed-ref-kind | source | phase-1 | authorized source context |
| governed-ref-kind | template | phase-1 | approved prompt template |
| phase-order | release-order | phase-1>phase-2-observability>phase-3-wiki | future phases require new contracts |
| prohibited-lexeme | audit-read-endpoint | /api/v1/admin/audit-events | public audit read endpoint declaration |
| prohibited-lexeme | diagnostics-endpoint | /api/v1/admin/diagnostics | public diagnostics endpoint declaration |
| prohibited-lexeme | logs-route | route: /logs | product route declaration |
| prohibited-lexeme | server-route | route: /server | product route declaration |
| prohibited-lexeme | usage-route | route: /usage | product route declaration |
| prohibited-lexeme | wiki-case-family | ### M-12 | removed case heading |
| prohibited-lexeme | wiki-dto | WikiPageDto | removed public DTO declaration |
| prohibited-lexeme | wiki-endpoint | /api/v1/wiki | removed endpoint declaration |
| prohibited-lexeme | wiki-ref-kind | ref_kind = 'wiki' | removed ref-kind declaration |
| prohibited-lexeme | wiki-route | route: /wiki | removed product route declaration |
| prohibited-lexeme | wiki-table | CREATE TABLE wiki_pages | removed target table declaration |
| removed-public-surface | audit-read-endpoint | http | later operator contract only |
| removed-public-surface | diagnostics-endpoint | http | later operator contract only |
| removed-public-surface | logs-route | route | later operator contract only |
| removed-public-surface | server-route | route | later operator contract only |
| removed-public-surface | usage-route | route | later operator contract only |
| removed-public-surface | wiki-case-family | case-family | later publication contract only |
| removed-public-surface | wiki-dto | dto | later publication contract only |
| removed-public-surface | wiki-endpoint | http | later publication contract only |
| removed-public-surface | wiki-ref-kind | ref | later publication contract only |
| removed-public-surface | wiki-route | route | later publication contract only |
| removed-public-surface | wiki-table | table | clean Phase 1 target excludes it |
| retained-safety-capability | allowlisted-logs | phase-1-private | secret-safe structured logs |
| retained-safety-capability | bounded-metrics | phase-1-private | service health only |
| retained-safety-capability | correlation | phase-1-private | request and private trace correlation |
| retained-safety-capability | health-readiness | phase-1-private | aggregate liveness and readiness |
| retained-safety-capability | privacy-checks | phase-1-private | response storage log and artifact scans |
| retained-safety-capability | runbooks | phase-1-private | deployment and recovery procedures |
| retained-safety-capability | transactional-audit | phase-1-private | protected mutation and denial writes |
| scan-file | AGENTS.md | active | repository governance |
| scan-file | DESIGN.md | active | subordinate visual constitution |
| scan-file | STRATEGY.md | active | frontend-factory strategy |
| scan-file | docs/README.md | active | documentation entry point |
| scan-file | docs/_scratch/code-docs-drift-review.md | historical | immutable dated review |
| scan-file | docs/_scratch/docs-phase-alignment-evidence.md | evidence-output | sole post-scan evidence output |
| scan-file | docs/architecture/api-and-integration-flows.md | active | architecture contract |
| scan-file | docs/architecture/as-built-gaps-and-decisions.md | active | brownfield evidence boundary |
| scan-file | docs/architecture/components.md | active | component authority |
| scan-file | docs/architecture/data-and-lifecycle.md | active | lifecycle authority |
| scan-file | docs/architecture/deployment-topology.md | active | deployment authority |
| scan-file | docs/architecture/frontend-security-boundary.md | active | browser trust boundary |
| scan-file | docs/architecture/legacy-persistence-retirement.md | active | compatibility stop condition |
| scan-file | docs/architecture/overview.md | active | system shape |
| scan-file | docs/architecture/production-adaptation-blueprint.md | active | adaptation decisions |
| scan-file | docs/architecture/security-operations-and-quality.md | active | operational safety |
| scan-file | docs/brownfield-refactor-register.md | active | drift disposition authority |
| scan-file | docs/contracts/document-and-evidence-contract.md | active | document and Evidence contract |
| scan-file | docs/contracts/dto-schema-catalog.md | active | public DTO contract |
| scan-file | docs/contracts/http-api-catalog.md | active | HTTP contract |
| scan-file | docs/contracts/sse-event-catalog.md | active | SSE contract |
| scan-file | docs/database-schema.txt | active | Phase 1 clean-install target |
| scan-file | docs/frontend/AGENTS.md | active | frontend agent rules |
| scan-file | docs/frontend/accessibility-contract.md | active | accessibility contract |
| scan-file | docs/frontend/api-client-and-stream-runtime.md | active | client and reducer contract |
| scan-file | docs/frontend/browser-e2e-scenarios.md | active | browser evidence contract |
| scan-file | docs/frontend/chat-and-evidence-workbench.md | active | chat workspace contract |
| scan-file | docs/frontend/component-contracts.md | active | component ownership |
| scan-file | docs/frontend/content-and-microcopy.md | active | safe product language |
| scan-file | docs/frontend/design-token-contract.md | active | token authority |
| scan-file | docs/frontend/document-viewer-spec.md | active | viewer contract |
| scan-file | docs/frontend/frontend-state-ownership.md | active | state ownership |
| scan-file | docs/frontend/implementation-slices.md | active | frontend work slices |
| scan-file | docs/frontend/interaction-state-catalog.md | active | reachable state authority |
| scan-file | docs/frontend/motion-and-feedback-spec.md | active | motion and feedback |
| scan-file | docs/frontend/navigation-and-url-state.md | active | navigation and URL state |
| scan-file | docs/frontend/responsive-and-desktop-matrix.md | active | responsive authority |
| scan-file | docs/frontend/route-and-workspace-spec.md | active | route workspace authority |
| scan-file | docs/frontend/source-adaptation-map.md | active | reference adaptation |
| scan-file | docs/frontend/ui-parity-spec.md | active | parity and factory catalog |
| scan-file | docs/frontend/visual-regression-plan.md | active | visual evidence |
| scan-file | docs/future/README.md | future | non-normative release roadmap |
| scan-file | docs/future/observability-layer.md | future | non-normative Phase 2 brief |
| scan-file | docs/future/wiki-layer.md | future | non-normative Phase 3 brief |
| scan-file | docs/ideation/2026-07-22-lean-agent-shell-ideation.html | historical | historical ideation only |
| scan-file | docs/interaction-behavior-prd.md | active | stable behavioral cases |
| scan-file | docs/master-build-plan.md | active | brownfield package tracker |
| scan-file | docs/phase-scope-manifest.md | manifest | this structural source |
| scan-file | docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md | mixed-removal | approved D0 execution plan |
| scan-file | docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md | mixed-removal | subordinate chat child |
| scan-file | docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md | active | subordinate frontend child |
| scan-file | docs/plans/2026-07-25-001-feat-scoped-retrieval-provenance-plan.md | active | P6-01 scoped retrieval plan |
| scan-file | docs/plans/2026-07-25-002-feat-stateless-evidence-projection-plan.md | active | P6-02 stateless Evidence plan |
| scan-file | docs/plans/2026-07-26-001-feat-conversation-ownership-plan.md | active | P7-01 conversation ownership plan |
| scan-file | docs/plans/2026-07-27-001-feat-server-intent-gate-plan.md | active | P7-02 server intent gate plan |
| scan-file | docs/plans/2026-07-27-002-feat-bounded-rag-orchestration-plan.md | active | P7-03 bounded RAG orchestration plan |
| scan-file | docs/plans/2026-07-27-004-feat-sealed-sse-replay-pipeline-plan.md | active | P7-04 sealed SSE replay pipeline plan |
| scan-file | docs/plans/2026-07-27-005-feat-delete-redaction-omission-plan.md | active | P7-05 delete redaction omission plan |
| scan-file | docs/plans/2026-07-27-006-feat-audit-allowlist-denial-privacy-plan.md | active | P8-01 audit allowlist denial privacy plan |
| scan-file | docs/plans/2026-07-27-007-feat-safe-json-logs-metrics-plan.md | active | P8-02 safe JSON logs metrics plan |
| scan-file | docs/plans/2026-07-27-008-feat-health-privacy-resilience-gate-plan.md | active | P8-03 health privacy resilience gate plan |
| scan-file | docs/prd.md | active | product authority |
| scan-file | docs/quality/definition-of-done.md | active | completion gates |
| scan-file | docs/quality/seeded-demo-and-test-data.md | active | deterministic fixture contract |
| scan-file | docs/residual-review-findings/feat-p2-02-credential-encryption-dto.md | active | accepted review residuals |
| scan-file | docs/residual-review-findings/feat-p2-03-embedding-validation-defaults.md | active | accepted review residuals |
| scan-file | docs/residual-review-findings/feat-p4-03-parser-adapters-canonical-blocks.md | active | accepted review residuals |
| scan-file | docs/residual-review-findings/feat-p4-04-source-outline-delete-apis.md | active | accepted review residuals |
| scan-file | docs/residual-review-findings/feat-p5-01-index-state-worker-claim.md | active | accepted review residuals |
| scan-file | docs/residual-review-findings/feat-p5-02-lightrag-renderer-adapter.md | active | accepted review residuals |
| scan-file | docs/residual-review-findings/feat-p5-03-index-eligibility.md | active | accepted review residuals |
| scan-file | docs/residual-review-findings/feat-p6-scoped-evidence.md | active | accepted review residuals |
| scan-file | docs/residual-review-findings/main-7de9a4a.md | active | accepted review residuals |
| scan-file | docs/residual-review-findings/main-e187555.md | active | accepted review residuals |
| scan-file | docs/tech-stack.md | active | technology authority |
