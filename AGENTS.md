# Context Engine — Agent Guidance

This repository reconstructs Context Engine, an internal shared-workspace retrieval-augmented generation (RAG) product. Administrators curate isolated Knowledge Domains and their source corpora; authenticated members receive durable, streamed answers grounded in authorized Evidence, manage their own conversations, and browse governed source documents.

The `docs/` package is the implementation authority for this rebuild. Keep this file focused on durable product and engineering constraints. Put setup commands, ports, environment variables, and troubleshooting in the README or service-specific documentation.

## Authority and Required Reading

Use this precedence when sources disagree:

1. This `AGENTS.md` and repository governance.
2. Approved product requirements and acceptance criteria: `docs/prd.md` and `docs/interaction-behavior-prd.md`.
3. Versioned HTTP, DTO, SSE, document/evidence, data, and AI contracts under `docs/contracts/` and `docs/database-schema.txt`.
4. Architecture, frontend, security, deployment, and quality specifications under `docs/architecture/`, `docs/frontend/`, and `docs/quality/`.
5. `docs/master-build-plan.md` and approved feature plans or task lists.
6. Code, migrations, tests, and observed runtime behavior.
7. Read-only reference implementations.

Read `docs/README.md` first, then the smallest authoritative set for the task. At minimum:

| Work | Required documents |
| --- | --- |
| Product behavior or permissions | `docs/prd.md`, applicable `M-*`/`A-*`/`C-*` cases in `docs/interaction-behavior-prd.md` |
| API or public data | `docs/contracts/http-api-catalog.md`, `docs/contracts/dto-schema-catalog.md` |
| Chat streaming | `docs/contracts/sse-event-catalog.md`, `docs/frontend/api-client-and-stream-runtime.md` |
| Retrieval, citations, or document viewing | `docs/contracts/document-and-evidence-contract.md`, `docs/architecture/data-and-lifecycle.md` |
| Database or state transitions | `docs/database-schema.txt`, the relevant architecture flow, and applicable interaction cases |
| Frontend | `docs/frontend/AGENTS.md`, root `DESIGN.md`, and the applicable route, state ownership, component, accessibility, responsive, and parity contracts under `docs/frontend/` |
| Security, BFF, auth, or deployment | `docs/architecture/frontend-security-boundary.md`, `docs/architecture/security-operations-and-quality.md`, `docs/architecture/deployment-topology.md` |
| Completion evidence | `docs/quality/definition-of-done.md`, `docs/quality/seeded-demo-and-test-data.md` |

Do not invent a transition, public field, endpoint, event, error code, or browser capability that is absent from the approved contracts. If a requirement has no approved contract, stop and identify the missing authority.

## Product Identity and Scope

Context Engine Phase 1 is a governed internal knowledge workstation, not a local-first Obsidian copilot, generic AI agent shell, conventional cloud admin dashboard, or multi-tenant workspace platform. Product-facing observability is deferred to Phase 2 and governed knowledge publication is deferred to Phase 3; the non-normative direction is retained under `docs/future/`.

The closed Phase 1 chat-capability manifest is owned only by `docs/prd.md#closed-phase-1-chat-capability-manifest`. Guidance, plans, microcopy, tasks, and tests must reference that anchor and must not create a competing capability list.

- A **Knowledge Domain** is the isolated retrieval boundary. It owns one private LightRAG runtime, one immutable embedding profile, its corpus, lifecycle, and query eligibility.
- A **Source Document** belongs to exactly one domain. Canonical Source Blocks are parser-independent, ordered, stable citable units.
- **Evidence** is a safe, authorized projection from private retrieval results to source labels, excerpts, document references, and semantic anchors.
- A **Conversation** belongs to one member. A turn is either `domain_rag` with exactly one domain or `direct_llm` with none.
- **Composer references** are short-lived opaque tokens for approved source, evidence, or template context. Store token hashes, not raw tokens.

Do not add a Workspace entity or use “domain” to mean a tenant, deployment, or runtime environment. Administrators gain operational capabilities; they do not automatically gain access to members’ private conversations or Evidence.

## Non-Negotiable Product Invariants

1. **Backend authority** — FastAPI and PostgreSQL own identity, authorization, configuration, lifecycle, operations, retrieval eligibility, conversations, Evidence, governed context, and audit history. UI state and disabled controls are never correctness boundaries.
2. **One-domain retrieval** — Query exactly one authorized, running, runtime-ready domain. Never mix corpora, expose raw LightRAG hits, or silently switch domains.
3. **Grounded means grounded** — A domain question may be synthesized only from mapped, authorized Evidence. No Evidence means a grounded refusal, never fallback to general model knowledge.
4. **Safe public projections** — Browser-visible values use approved opaque refs and closed DTOs. Private database IDs, block IDs, object keys, paths, runtime/provider URLs, credentials, traces, and raw payloads stay behind the API boundary.
5. **Durable idempotency and concurrency** — Database constraints, transactions, ETags, idempotency fingerprints, leases, and generation fences decide outcomes. Client deduplication and button state are presentation aids only.
6. **Deletion is a workflow** — Fence retrieval first; redact affected turns; invalidate governed-context references; clean remote, object, and local state idempotently; audit the outcome; keep failures recoverable.
7. **Protected mutations are audited atomically** — The product state change and required audit event commit together or neither commits.
8. **Privacy by construction** — Never persist or emit raw prompts, assembled context, raw hits, provider payloads, credentials, session/composer tokens, storage paths, runtime URLs, or stack traces where the schema or contract forbids them.

## Target Architecture

Keep the product a modular monolith with explicit outbound ports:

```text
untrusted browser -> public TLS ingress -> Next.js web/BFF -> private FastAPI
                                                        |-> PostgreSQL 16
                                                        |-> governed object storage
                                                        |-> private adapters and LightRAG runtimes
                                                        |-> database-leased workers
```

### Backend

- Use Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, and PostgreSQL 16. SQLite is a test convenience only and is never deployment or concurrency evidence.
- Keep route handlers thin: validate transport, invoke one application service, translate known failures, and project an approved public DTO or SSE stream.
- Services own authorization, transactions, state transitions, and cross-capability invariants. Repositories persist state but do not authorize. Adapters return typed results and safe error codes.
- Compose dependencies explicitly. Keep parser, model, object-storage, LightRAG, tracing, and runtime-controller implementations behind ports.
- Run migrations as an explicit release step. Do not run them from application replica startup.
- Use governed object storage for production source binaries and durable derived objects. A filesystem adapter is development-only; per-domain runtime directories are ephemeral and rebuildable.
- Use database-backed operation/outbox rows and workers. Do not add Redis, RQ, Celery, a message broker, or a generic workflow engine without an approved architecture change.

### Frontend and BFF

- Use the documented Next.js App Router, React, TypeScript, and Tailwind stack. Restore and honor committed lockfiles; do not select versions from minimum constraints alone.
- Only the Next.js origin is public. BFF handlers are narrow, request-scoped streaming proxies/DTO adapters; they do not authorize, persist product state, synthesize identity, or accept a browser-selected upstream.
- Keep `src/app` to routes, layouts, metadata, and same-origin BFF handlers; capability orchestration belongs in `src/features`; shared browser-safe contracts/utilities belong in `src/lib`; API-free, router-free, product-neutral primitives belong in `src/ui`.
- Do not create a competing `src/components` tree or let lower layers import upward. Share a primitive only after real reuse justifies it.
- Browser stores hold transient presentation state only. Never place sessions, CSRF values, passwords, raw composer tokens, prompts, answers, source excerpts, or private IDs in local/session storage.
- Personalized JSON, SSE, document bytes, and errors are `private, no-store`. Partition caches by current identity and clear private projections on logout, expiry, disablement, or role change.

## Authentication and Browser Trust Boundary

- FastAPI issues the `ce_session` opaque HttpOnly cookie, stores only its hash, and enforces absolute/idle expiry, revocation, and session rotation. Passwords use Argon2; provider credentials are encrypted at rest.
- Unsafe requests, including streaming POSTs, require an allowed Origin and session-bound `ce_csrf` cookie/`X-CSRF-Token` double submit. Host, public origin, trusted proxy, and cookie settings fail closed.
- The BFF forwards only allowlisted headers, strips caller identity/role/auth/upstream/forwarding headers, derives the trusted public host/protocol from server configuration, preserves streaming and range semantics, and propagates aborts.
- FastAPI re-derives current identity, role, ownership, state, and domain compatibility on every request and inside the committing transaction. Next middleware redirects only for user experience.
- Ownership-sensitive resources return the same `404` shape for unknown and unauthorized identifiers. Role revocation takes effect on the next authoritative check.
- Use the canonical safe error envelope and server-generated request ID. Do not leak raw exceptions or disclose whether another user’s resource exists.

## Domains, Sources, Retrieval, and Evidence

- Domains start `stopped`. Lifecycle operations use monotonically increasing generations; stale workers cannot overwrite newer start, stop, or delete decisions.
- Freeze a domain’s embedding profile and vector dimensions at creation. A migration to another embedding profile requires a separately approved re-index workflow.
- Stream uploads through server-side limits. Sniff and allowlist content, compute SHA-256 server-side, deduplicate within the domain, randomize object keys, sanitize display filenames, reject bombs, and freeze parser kind for the operation.
- Preparation atomically replaces ordered text/table/figure Source Blocks and safe image metadata. Never expose canonical source text through an outline endpoint.
- Render the versioned LightRAG handoff with local provenance markers. Index submit, readiness, retry, cancel, and delete are idempotent and fenced by lease/generation.
- Map every retrieval candidate back to an authorized local Source Block. Discard unmapped or cross-domain hits; only ordered safe Evidence crosses the product boundary.
- Evidence deep links use opaque document/evidence refs plus semantic page/block/region anchors. Content endpoints reauthorize every request, support governed PDF byte ranges, and never redirect to object storage.

## Chat, Governed Context, and SSE

- The server owns direct-chat versus domain-RAG classification. A domain-seeking question without a domain returns `domain_required`; the client never chooses a domain or reroutes silently.
- Use `(conversation_id, client_request_id)` plus the server-computed effective-input fingerprint for idempotency. Identical retries attach/replay without another provider or retrieval call; changed input with the same ID conflicts.
- Resolve ordered source, evidence, and template composer refs before provider work. Validate ownership, expiry, one-use state, duplicates, target state, and domain compatibility. Persist safe accepted-ref metadata and private linkage, never the assembled prompt.
- Use fetch-based SSE and the versioned envelope/event order in `docs/contracts/sse-event-catalog.md`. Do not introduce WebSockets, native `EventSource` for turn-start POSTs, or a second event protocol.
- Live start, resume, and durable replay feed one canonical reducer. Track received and applied cursors separately; ignore only exact duplicates, stop at gaps/regressions, reject unsupported major versions, and never infer completion from socket close.
- Persist a safe terminal projection. Disconnect is not cancellation; cancellation occurs only through the contracted endpoint. Redaction clears the public answer, citations, Evidence, and accepted-ref labels while preserving the user question.

## Asynchronous Work and External Calls

- Claims use real PostgreSQL locking, lease owner/expiry, heartbeat, and generation checks. Workers stop claiming during shutdown; expired work is recoverable.
- Commit operation intent before calling an external system. Make external calls outside database transactions with bounded timeouts and stable idempotency keys.
- A timeout with unknown remote outcome enters reconciliation before retry. Cleanup and retries must be repeatable and must not undo retrieval fencing, redaction, or invalidation.
- Freeze operation inputs such as parser kind, embedding dimensions, content hash, and generation. Changes to runtime defaults affect new work, not already accepted work.
- Return safe retryable operation states instead of disguising failures as empty success. Shed load with the contracted `413`, `429`, `503`, and conflict responses before resource use becomes unbounded.

## Frontend Product and Visual Contract

The frontend is a compact workstation informed by Local Studio’s visual patterns, not a generic dashboard. Local Studio is a design/pattern source only; Context Engine owns all copied tokens and primitives and must not import the reference at runtime.

- Required Phase 1 routes are `/login`, `/chat`, `/documents`, `/database-visualize`, `/settings`, and the safe forbidden/not-found states described in the route contract.
- The authenticated shell uses a collapsible discovery rail, one route-owned primary work surface, and an optional route-specific inspector. Chat specializes this into conversation discovery, transcript/composer, and a turn-scoped Evidence/Refs/Source inspector.
- `/database-visualize` remains deliberately unavailable and makes no graph or LightRAG request until a versioned graph API/DTO and coordinated product contract are approved.
- Default to the `zai-dark` layered-charcoal theme and support `zai-light` without geometry drift. Use Geist typography, semantic/component tokens, compact density, restrained borders/elevation, and the documented blue focus/link treatment.
- Feature code may use semantic or component tokens only. Do not scatter raw colors, spacing, radii, shadows, or transitions when a token exists.
- Implement loading, empty, ready, stale/refresh, safe failure with request ID, conflict, forbidden/not-found, reconnecting/offline, cancelled, deleted/redacted, and recovery states wherever reachable.
- Server truth wins after every mutation. Optimistic UI is limited to reversible presentation state; reject slow stale responses with request/selection/session generations.
- Preserve drafts across recoverable failures and safe navigation as specified. Do not persist them beyond allowed tab-memory state, and always clear them on identity change/logout.
- Below the documented breakpoints, rails and inspectors become accessible drawers rather than disappearing. Verify narrow 320 CSS-pixel layouts, desktop widths, touch/coarse pointer use, 200%/400% zoom, and no horizontal viewport push.
- Every action must work by keyboard and touch, not hover or color alone. Preserve visible focus, semantic status, focus trap/return, reduced motion, sanitized Markdown, and bounded live-region announcements.

The docs record historical conflict between older narrow-rail/two-column designs and the later three-region governed-context design. Follow the active normative frontend contracts; if an implementation plan reintroduces an incompatible layout, stop for one explicit authoritative decision rather than blending designs.

## Contracts, Schema, and Change Discipline

- Public JSON uses strict camelCase, closed enums and inputs, approved opaque refs, RFC 3339 UTC timestamps, and the canonical error/page envelopes. Unknown request fields fail closed.
- Generate OpenAPI and JSON Schema from registered backend routes and generate the browser client from those contracts. Handwritten substitute DTO interfaces are prohibited once a generated contract is required.
- Version SSE schemas and fixtures separately from OpenAPI. A contract change updates producer, generated client, reducer, fixtures, snapshots, compatibility range, and release/migration notes in one slice.
- PostgreSQL 16 plus Alembic is the persistence source of truth. Reproduce named uniqueness, check, FK, partial-index, and append-only invariants from `docs/database-schema.txt`.
- A migration lands with model/service tests, fresh-install and supported-upgrade proof, and rollback/restore notes. Destructive changes use expand/migrate/contract and require backup/restore evidence.
- Do not expose internal schema shape through public DTOs. `allowedActions` is advisory UI metadata; every mutation is reauthorized.

## Reference and Adaptation Policy

Local Studio and any reviewed Context Engine checkout are read-only evidence, not product or runtime dependencies.

- Use `docs/frontend/source-adaptation-map.md` and `docs/architecture/production-adaptation-blueprint.md` before porting a pattern.
- Record source provenance for adapted frontend tokens/primitives and verify them against Context Engine security, accessibility, and contract requirements.
- Do not inherit Local Studio’s SQLite/JSON persistence, agent tools, plugin system, filesystem/terminal/browser access, inference-controller authority, Electron trust model, or browser-selectable runtime configuration.
- Vendored LightRAG is a private retrieval adapter. Its internals, identifiers, payloads, URLs, and operational state are not public product contracts.

## Explicitly Out of Scope Without an Approved Contract Change

- Generic multi-tenant workspaces or a new Workspace entity.
- Plugins, arbitrary agent tools, terminal/filesystem/browser automation, or a generic workflow engine.
- Redis/RQ/Celery, a message broker, Kubernetes, or a new external queue/orchestrator chosen by implementation convenience.
- WebSocket migration or a second streaming protocol.
- Browser access to providers, parsers, LightRAG, Docker, PostgreSQL, object storage, runtime URLs, credentials, host paths, usage/cost calculation, or controller selection.
- A second retrieval stack or ungrounded fallback for domain questions.
- Phase 2 product-observability routes, read APIs, dashboards, live log streams, exports, retention controls, or analytics. Retain only the private Phase 1 operational-safety baseline defined by the PRD and architecture contracts.
- Phase 3 knowledge-publication schema, APIs, routes, composer refs, contribution/review workflows, fixtures, or release gates.
- A functional graph UI before the graph contract is approved.

## Testing and Verification

- Every feature maps to its applicable `M-*`, `A-*`, and `C-*` interaction cases. Include the case ID in tests.
- Start with the lowest useful deterministic test, then cover the actual boundary: pure unit, real PostgreSQL service/repository, HTTP/SSE contract, adapter fixture, frontend state/component, browser E2E, or deployed ingress.
- Use PostgreSQL transaction barriers/latches, not sleeps, for shared-state races. Mocks cannot prove authorization, locking, generation fences, audit rollback, streaming, or recovery.
- Freeze OpenAPI/SSE snapshots and validate examples with production schemas. Exercise success, boundary, malformed input, denial, timeout, uncertain outcome, retry, cancellation, stale completion, and cleanup failure where applicable.
- Use the deterministic fixtures in `docs/quality/seeded-demo-and-test-data.md`. They must be synthetic, versioned, reproducible, idempotent, network-free, and impossible to seed in production accidentally.
- Browser E2E runs through the production Next build, BFF, FastAPI, workers, PostgreSQL 16, and governed test object store. Test two-user cache isolation, multi-tab races, logout/back-cache behavior, keyboard/focus, narrow layouts, and real SSE reconnect/replay.
- Privacy tests scan responses, browser storage, logs, audit rows, traces, metrics, snapshots, fixtures, and failure artifacts for forbidden data.
- Frontend changes require type/lint/build checks, component/state coverage, accessibility checks, and visual regression at the documented theme/viewport/density matrix.
- Production evidence must use built artifacts through the deployed ingress topology. A local Compose success or green mocked UI suite is pilot evidence only.

## Implementation Workflow and Stop Conditions

- Follow `docs/master-build-plan.md` in dependency order. Each phase is a vertical slice: migrations, contracts, service behavior, tests, acceptance evidence, and operational notes complete together.
- Treat reviewed source as evidence, not proof that a rebuild task is done. Inspect `docs/architecture/as-built-gaps-and-decisions.md` before relying on scaffolded parsers, providers, native LightRAG/runtime control, tracing, PDF preview, graph, or node operations.
- Do not scaffold future controls or fixture-only loaded states. When a contracted capability is unavailable, render the deliberate unavailable state only if the product contract permits it.
- Keep one user intent per implementation slice and produce the evidence record required by `docs/quality/definition-of-done.md`.

Stop and obtain an explicit decision when:

1. A browser feature needs a field, event, endpoint, source-content URL, runtime target, or private identifier absent from the approved contracts.
2. Real parser/provider behavior would change canonical blocks, Evidence, streaming, or error semantics.
3. Native LightRAG cannot prove provenance mapping, idempotent submit, readiness, or deletion.
4. Production needs a queue, object-store technology, orchestrator, tenancy model, or topology outside the approved architecture.
5. A destructive migration or delete/redaction flow lacks automated recovery and restore evidence.
6. Visual parity conflicts with security or accessibility and no approved divergence exists.

## Definition of Done

A change is complete only when:

1. It satisfies the applicable PRD requirements and interaction case outcomes, including race/failure behavior.
2. Backend authority, authorization, privacy classifications, and public contract boundaries remain intact.
3. Persistence, audit, idempotency, lease/generation, deletion/redaction, and recovery invariants are proven at the appropriate real boundary.
4. HTTP, DTO, SSE, generated client, fixtures, snapshots, and migrations remain synchronized.
5. The UI implements all reachable states and passes keyboard, focus, responsive, theme, zoom, reduced-motion, and visual-parity checks.
6. Relevant deterministic tests and the root verification gate pass; any non-applicable gate has a written boundary reason.
7. Operational impacts, safe observability, compatibility, and recovery notes are documented, and completion evidence identifies the artifact/source revision tested.

When requirements conflict, protect authorization and private data first, preserve contract and transactional correctness second, and prefer explicit unavailability over invented behavior.
