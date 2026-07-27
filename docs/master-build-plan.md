# Master Build Plan

## Tracker conventions

Status values: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `DEFERRED`. This is a brownfield refactor of `app/client`, the P0-01-canonical `app/context_engine`, `app/vendor/lightrag`, container/environment files, and root scripts. At D0, all application tasks began `NOT_STARTED`; an existing file or passing pilot test is evidence, not completion proof. Post-D0 status changes require task-owned evidence that names the tested boundary and remaining gaps.

Each phase is a vertical slice. Complete its migrations, API/SSE contract, service behavior, tests, acceptance evidence, and operational notes before starting a dependent phase.

Every task must begin from `brownfield-refactor-register.md`: inventory current call sites and persistence/build dependencies, choose `retain-and-reverify`, `modify`, `replace`, `add`, or `remove-from-phase-1`, then prove the named boundary. Do not rebuild an existing seam until its disposition is recorded, and do not preserve a deferred seam behind a flag or unreachable route.

This tracker is limited to the Phase 1 production build. `P0` through `P12` are work packages inside release Phase 1, not later release phases. Deferred features are not dependencies, release gates, or permitted scaffolding: the Phase 2 observability layer and Phase 3 wiki layer are recorded separately under `future/`.

## Phase tracker

| ID | Phase/outcome | Status | Depends on | Exit gate |
| --- | --- | --- | --- | --- |
| P0 | Contract and repository spine | DONE | - | governance, vocabulary, ADRs, API/data/SSE conventions, CI skeleton approved |
| P1 | Trusted app foundation | DONE | P0 | migrated Postgres, seeded admin, cookie auth, owner/admin guards, health and safe errors, append-only transactional audit pass |
| P2 | Trusted runtime configuration | DONE | P1 | encrypted credentials, model profiles, parser/synthesis defaults, admin contract tests pass |
| P3 | Knowledge Domain runtime | DONE | P2 | per-domain runtime boundary, lifecycle operations, leases/generations, readiness proven |
| P4 | Source preparation | DONE | P3 | upload/storage/parser adapters produce canonical blocks and support retry/cancel/delete |
| P5 | LightRAG indexing eligibility | DONE | P4 | vendored fixture proves idempotent submit, readiness, delete, provenance markers, eligibility |
| P6 | Scoped Evidence retrieval | DONE | P5 | single-domain authorized retrieval maps only valid local blocks to safe Evidence |
| P7 | Durable grounded streaming chat | DONE | P6 | conversation ownership, intent gate, bounded RAG, SSE, idempotent replay, redaction pass |
| P8 | Operational safety and Phase 1 gate | DONE | P1-P7 | transactional audit writes, allowlisted logs, request/trace correlation, health, privacy scans, and resilience evidence pass |
| P9 | Thin Next.js frontend | NOT_STARTED | P1-P8 | login/chat/documents/settings and the reserved graph state use only versioned APIs and pass parity/accessibility checks |
| P10 | Deployable application stack | NOT_STARTED | P8-P9 | runnable Compose stack, explicit migrations/bootstrap, worker lifecycle, smoke path, and operator runbook pass |
| P11 | Governed context assembly | NOT_STARTED | P6-P7 | opaque refs for sources/evidence/templates, private bounded assembly, replay fingerprint and invalidation pass |
| P12 | Production release and recovery | NOT_STARTED | P0-P11 | immutable artifacts, deployed-path streaming, migration/rollback, security/load/backup/restore and runbooks pass |

## Detailed task register

### P0 - Contract and repository spine

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P0-01 | DONE | - | inventory the lifted tree; choose and enforce one canonical package/migration/container/script layout while preserving valid lockfiles |
| P0-02 | DONE | P0-01 | adopt vocabulary, authority precedence, coding-agent rules and stop conditions |
| P0-03 | DONE | P0-02 | define canonical error envelope, ID/time conventions and API `/api/v1` policy |
| P0-04 | DONE | P0-03 | define data ownership, privacy classification, adapter ports and state-machine conventions |
| P0-05 | DONE | P0-01 | CI for lint, typecheck, tests, OpenAPI snapshots, frontend build and Docker integration |
| P0-06 | DONE | P0-03 | generate OpenAPI/JSON Schema and typed client from the HTTP, DTO and evidence catalogs |
| P0-07 | DONE | P0-01,P0-04 | inventory and transitively remove Phase 2/3 runtime, build, registration, persistence and test seams; preserve positive operational-safety behavior |

Post-D0 evidence is explicit: P0-04 is proven by `docs/_scratch/p0-04-foundation-conventions.md` and the documentation gate: authoritative ownership, four privacy classes/sinks, nine outbound ports, and seven transition rules are pinned while lifted protocols/state assignments remain evidence only for P1/P3-P8. P0-03 is proven by `docs/_scratch/p0-03-api-conventions.md`: production and generation share one non-configurable `/api/v1` registrar, request IDs use the canonical server-owned header and error correlation, the closed error union is generated, and naive/aware timestamps normalize to RFC 3339 UTC. Feature error adoption, cache policy, ETags, idempotency, and race behavior remain with P0-06/P1/P3-P7. P0-02 is adversarially enforced by `scripts/check-doc-phase-scope.sh` and its fixture suite, which pin mirrored authority precedence, canonical product vocabulary, the Workspace prohibition, coding-agent read/dependency/evidence rules, and all six explicit-decision stop conditions. `docs/_scratch/p0-01-layout-inventory.md` proves the bounded P0-01 layout task and records the partial P0-03 error-envelope slice plus P0-05’s historical red baseline and subsequent green local-loop checkpoint. `docs/_scratch/p0-06-generated-contract-inventory.md` records the proof-first OpenAPI/TypeScript reproducibility gate that completes P0-05’s bounded CI deliverable while leaving catalog parity, broad generated-client adoption, and canonical SSE migration open under P0-06/P7/P9. `docs/_scratch/p0-07-deferred-surface-inventory.md` records the historical baseline and completed active-tree closure; `app/tests/test_phase_one_production_scope.py` pins the physical route tree, source/build manifests, generated OpenAPI and compiled-module boundary; `app/tests/test_phase_one_route_scope.py` proves public-registration removal and retains health/readiness assertions. `app/tests/test_phase_one_observability_scope.py` proves the audit/diagnostic read service, read-event vocabulary, and diagnostic-only metadata keys are absent while private transactional audit recording remains functional. `app/tests/test_composer_refs_phase_one.py` proves that composer discovery defaults and explicit kinds are limited to source/evidence/template, generic unsupported tokens/refs fail closed and add no prompt content, and filtered/unfiltered query limits preserve the intended boundary. `app/tests/test_phase_one_schema_scope.py` now proves the active package, ORM metadata, accepted-ref columns, constraints, and audit vocabulary contain no Wiki implementation. The lifted Alembic history is missing, so fresh-install and populated-compatibility migration proof remain blocked under P12-01; active ORM cleanup is not represented as a destructive upgrade. `scripts/check-doc-phase-scope.sh` plus `scripts/tests/check-doc-phase-scope.sh` provide the live and adversarial documentation gates. `scripts/generate_openapi.py`, `app/contracts/openapi.json`, and `app/client/src/lib/api/generated/openapi.ts` start P0-06. The root gate now regenerates and byte-compares OpenAPI and TypeScript, adversarial fixtures reject stale artifacts, production and generation share route registration, health success/readiness-failure responses use closed generated components and approved status/error values, and all current browser JSON request bodies backed by generated components are pinned through their capability adapters. Closed shared identity, configuration, domain, operation, source, document, conversation, turn, composer-ref, Evidence, and anchor response DTOs are generated without placeholder routes. Registered path templates/parameters use exact authoritative camelCase names and matched operations are compared directly with the catalog. All 39 registered operations are cataloged; the zero-extra/seven-missing semantic route delta is characterization-gated, and all registered responses are assigned to their vertical adoption owner. The four uncataloged lifted shortcuts and their browser/test seams were removed transitively, with read-only or deliberate unavailable states retained until the owning opaque routes land. Most registered operations have not adopted the authoritative response components and all canonical SSE schemas remain ungenerated/unadopted, so P0-06 stays in progress. Missing identity, document/evidence, resume/cancel, and canonical-stream behavior remains dependency-owned by P1/P4/P6/P7/P9 rather than being scaffolded in P0; final route/response convergence is a cross-phase contract gate.

P0-06 closure evidence (2026-07-24): deterministic generation now emits and byte-compares the registered HTTP OpenAPI snapshot, standalone Draft 2020-12 public-DTO JSON Schema, standalone versioned canonical SSE JSON Schema, an SSE-only OpenAPI generation view, and generated HTTP/SSE TypeScript artifacts. Replay and cancel routes are registered and cataloged; committed raw SSE transcripts validate against the production discriminated union; the chat adapter consumes the generated SSE union; live and adversarial stale-artifact gates cover all six artifacts. Focused closure evidence is 19 generated-contract/schema tests, live snapshot comparison, independent stale-artifact fixtures, and frontend typecheck. Four governed document/evidence routes and route-specific authoritative response adoption remain with P4/P6/P7/P9 and are not P0 implementation prerequisites.

### P1-P2 - Identity and trusted configuration

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P1-01 | DONE | P0 | FastAPI app factory, settings, PostgreSQL engine/session and Alembic baseline |
| P1-02 | DONE | P1-01 | users/auth_sessions schema, Argon2, admin seed and opaque cookie sessions |
| P1-03 | DONE | P1-02 | current-user/admin dependencies, ownership helpers and denial audit hook |
| P1-04 | DONE | P1-01 | request IDs, safe errors/logging, live/ready endpoints |
| P1-05 | DONE | P1-02,P1-03 | Origin/Host and CSRF policy, session rotation/revocation/TTL, login throttling and ingress auth tests; security persistence/config contract approved 2026-07-24 |
| P1-06 | DONE | P1-01 | append-only audit schema, transactional AuditService and protected-mutation helper |
| P2-01 | DONE | P1 | provider_configs, model_profiles, runtime_settings migrations and services |
| P2-02 | DONE | P2-01 | credential encryption/rotation and safe DTO projection |
| P2-03 | DONE | P2-01 | synthesis/embedding validation, immutable dimension rules and defaults |

P2-03 closure evidence (2026-07-24): `docs/_scratch/p2-03-embedding-validation-inventory.md` records retain/modify decisions. Service validation rejects non-positive embedding dimensions before catalog checks; domain-referenced embeddings are immutable under PATCH/DELETE via ORM reference detection; defaults reject embedding-as-synthesis; embedding resolve fails closed for synthesis/unready providers. PostgreSQL 16 proof covers domain-referenced A-02 denial, unused-profile create/rename, DB zero-dimension check, and HTTP admin PATCH `409 model_profile_in_use` plus create `201`. Results were 37 focused runtime-config/foundation/audit/schema/health tests passing. `docs/_scratch/p2-03-embedding-validation-evidence.md` records commands and keeps domain embedding replacement with P3, Settings UI with P9, and HTTP ErrorCode catalog closure as a residual.

P2-02 closure evidence (2026-07-24): `docs/_scratch/p2-02-credential-dto-inventory.md` records retain/modify/add decisions. Alembic head `b7e2a91c04d8` adds positive `version` columns on the three runtime-config tables. PostgreSQL 16 proof covers Fernet encrypt-at-rest rotate, closed `ProviderSummaryDto`/`ModelProfileDto`/`RuntimeSettingsDto` snapshots, sequential and concurrent `stale_revision` losers, and HTTP A-01 `428`/`409`/`200` with strong `ETag`. Unit proofs cover closed projection, wrong-key decrypt fail-closed, `If-Match` parse, and stale rotate rejection. Results were 35 focused runtime-config/foundation/audit/schema/health/DTO tests passing; generated contract snapshots pass. `docs/_scratch/p2-02-credential-dto-evidence.md` records commands and keeps immutable embedding completion with P2-03 and Settings UI DTO/`If-Match` adoption with P9.

P2-01 closure evidence (2026-07-24): `docs/_scratch/p2-01-runtime-config-inventory.md` records retain/modify/defer decisions. PostgreSQL 16 proof covers schema checks for the three tables, insert-only catalog seed that preserves credentials, protected-mutation profile create and defaults update, default-profile delete denial, synthesis/Reducto readiness gates, and snapshot absence of secrets. Unit proofs cover default delete, audit rollback on create, and unready-provider rejection. Results were 27 focused runtime-config/foundation/audit/schema/health tests passing. `docs/_scratch/p2-01-runtime-config-evidence.md` records commands and keeps DTO/ETag/encryption with P2-02 and immutable embedding completion with P2-03.

P1-01 closure evidence (2026-07-24): `docs/_scratch/p1-01-foundation-inventory.md` records retain/modify/add decisions before implementation. `app/tests/test_postgres_foundation.py` then proved, against an ephemeral PostgreSQL 16 server, empty-database Alembic upgrade to the single head `d07141ac7d95`, app-factory construction without schema mutation, canonical engine/session behavior, successful metadata drift checks, baseline-to-head retained data, incremental downgrade, and clean re-upgrade. The focused result was 2 passed. `docs/_scratch/p1-01-foundation-evidence.md` records the command, safety controls, and rollback/restore boundary. Unknown populated legacy compatibility remains blocked under P12-01.

P1-02 closure evidence (2026-07-24): `docs/_scratch/p1-02-auth-session-inventory.md` records the dependency boundary and retain/modify decisions. PostgreSQL 16 proof now covers Argon2 salting/verification, hash-only opaque sessions, generic credential denial, insert-only restart-safe administrator bootstrap, no bootstrap side effect in API lifespan, explicit bootstrap command behavior, atomic presented-session replacement, independent sessions, revocation, user-session cascade, exact login JSON, and cookie attributes. Results were 5 PostgreSQL tests and 26 focused identity/generated-contract tests passing. `docs/_scratch/p1-02-auth-session-evidence.md` records red baselines, commands, safety decisions, and the P1-03/P1-05/P10 boundaries.

P1-03 closure evidence (2026-07-24): `docs/_scratch/p1-03-authorization-inventory.md` records retain/modify decisions and dependency boundaries. PostgreSQL 16 HTTP proof covers authoritative `/auth/me`, disabled-user and downgraded-admin next-request enforcement, member/admin non-ownership, indistinguishable cross-owner and unknown conversation responses, safe correlated denial audits, and owner success. A static assertion pins `require_admin` on every active `/admin/*` route. Results were 8 PostgreSQL/static tests and 26 focused identity/generated-contract tests passing. `docs/_scratch/p1-03-authorization-evidence.md` records the red baseline, commands, and remaining P1-05/P1-06/P7 boundaries.

P1-04 closure evidence (2026-07-24): `docs/_scratch/p1-04-health-readiness-inventory.md` records retained P0 request/error behavior and the bounded P1-04 readiness scope. PostgreSQL 16 proof now covers database connectivity, exact Alembic head, enabled-administrator bootstrap viability, safe correlated/no-store `503`, and process-only liveness. Structured logging tests prove unsafe keyword fields are dropped and unclassified raw messages cannot become JSON events. Results were 12 focused logging/health/error/request-ID tests, 9 PostgreSQL tests, and 26 identity/generated-contract tests passing. `docs/_scratch/p1-04-health-readiness-evidence.md` records red baselines and keeps governed object-storage readiness with P4/P10-02, browser cache isolation with P9-05, and broad sink privacy with P8.

P1-05 closure evidence (2026-07-24): `docs/_scratch/p1-05-ingress-session-inventory.md` records the approved schema/security/deployment contract boundary. PostgreSQL 16 HTTP proof covers untrusted-peer denial, signed CSRF bootstrap, hostile Origin rejection, login session+CSRF rotation, authenticated logout `204`, durable login throttle `429` with `Retry-After`, idle touch cadence, and idle expiry. Unit tests cover CSRF binding and Origin/CSRF enforcement. Results were 5 focused ingress/security tests and 40 focused P1 regression tests passing; generated contract snapshots pass. `docs/_scratch/p1-05-ingress-session-evidence.md` records commands and keeps deployed topology/BFF stripping with P9-05/P10, stream checkpoints with P7, and broad privacy with P8.

P1-06 closure evidence (2026-07-24): `docs/_scratch/p1-06-audit-inventory.md` records retain/modify/add decisions for append-only enforcement and the protected-mutation helper. PostgreSQL 16 proof covers Alembic head `c4e8f1a02b93` triggers, atomic `commit_protected_mutation` success for `user.disabled`, ORM/raw UPDATE/DELETE rejection, and product-row rollback when the required audit event is rejected. Unit proofs cover allowlist rejection and helper commit/rollback. Results were 22 focused audit/foundation/observability/schema tests passing. `docs/_scratch/p1-06-audit-evidence.md` records commands and keeps broad call-site allowlist coverage and privacy scans with P8-01.

### P3-P6 - Domain, content, indexing, retrieval

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P3-01 | DONE | P2 | domains/domain_operations schema and admin APIs |
| P3-02 | DONE | P3-01 | runtime controller port plus local/Docker implementations |
| P3-03 | DONE | P3-02 | lease, generation, conflict, readiness and async delete behavior |

P3-03 closure evidence (2026-07-25): `docs/_scratch/p3-03-domain-leases-inventory.md` records retain/modify/defer decisions. Start/stop keep sync completion with lifecycle leases and generation-fenced state updates; delete supersedes active start/stop; `DomainDeleteWorker` heartbeats leases, reclaims expired/uncertain deletes, and cancels stale-generation completions; uncertain start/stop reconcile via health probe. PostgreSQL 16 proof covers A-03 stale no-op, A-04 stop fence, A-05 supersede, A-10 worker delete, lease reclaim, and stale delete cancel. Results were 11 focused lease/domain/controller tests passing. `docs/_scratch/p3-03-domain-leases-evidence.md` records commands and keeps mid-turn chat A-04 with P7 and index DRIFT-32 with P5-03. DRIFT-12 race half closed.

P3-02 closure evidence (2026-07-25): `docs/_scratch/p3-02-runtime-controller-inventory.md` records the extract into `adapters/domain_runtime_controller.py`. Local/Docker adapters require stable `operation_key`/`control_generation`, return typed `succeeded`/`failed`/`uncertain` results, and map Docker timeouts to `uncertain`. Unit proofs cover local lifecycle records, Docker payload keys, timeout→uncertain, and hard failure; P3-01 PostgreSQL domains suite remains green with `kind=local`. `docs/_scratch/p3-02-runtime-controller-evidence.md` records commands and keeps lease/reconciliation races with P3-03.

P3-01 closure evidence (2026-07-25): `docs/_scratch/p3-01-domains-admin-inventory.md` records retain/modify/replace/add decisions. Alembic head `e3a1c8d04f21` adds positive `version` on `domains`/`domain_operations`. Closed `AdminDomainDto`/`OperationDto`/`DomainSummaryDto` projections replace lifted `available`/`storageSummary` shapes. DRIFT-12 projection half: start/stop return `202 {operation}`; GET detail `ETag`; DELETE `If-Match` `428`/`409 stale_revision`. PostgreSQL 16 proof covers A-03 create→stopped→start generation bump, start conflict, member `queryEligible`, and HTTP `201`/`202` closed envelopes. Results were 54 focused domain/runtime-config/foundation/audit/schema/health/DTO/contract tests passing; generated OpenAPI/TypeScript regenerated. `docs/_scratch/p3-01-domains-admin-evidence.md` records commands and keeps controller port with P3-02, lease/authoritative-refresh races with P3-03, and Settings UI adoption with P9-04.

P4-01 closure evidence (2026-07-25): `docs/_scratch/p4-01-source-storage-inventory.md` records retain/modify/replace/add decisions. Alembic head `f4b2c9e18a70` adds source/prep `version` and private `original_object_key`. Closed `AdminSourceDto` projection emits `documentRef` and maps internal index states to public `IndexState`. Governed object-store port plus filesystem adapter prove put/get/range/delete, opaque keys, and path-escape rejection. PostgreSQL 16 proof covers schema constraints, upload→object write, projection leak absence, domain-hash and one-active-prep uniqueness. Results were 7 focused source/storage tests and 13 foundation/domains/health regressions passing. `docs/_scratch/p4-01-source-storage-evidence.md` records commands and keeps upload sniff (P4-02), parsers (P4-03), outline/delete APIs (P4-04), and member document routes (P6/P9).

P4-02 closure evidence (2026-07-25): `docs/_scratch/p4-02-upload-validation-inventory.md` records replace/modify decisions for DRIFT-13. Chunked `UploadFile` ingest replaces `request.body()` buffering; magic/structure sniff ignores declared MIME; DOCX uncompressed/ratio bombs and oversize emit `content_rejected` with zero partial rows; domain hash collisions emit `duplicate_source`; retry keeps upload-frozen `parser_kind` after runtime parser change. Results were 12 unit + 7 PostgreSQL/source-upload tests passing. `docs/_scratch/p4-02-upload-validation-evidence.md` records commands and keeps real parsers with P4-03 and outline/delete APIs with P4-04.

P4-03 closure evidence (2026-07-25): `docs/_scratch/p4-03-parser-adapters-inventory.md` records replace/modify/add decisions for DRIFT-22 parser half and DRIFT-30. `DocumentParser` port plus Docling/Reducto adapters fail closed with typed timeout/auth/malformed errors; normalizer fixtures prove privacy (no job/URL leakage). Alembic head `a8d3f1c62e90` adds `source_images.object_key`; publish atomically replaces blocks/images via the object-store port under lease-owner/expiry/generation fences with prep heartbeat. Results were 18 focused unit tests and 2 PostgreSQL prep/source schema tests passing. `docs/_scratch/p4-03-parser-adapters-evidence.md` records commands and keeps outline/delete APIs with P4-04 and synthesis stand-ins with P7-03.

P4-04 closure evidence (2026-07-25): `docs/_scratch/p4-04-source-outline-delete-inventory.md` records replace/modify decisions for DRIFT-29 and closed outline/`OperationDto` envelopes. Alembic head `b5c8e2d19f47` allows `prepare|delete` source ops and delete audit events. Outline omits canonical text; cancel requires `If-Match`; delete returns `202 {operation}` after fence/redact/token-expiry/audit intent; `SourceDeleteWorker` performs leased object/index cleanup. Results were 5 unit + 3 PostgreSQL source API/schema/prep tests passing; OpenAPI/TypeScript regenerated. `docs/_scratch/p4-04-source-outline-delete-evidence.md` records commands and keeps Idempotency-Key transport, index envelopes (P5), member routes (P6/P9), and Settings/documents UI If-Match (P9).

P5-01 closure evidence (2026-07-25): `docs/_scratch/p5-01-index-state-claim-inventory.md` records retain/modify/defer decisions. Internal index CHECK vocabulary retained; public mapping stays with P4-01. `SourceIndexWorker._claim_next_source` assigns lease owner/expiry on queued→submitting, expired submitting reclaim, and accepted readiness when lease absent/expired; unexpired leases are not double-claimed. PostgreSQL 16 proof covers schema columns/CHECKs/`ix_source_documents_domain_index_state`, claim/reclaim, accepted lease skip/reclaim, and generation/request fence no-ops. Results were 1 focused PostgreSQL index-claim test passing. `docs/_scratch/p5-01-index-state-claim-evidence.md` records commands and keeps renderer/adapter with P5-02 and submit/poll/eligibility with P5-03.

P5-02 closure evidence (2026-07-25): `docs/_scratch/p5-02-lightrag-renderer-adapter-inventory.md` records retain/modify/defer decisions. `LIGHTRAG_HANDOFF_SCHEMA_VERSION=1` and `render_blocks_to_lightrag_handoff` pin CE_SOURCE/CE_BLOCK provenance markers and content-hash identity. Local LightRAG adapter fixtures prove idempotent submit, hash conflict, readiness, delete/absence, and preserved block IDs. Native `_run` bounds lifecycle work with `CE_SOURCE_INDEX_TIMEOUT_SECONDS` and maps overrun to `504 source_index_timeout` (DRIFT-27 timeout half). Results were 4 focused renderer/adapter unit tests passing. `docs/_scratch/p5-02-lightrag-renderer-adapter-evidence.md` records commands and keeps index HTTP/eligibility with P5-03.

P5-03 closure evidence (2026-07-25): `docs/_scratch/p5-03-index-eligibility-inventory.md` records retain/modify/defer decisions. Closed index retry/cancel `AdminSourceDto` envelopes map service codes to approved ErrorCodes. Worker heartbeats leases; timeout leaves `submitting` uncertain then readiness-probes before re-submit (DRIFT-32); not-ready accepted polls use lease-expiry backoff (DRIFT-28). `source_is_query_eligible` requires domain available + prepared + ready + current request identity. PostgreSQL 16 proof covers submit→ready→eligible, backoff skip, HTTP `202`/`409`/`200`, and cancel non-eligibility. Results were 6 unit + 1 PostgreSQL index-eligibility tests passing; OpenAPI/TypeScript regenerated. `docs/_scratch/p5-03-index-eligibility-evidence.md` records commands and keeps native process-lock concurrency, Idempotency-Key store, and member routes with later owners.
| P4-01 | DONE | P3 | source_documents/preparation_operations schema, opaque public document refs and secure storage adapter |
| P4-02 | DONE | P4-01 | upload validation, domain deduplication and parser-kind freeze |
| P4-03 | DONE | P4-02 | Docling/Reducto adapters and canonical blocks/images transaction |
| P4-04 | DONE | P4-03 | outline, operation, retry/cancel and delete APIs |
| P5-01 | DONE | P4 | index state/generation fields and worker claim loop |
| P5-02 | DONE | P5-01 | versioned canonical-block renderer and vendored LightRAG adapter |
| P5-03 | DONE | P5-02 | submit/poll/retry/cancel/delete and query-eligibility service |
| P6-01 | DONE | P5 | scoped retrieval port and raw-hit provenance mapper |
| P6-02 | DONE | P6-01 | approved stateless Evidence projection/ref/anchor/error contract plus authorized safe DTO, ordering, excerpt limits and failure mapping |

P6-01 closure evidence (2026-07-25): `docs/_scratch/p6-01-scoped-retrieval-inventory.md`
records the retain/modify/defer boundary. Index lifecycle and scoped retrieval
now use separate private protocols with bounded admission, one deadline,
candidate count, and UTF-8 byte budgets. The schema-v2 LightRAG handoff keeps a
document `CE_SOURCE` header and gives every block a self-contained exact
provenance marker. Retrieval freezes domain/source generations and index
identities before provider work; one joined post-call query maps only current
selected-domain canonical blocks. Barrier-driven PostgreSQL 16 proof covers
stop/restart, reindex/new-ready, delete, and preparation-replacement fences.
Results were 35 focused/regression tests plus the exact Ruff, generated-contract,
and 64-file phase-scope gates passing.
`docs/_scratch/p6-01-scoped-retrieval-evidence.md` records commands, privacy,
schema-v2 reindex rollout, and keeps public Evidence projection with P6-02.

P6-02 closure evidence (2026-07-26):
`docs/_scratch/p6-02-evidence-inventory.md` records the retain/modify/replace/add
boundary. The approved stateless DTO remains ID-free, trims before bounds,
uses a closed page/section-only nullable anchor, and rejects result/Evidence
contradictions. The member/admin route validates the final projection, maps
safe failures, and remains private no-store and request-time read-only.
PostgreSQL 16 barrier proof passed all five lifecycle/concurrency cases; 50
focused tests (including 12 HTTP contract cases), 14 retrieval/indexing
regressions, 194 broad backend tests, full-package Ruff, generated-contract
snapshots, and the 65-file phase-scope gate passed.
`docs/_scratch/p6-02-evidence.md` records exact commands, privacy/no-mutation
coverage, rollback, and keeps durable Evidence/replay/redaction with P7,
system-wide cross-sink privacy with P8, and browser navigation with P9.

### P7-P8 - Chat and operational safety

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P7-01 | DONE | P6 | conversations, turns and opaque public evidence-ref migrations plus owner CRUD |
| P7-02 | DONE | P7-01 | server intent gate and direct/domain route invariants |
| P7-03 | DONE | P7-02 | bounded plan/retrieve/repair/synthesize orchestration |
| P7-04 | DONE | P7-03 | sealed versioned SSE live/resume/replay pipeline, terminal persistence, idempotent attach/replay, and grounded-refusal/evidence-only terminal projections |
| P7-05 | DONE | P7-04 | source/domain delete redaction hooks and public omission tests |
| P8-01 | DONE | P1-06,P7 | transactional audit-write allowlist coverage, denial events and privacy/adversarial audit tests |
| P8-02 | DONE | P8-01 | safe JSON logs, request/trace correlation and bounded-cardinality service metrics |
| P8-03 | DONE | P8-02 | liveness/readiness, privacy scans and resilience/load evidence with no observability read API or UI |

P8-03 closure evidence (2026-07-27):
`docs/_scratch/p8-03-operational-safety-inventory.md` freezes health
live/ready surfaces, the four-sink privacy union, resilience cite matrix,
`DisabledTracingPort` retain-absence, and as-built bootstrap semantics
(any enabled administrator; configured-username residual). Health re-proof
extends live-under-failure, schema-edge safe `503`, and ready with stopped
domain plus unready provider. `test_cross_sink_privacy_scan.py` plants once
across audit + JSON logs + metrics + health. Focused resilience executes
`413 content_rejected`, login-throttle `429`+Retry-After, capacity `503`,
and domain/index/turn lease reclaim (PostgreSQL 16). Results: focused unit
suite green + opted-in PostgreSQL throttle/lease/readiness green. `docs/_scratch/p8-03-operational-safety-evidence.md` records
commands and residuals (P10-02 object-store ready / DRIFT-15, concurrent-stream
429, SIGTERM/stream-drain / P12, Phase 2 read). DRIFT-20 / DRIFT-29
cross-sink/health halves closed; P8 phase exit complete.

P8-02 closure evidence (2026-07-27):
`docs/_scratch/p8-02-telemetry-inventory.md` freezes every production
`safe_log` disposition and the closed metric name/label catalog (option b:
chat terminals join via `trace_id`; optional `request_id` when available —
no turn-row schema migration). Process-local `metrics.py` rejects
identity-bearing label keys/values; HTTP/chat/worker emitters land beside
existing allowlisted logs; `DisabledTracingPort` stays disabled. Adversarial
privacy scans cover formatted JSON logs and metric dumps. Results were 15
focused unit tests passing; observability-scope / no-scrape absence remains
green. `docs/_scratch/p8-02-telemetry-evidence.md` records commands and
residuals (P8-03 health/cross-sink, Phase 2 read, P12 ingress). DRIFT-20 /
DRIFT-29 log/metric halves advanced; cross-sink/health stay P8-03.

P8-01 closure evidence (2026-07-27):
`docs/_scratch/p8-01-audit-inventory.md` dispositions every closed audit
event and production writer (`migrate` / `protected-helper` / exemption
classes including `open-txn-object-put`, `worker-terminal`,
`nested-redaction-flush`, `external-call-split`, `orphan-reserved`).
Migrated prep retry/cancel and index retry/cancel terminals onto
`commit_protected_mutation` with IntegrityError→409 preserved on prep
retry. `require_admin` hardens denial-audit failure to
`503 audit_unavailable` (KTD8); denial rows stay role-safe without
resource `target_id`. Adversarial privacy scans cover `audit_events`
only. Results were 15 focused unit tests passing; observability-scope
absence remains green. `docs/_scratch/p8-01-audit-evidence.md` records
commands and residuals (P8-02 logs/metrics, P8-03 cross-sink/health,
Phase 2 audit-read, P12 ingress). DRIFT-20 / DRIFT-29 audit-write halves
advanced; log/metric/cross-sink residuals stay P8-02/P8-03.

P7-05 closure evidence (2026-07-27):
`docs/_scratch/p7-05-delete-redaction-inventory.md` records retain/modify/defer
for redaction helpers, source/domain delete enqueue, token expiry, and
public-omission surfaces. `redact_turns_for_domain` gains `commit=` and a
dependent-turn union; `enqueue_delete_domain` redacts and expires source- and
evidence-kind composer tokens in the fence transaction; late turn finalize
cannot un-redact. Public omission is proven for DTO, sanitized ledger,
`turn.redacted`, and redacted `terminalSnapshot`. Results were 7 focused
unit/service tests and 1 PostgreSQL 16 barrier test passing.
`docs/_scratch/p7-05-delete-redaction-evidence.md` records commands and keeps
P8 privacy/audit breadth, P9 UI/reducer, P9-03 location/content routes (M-11
open-panel half), P11 composer depth, and P12-03 adversarial deletion as
residuals. DRIFT-29 chat-redaction half is closed; full DRIFT-29 remains
P8-01 for audit/privacy breadth. P7 phase exit is complete for Phase 1 chat
backend tasks P7-01–P7-05.

P7-04 closure evidence (2026-07-27):
`docs/_scratch/p7-04-sse-pipeline-inventory.md` records retain/modify/defer for
the request-coupled stream producer, event ledger, cancel path, resume
projector, and worker registry. Turn leases land in migration `e9f2a1b83c70`
(supported Alembic head). HTTP only tails the durable ledger;
`ConversationTurnWorker` owns retrieval/synthesis; cooperative cancel fences
outbound work; terminal attach/GET emit `replay:true`; unreconstructable
cursors return `410 cursor_expired` + authorized `terminalSnapshot`.
`docs/_scratch/p7-04-sse-pipeline-evidence.md` records focused verification,
opt-in PostgreSQL race tests, producer fixtures, and residuals (P7-05
redaction; P8 privacy breadth; P9/DRIFT-03/06 reducer consumer; P12 ingress
drain). DRIFT-23 and DRIFT-25 are closed; DRIFT-24 producer half is closed with
P9-02 residual for parser/reducer.

P7-03 closure evidence (2026-07-27):
`docs/_scratch/p7-03-orchestration-inventory.md` records retain/modify/defer for
`TurnOrchestrator`, the synthesis stand-in, `P6RetrievalPort`, event emission vs
P7-04/P7-05, and the single-shot / `evidence_only` sequencing constraints. The
deterministic synthesis stand-in is replaced by a typed OpenAI adapter plus
fail-closed registry (`adapters/synthesis.py`) with no-network fixtures.
Domain RAG synthesizes only from mapped Evidence or completes
`no_grounded_context`; post-answer provider failure uses safe `turn.failed`
rather than `evidence_only`; budgets remain `domain 1/1/0` and `direct 0/0/0`.
Results were 29 focused orchestration/adapter/SSE/turn-route HTTP tests and
changed-file Ruff passing. OpenAPI/generated TS were untouched (Windows CRLF
vs LF check residual only). `docs/_scratch/p7-03-orchestration-evidence.md`
records commands, privacy assertions, and keeps sealed SSE with P7-04,
redaction with P7-05, system-wide privacy with P8, chat UI with P9, and
Bedrock/Ollama synthesis adapters as fail-closed residuals. DRIFT-22 synthesis
half is closed.

P7-02 closure evidence (2026-07-27):
`docs/_scratch/p7-02-intent-route-inventory.md` records retain/modify/defer for
the pattern classifier, `classify_turn_route` / `start_or_replay_turn` authority,
passthrough `_chat_turn_api_error`, non-authoritative `claim_turn`, and the
empty-corpus eligibility exit criterion. Optional `domainId` now validates
against `DOMAIN_ID_PATTERN`; turn-start failures project only approved
ErrorCodes with Evidence-parity messages; selected ineligible domains never
rewrite to `direct_llm`. Results were 30 focused intent/route/HTTP tests plus
SSE compatibility, generated-contract, and phase-scope gates (46 total in the
closure command) and changed-file Ruff passing.
`docs/_scratch/p7-02-intent-route-evidence.md` records commands, privacy
assertions, and keeps orchestration with P7-03, SSE/replay with P7-04,
redaction with P7-05, system-wide privacy with P8, and draft UX with P9.

P9-02 closure evidence (2026-07-27):
`docs/_scratch/p9-02-chat-workbench-inventory.md` and
`docs/_scratch/p9-02-chat-workbench-evidence.md` record generated chat DTO
adoption, `src/lib/stream` live/resume/replay reduction over all nine producer
SSE fixtures plus `410` replace helpers, gated composer-ref discovery, and the
Evidence/Refs/Source workbench with opaque Library deep-link construction kept
disabled until P9-03. Results were 39 node stream/chat tests, clean typecheck,
and 7 Vitest inspector/deep-link tests. Residuals remain P11 discover/`token`,
P9-03 preview, P9-05 CI validators, and P12 ingress/visual matrix. Phase P9
stays open until P9-03–P9-05 land.

### P9-P11 - User interface, deployable runtime, and governed context workflows

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P9-01 | DONE | P1,P8 | inventory every `components/**` and `_shared/ui/**` file/call site in `docs/_scratch/p9-01-ui-inventory.md`; disposition Button/Input/StatusPill to canonical `src/ui`, SettingsRow to Settings, and shell composition to `src/features/shell`; define `app/client/tests/structure/ui-ownership.test.ts`, `app/client/tests/parity/manifests/<target>.json`, `app/client/tests/parity/fixtures/<target>.html`, `app/client/tests/parity/react/<target>.test.tsx`, and `app/client/tests/e2e/`; migrate without a competing physical kit — evidence `docs/_scratch/p9-01-ui-ownership-evidence.md`; accordion + live Settings domains remain P9-04/P12-07 |
| P9-02 | DONE | P7 | generated HTTP/SSE client plus `/chat` conversation discovery, transcript/composer, turn-scoped Evidence/Refs/Source workbench, and canonical live/resume/replay reducer states — evidence `docs/_scratch/p9-02-chat-workbench-evidence.md`; P11 discover/`token` residual, P9-03 Library preview, and P12 ingress remain |
| P9-03 | NOT_STARTED | P4-P6 | documents/outline/preview and graph route through approved contracts |
| P9-04 | BLOCKED | P2-P3,P8,P9-01 | approve the Settings Domain accordion interaction amendment across behavior/component/state/accessibility contracts, then implement `/settings?section=domains`; no deferred operator or publication UI |
| P9-05 | NOT_STARTED | P9-01 | import-direction, thin-route, server/browser boundary and contract/barrel CI validators |
| P10-01 | NOT_STARTED | P8,P9 | Compose services and production-like server configuration for PostgreSQL, migration, API, worker and frontend |
| P10-02 | NOT_STARTED | P10-01 | explicit migration/bootstrap plus BFF/API/SSE core-path smoke stack |
| P10-03 | NOT_STARTED | P10-02 | startup/shutdown, worker claim recovery and deployment operator runbook |
| P11-01 | NOT_STARTED | P6 | prompt_templates/composer_ref_tokens/accepted-ref schema and seeds for source/evidence/template refs |
| P11-02 | NOT_STARTED | P11-01 | discovery, opaque-token validation, domain compatibility and expiry |
| P11-03 | NOT_STARTED | P11-02,P7 | private context assembly, turn fingerprint, replay/conflict and redaction |
| P11-04 | BLOCKED | P7-04,P9-02,P11-03 | require product-owner evidence of repeated Evidence reattachment need, comprehension of explicit accept/dismiss behavior, and no pressure to weaken the sealed-chat baseline; only after approval, amend HTTP, DTO, interaction-state, component, and accessibility contracts and implement compose-epoch, focus, touch, announcement, recovery, narrow-layout, and cross-tab rules |

### P12 - Production release and recovery

| Task | Status | Depends on | Deliverable |
| --- | --- | --- | --- |
| P12-01 | BLOCKED | P0-P11 | fresh-install proof plus the approved populated-compatibility path from `architecture/legacy-persistence-retirement.md` against PostgreSQL 16 |
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

## Documentation and application gates

- **D0 — documentation authority:** the phase manifest, root guidance, PRD/contracts/schema, architecture/frontend/quality docs, all three plans, complete DRIFT-01..33 register, and deterministic phase checker agree. D0 authorizes application planning only and never marks P0-P12 complete.
- **B0 — brownfield repository boundary:** canonical package/migration/container/script paths build; the root verification loop runs; Phase 2/3 code is absent from Phase 1 registration, routes, generated contracts, schema target, navigation and production bundle; transactional audit writes, allowlisted logs, correlation, health/readiness, bounded metrics, privacy checks and runbooks still have positive tests.
- Later B-gates are package exit gates in the phase tracker. Existing code earns credit only after the matching real-boundary proof is attached.

## Populated-database compatibility barrier

The Phase 1 schema is a clean-install target, not authority for destructive contraction. Before P12-01 can leave `BLOCKED`, the release must choose one path:

1. **Unsupported populated legacy upgrade:** a read-only migration preflight reconciles `pg_catalog`, `information_schema`, Alembic current/history, ORM metadata, and every application-owned table, column, enum, sequence, index, constraint, trigger, function, view, and dependency against a versioned system-schema and approved-extension allowlist. It accepts only an empty database or the exact current target catalog/Alembic head and refuses legacy, partial, renamed, unknown-object, unknown-history, behind, and ahead states before migration writes. Startup separately accepts the exact current target catalog/head with valid populated Phase 1 data and refuses behind, ahead, or unknown state before product writes. Fixtures prove empty-install and populated-current-target success plus every named refusal.
2. **Supported populated upgrade:** reconcile live catalogs, full migration history, ORM metadata, and the documented closure across every table, column, enum, sequence, index, constraint, trigger, function, view, and dependency; block on anything unaccounted for; fence writes/claims; drain work; census and take a transactionally consistent protected backup/export; disposition every dependent object; quarantine rollback-compatibly; rehearse prior-version rollback and isolated restore; prove per-object counts, stable checksums, FK/orphan/constraint integrity, audit count/hash continuity, and affected-conversation replay/read behavior before later contraction.

Both paths require secret-safe operator errors; a declared backup scope and consistency point; an approved KMS/key-management source; separate artifact/key custody; least-privileged audited backup/restore roles; key rotation and revocation across retention; retention/deletion rules; verified cleanup of temporary export/restore material; exact PostgreSQL and application restore versions; an owned rollback decision and go/no-go cutoff; and proof that required keys remain recoverable. Any unknown object/history, unaccounted dependency, missing key, or failed restore keeps migration blocked.

## Frontend-factory evidence staging

D0 creates only `DESIGN.md`, `frontend/AGENTS.md`, and parity/catalog rules. P9-01 owns the four unblocked starter targets and migration enforcement. The Settings Domain accordion remains `BLOCKED_CONTRACT` until P9-04 approval. Script-free synthetic HTML may prove static appearance only; React owns semantics/focus/accessibility. P12 browser acceptance for `/settings?section=domains` must use the production Next build, same-origin BFF and FastAPI with server-produced DTOs, without intercepted or mocked product responses.

The sole member-chat capability list is `docs/prd.md#closed-phase-1-chat-capability-manifest`. P7/P9/P11 tasks and tests link to it and do not redefine it. Evidence suggestions cannot block sealed SSE, grounded-terminal, and Evidence/Refs/Source workbench acceptance.

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
