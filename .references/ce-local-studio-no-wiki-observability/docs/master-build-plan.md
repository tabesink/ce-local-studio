# Master Build Plan

## Tracker conventions

Status values: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `DEFERRED`. All rebuild tasks begin `NOT_STARTED`; source code in the reviewed repo is evidence, not completion evidence for the new build.

Each phase is a vertical slice. Complete its migrations, API/SSE contract, service behavior, tests, acceptance evidence, and operational notes before starting a dependent phase.

This tracker is limited to the Phase 1 production build. `P0` through `P12` are work packages inside release Phase 1, not later release phases. Deferred features are not dependencies, release gates, or permitted scaffolding: the Phase 2 observability layer and Phase 3 wiki layer are recorded separately under `future/`.

## Phase tracker

| ID | Phase/outcome | Status | Depends on | Exit gate |
| --- | --- | --- | --- | --- |
| P0 | Contract and repository spine | NOT_STARTED | - | governance, vocabulary, ADRs, API/data/SSE conventions, CI skeleton approved |
| P1 | Trusted app foundation | NOT_STARTED | P0 | migrated Postgres, seeded admin, cookie auth, owner/admin guards, health and safe errors pass |
| P2 | Trusted runtime configuration | NOT_STARTED | P1 | encrypted credentials, model profiles, parser/synthesis defaults, admin contract tests pass |
| P3 | Knowledge Domain runtime | NOT_STARTED | P2 | per-domain runtime boundary, lifecycle operations, leases/generations, readiness proven |
| P4 | Source preparation | NOT_STARTED | P3 | upload/storage/parser adapters produce canonical blocks and support retry/cancel/delete |
| P5 | LightRAG indexing eligibility | NOT_STARTED | P4 | vendored fixture proves idempotent submit, readiness, delete, provenance markers, eligibility |
| P6 | Scoped Evidence retrieval | NOT_STARTED | P5 | single-domain authorized retrieval maps only valid local blocks to safe Evidence |
| P7 | Durable grounded streaming chat | NOT_STARTED | P6 | conversation ownership, intent gate, bounded RAG, SSE, idempotent replay, redaction pass |
| P8 | Operational safety and Phase 1 gate | NOT_STARTED | P1-P7 | transactional audit writes, allowlisted logs, request/trace correlation, health, privacy scans, and resilience evidence pass |
| P9 | Thin Next.js frontend | NOT_STARTED | P1-P8 | login/chat/documents/settings and the reserved graph state use only versioned APIs and pass parity/accessibility checks |
| P10 | Deployable application stack | NOT_STARTED | P8-P9 | runnable Compose stack, explicit migrations/bootstrap, worker lifecycle, smoke path, and operator runbook pass |
| P11 | Governed context assembly | NOT_STARTED | P6-P7 | opaque refs for sources/evidence/templates, private bounded assembly, replay fingerprint and invalidation pass |
| P12 | Production release and recovery | NOT_STARTED | P0-P11 | immutable artifacts, deployed-path streaming, migration/rollback, security/load/backup/restore and runbooks pass |

## Detailed task register

### P0 - Contract and repository spine

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P0-01 | NOT_STARTED | - | create repo layout, Python/Node manifests and committed lockfiles |
| P0-02 | NOT_STARTED | P0-01 | adopt vocabulary, authority precedence, coding-agent rules and stop conditions |
| P0-03 | NOT_STARTED | P0-02 | define canonical error envelope, ID/time conventions and API `/api/v1` policy |
| P0-04 | NOT_STARTED | P0-03 | define data ownership, privacy classification, adapter ports and state-machine conventions |
| P0-05 | NOT_STARTED | P0-01 | CI for lint, typecheck, tests, OpenAPI snapshots, frontend build and Docker integration |
| P0-06 | NOT_STARTED | P0-03 | generate OpenAPI/JSON Schema and typed client from the HTTP, DTO and evidence catalogs |

### P1-P2 - Identity and trusted configuration

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P1-01 | NOT_STARTED | P0 | FastAPI app factory, settings, PostgreSQL engine/session and Alembic baseline |
| P1-02 | NOT_STARTED | P1-01 | users/auth_sessions schema, Argon2, admin seed and opaque cookie sessions |
| P1-03 | NOT_STARTED | P1-02 | current-user/admin dependencies, ownership helpers and denial audit hook |
| P1-04 | NOT_STARTED | P1-01 | request IDs, safe errors/logging, live/ready endpoints |
| P1-05 | NOT_STARTED | P1-02,P1-03 | Origin/Host and CSRF policy, session rotation/revocation/TTL, login throttling and ingress auth tests |
| P1-06 | NOT_STARTED | P1-01 | append-only audit schema, transactional AuditService and protected-mutation helper |
| P2-01 | NOT_STARTED | P1 | provider_configs, model_profiles, runtime_settings migrations and services |
| P2-02 | NOT_STARTED | P2-01 | credential encryption/rotation and safe DTO projection |
| P2-03 | NOT_STARTED | P2-01 | synthesis/embedding validation, immutable dimension rules and defaults |

### P3-P6 - Domain, content, indexing, retrieval

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P3-01 | NOT_STARTED | P2 | domains/domain_operations schema and admin APIs |
| P3-02 | NOT_STARTED | P3-01 | runtime controller port plus local/Docker implementations |
| P3-03 | NOT_STARTED | P3-02 | lease, generation, conflict, readiness and async delete behavior |
| P4-01 | NOT_STARTED | P3 | source_documents/preparation_operations schema, opaque public document refs and secure storage adapter |
| P4-02 | NOT_STARTED | P4-01 | upload validation, domain deduplication and parser-kind freeze |
| P4-03 | NOT_STARTED | P4-02 | Docling/Reducto adapters and canonical blocks/images transaction |
| P4-04 | NOT_STARTED | P4-03 | outline, operation, retry/cancel and delete APIs |
| P5-01 | NOT_STARTED | P4 | index state/generation fields and worker claim loop |
| P5-02 | NOT_STARTED | P5-01 | versioned canonical-block renderer and vendored LightRAG adapter |
| P5-03 | NOT_STARTED | P5-02 | submit/poll/retry/cancel/delete and query-eligibility service |
| P6-01 | NOT_STARTED | P5 | scoped retrieval port and raw-hit provenance mapper |
| P6-02 | NOT_STARTED | P6-01 | authorized safe Evidence DTO, ordering, excerpt limits and failure mapping |

### P7-P8 - Chat and operational safety

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P7-01 | NOT_STARTED | P6 | conversations, turns and opaque public evidence-ref migrations plus owner CRUD |
| P7-02 | NOT_STARTED | P7-01 | server intent gate and direct/domain route invariants |
| P7-03 | NOT_STARTED | P7-02 | bounded plan/retrieve/repair/synthesize orchestration |
| P7-04 | NOT_STARTED | P7-03 | versioned SSE stream, terminal persistence and idempotent replay |
| P7-05 | NOT_STARTED | P7-04 | source/domain delete redaction hooks and public omission tests |
| P8-01 | NOT_STARTED | P1-06,P7 | transactional audit-write allowlist coverage, denial events and privacy/adversarial audit tests |
| P8-02 | NOT_STARTED | P8-01 | safe JSON logs, request/trace correlation and bounded-cardinality service metrics |
| P8-03 | NOT_STARTED | P8-02 | liveness/readiness, privacy scans and resilience/load evidence with no observability read API or UI |

### P9-P11 - User interface, deployable runtime, and governed context workflows

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P9-01 | NOT_STARTED | P1,P8 | Next.js shell, Local Studio tokens/primitives, login and middleware guards |
| P9-02 | NOT_STARTED | P7 | typed API/SSE client, chat route, conversation history and Evidence Panel |
| P9-03 | NOT_STARTED | P4-P6 | documents/outline/preview and graph route through approved contracts |
| P9-04 | NOT_STARTED | P2-P3,P8 | settings and domain-operation surfaces; no Logs, Usage, Server, audit-browser, or diagnostics-browser UI |
| P9-05 | NOT_STARTED | P9-01 | import-direction, thin-route, server/browser boundary and contract/barrel CI validators |
| P10-01 | NOT_STARTED | P8,P9 | Compose services and production-like server configuration for PostgreSQL, migration, API, worker and frontend |
| P10-02 | NOT_STARTED | P10-01 | explicit migration/bootstrap plus BFF/API/SSE core-path smoke stack |
| P10-03 | NOT_STARTED | P10-02 | startup/shutdown, worker claim recovery and deployment operator runbook |
| P11-01 | NOT_STARTED | P6 | prompt_templates/composer_ref_tokens/accepted-ref schema and seeds for source/evidence/template refs |
| P11-02 | NOT_STARTED | P11-01 | discovery, opaque-token validation, domain compatibility and expiry |
| P11-03 | NOT_STARTED | P11-02,P7 | private context assembly, turn fingerprint, replay/conflict and redaction |

### P12 - Production release and recovery

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P12-01 | NOT_STARTED | P0-P11 | fresh install and upgrade migration proofs against PostgreSQL 16 |
| P12-02 | NOT_STARTED | P0-P11 | full backend/frontend/adapter/Docker suite and contract snapshot convergence |
| P12-03 | NOT_STARTED | P8-P11 | authz, secret/content leakage, deletion/redaction and adversarial retrieval review |
| P12-04 | NOT_STARTED | P12-01 | backup/restore, image rollback, failed-worker recovery and incident drills |
| P12-05 | NOT_STARTED | P7,P9,P12-02 | deployed-ingress incremental SSE, reconnect/replay, graceful shutdown and stream-drain proof |
| P12-06 | NOT_STARTED | P0,P12-02 | immutable artifact manifest with pinned runtimes, locks, schema and contract versions, SBOM and provenance |
| P12-07 | NOT_STARTED | P12-02,P12-03 | accessibility, browser E2E, capacity, provider-failure and minimum operational-safety evidence |
| P12-08 | NOT_STARTED | P12-03,P12-04,P12-05,P12-06,P12-07 | production acceptance record, runbooks, recovery objectives and release decision |

## Post-Phase 1 release sequence

| Release phase | Planned branch | Scope | Relationship to this tracker |
| --- | --- | --- | --- |
| Phase 2 | `feature/observability-layer` | Logs, Usage, Server status, audit/diagnostic browsing, live log delivery, analytics, retention/export UX | future brief only; no `P*` task or Phase 1 gate |
| Phase 3 | `feature/wiki-layer` | governed pages, revisions, contributions, review/publication, wiki context refs and UI | future brief only; no `P*` task or Phase 1 gate |

See `future/README.md`, `future/observability-layer.md`, and `future/wiki-layer.md`. Activating a future phase requires a new approved contract and an updated build tracker on its named feature branch.

## Cross-phase gates

- No phase may invent a browser-visible field absent from the approved contract.
- No Phase 1 task may scaffold a route, DTO, table, event, component, fixture, or disabled flag belonging only to a future brief.
- A migration must land with its model/service tests and rollback/restore note.
- Every external call needs timeout, safe error mapping, and an idempotency/retry decision.
- Every delete path must identify retrieval fencing, chat redaction, governed-ref invalidation, remote cleanup, local cleanup, audit, and failure recovery.
- Every UI surface must prove backend authority and Local Studio visual/accessibility parity.
- Every completed feature must map its applicable `interaction-behavior-prd.md` cases to unit, contract, browser, and PostgreSQL concurrency evidence.
- Every streaming surface must prove identical live/replay reduction, duplicate/sequence handling and real-ingress non-buffering.
- Root verification must cover contracts, structure, backend, frontend, migrations, privacy scans and deployed-path integration from pinned inputs.
- Stop if the pinned LightRAG contract cannot prove provenance, idempotent submit, readiness, or deletion.
