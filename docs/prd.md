# Product Requirements Document: Context Engine

## 1. Product summary

Context Engine is an internal shared-workspace RAG product. Administrators curate isolated Knowledge Domains and their source corpora; authenticated members ask questions and receive streamed, evidence-grounded answers with durable conversations and citations. The same system provides governed prompt-context assembly and the operational controls required by those workflows without exposing infrastructure or secrets to the browser.

Phase 1 production scope ends at the grounded RAG workstation, governed source/evidence/template context, and its minimum operational-safety controls. The operator-facing observability layer is deferred to Phase 2 in `future/observability-layer.md`; the wiki layer is deferred to Phase 3 in `future/wiki-layer.md`. Neither future layer is a Phase 1 dependency or implementation target.

## 2. Product goals

- Make organizational knowledge queryable within explicit, administrator-controlled retrieval boundaries.
- Make every domain answer traceable to authorized Source Blocks and safe user-visible Evidence.
- Preserve backend authority over authentication, configuration, ingestion, retrieval, deletion, redaction, and context assembly.
- Support local/private model and LightRAG execution while keeping deployment targets opaque to users.
- Provide a compact, dark-first Local Studio-style workstation rather than a generic administration dashboard.

## 3. Actors and permissions

### Member

- Authenticate with a server-issued HttpOnly cookie session.
- List query-eligible Knowledge Domains.
- Create, rename, list, open, and delete only their own conversations.
- Stream direct-general-chat or domain-grounded turns; the server chooses the route.
- View turn-scoped evidence.
- Discover safe, opaque composer references for authorized sources, evidence, and templates.

### Administrator

Includes Member capabilities and may additionally:

- manage provider credentials, model profiles, parser defaults, and runtime defaults;
- create/start/stop/delete Knowledge Domains;
- upload, prepare, index, retry, cancel, inspect, and delete Source Documents;
- inspect and control the contracted Knowledge Domain and Source Document operations.

### Worker/system

- Claim leased domain, preparation, and indexing operations.
- Execute idempotent transitions and write safe audit/log records.
- Never broaden authorization or expose private runtime/storage identifiers.

## 4. Core domain concepts

- **Knowledge Domain:** isolated retrieval boundary with one private LightRAG runtime, immutable embedding profile, immutable graph-extraction-capable synthesis profile, corpus, lifecycle, query-eligibility state, and bounded read-only graph projection.
- **Source Document:** uploaded file belonging to exactly one domain.
- **Canonical Source / Source Block:** normalized, parser-independent representation and stable citable units.
- **Evidence:** authorized mapping from retrieval output to safe source labels/excerpts and private source identities.
- **Conversation / Turn:** user-owned history; a turn is either `domain_rag` with exactly one domain or `direct_llm` with none.
- **Composer reference:** short-lived opaque backend token selecting approved context without revealing private target IDs.

Do not add a Workspace entity or use “domain” to mean tenant/deployment environment without an approved contract change.

## 5. Functional requirements

### FR-01 Authentication and authorization

- Seed an initial administrator from environment configuration.
- Store Argon2 password hashes and hashed session tokens.
- Issue opaque HttpOnly cookie sessions with expiry, revocation, configurable `Secure`, and validated `SameSite` behavior.
- FastAPI owns sessions; require trusted Host/Origin plus a session-bound CSRF token for every unsafe request, rotate sessions at login, and enforce absolute/idle expiry and revocation.
- Enforce ownership on member resources and role checks on `/admin/*` routes.

### FR-02 Trusted runtime configuration

- Support provider kinds `openai`, `bedrock`, `ollama`, and parser-provider `reducto`.
- Encrypt credentials at rest; return only safe presence/update metadata.
- Maintain synthesis and embedding model profiles; embedding profiles require fixed vector dimensions.
- Freeze a domain’s embedding profile after creation.
- Bind each Knowledge Domain to one immutable, catalog-declared graph-extraction-capable synthesis model profile for private LightRAG entity/relation extraction, sealed separately from chat synthesis defaults. Profiles bound in either role cannot be mutated or deleted while in use. Detail for one-time legacy assignment and ineligibility rules lands with the owning implementation slice.
- Maintain singleton defaults for active synthesis model and parser.

### FR-03 Knowledge Domain lifecycle

- Create domains stopped, then support start, stop, status, operation history, and asynchronous hard delete.
- Give each domain a private runtime instance and monotonically increasing control generation.
- Reject conflicting lifecycle operations and stale worker completions.
- A domain is query-eligible only when authorized, running, not deleting, and runtime-ready.

### FR-04 Source ingestion and preparation

- Stream uploads through server-side size limits; sniff and allowlist content, compute SHA-256 server-side, reject decompression/content bombs, use randomized object keys, and treat the sanitized filename as display metadata only.
- Deduplicate source content within a domain.
- Freeze parser kind on upload; resolve current credentials privately at execution.
- Prepare asynchronously into ordered text/table/figure Source Blocks plus safe image metadata.
- Support operation status, retry, cancel, and hard delete.

### FR-05 Indexing and scoped evidence

- Render canonical blocks into the versioned LightRAG handoff format.
- Submit idempotently, poll readiness, retry/cancel, and fence stale index workers by generation and lease.
- Query exactly one eligible domain.
- Map raw LightRAG results back to authorized local Source Blocks; never return raw hits.
- Return ordered Evidence with safe source labels/excerpts and no storage/runtime/provider details.

### FR-05a Read-only Knowledge Domain graph

- Expose authenticated, domain-authorized, `private, no-store` read-only graph snapshot and label-search endpoints defined by the HTTP and DTO catalogs.
- Project only opaque purpose-derived graph refs (`CE_GRAPH_REF_KEY`), safe labels, closed kinds, non-negative degrees, and truncation metadata. Reject raw properties, source/chunk IDs, paths, URLs, prompts, provider payloads, and coordinates.
- Keep depth, node/edge/byte/time bounds server-owned. Unknown or unauthorized domains share the same `404` shape; stopped, unready, or deleting domains return approved safe conflict or dependency states; deletion races where desired generation is ahead of applied return retryable `409 graph_refreshing`.
- Admit graph reads through per-domain and global in-flight permits with a zero-length wait queue (`429` + `Retry-After` or `503 capacity_unavailable`). Private adapter payloads above 2 MiB become `dependency_unavailable`; mapper truncation sets `truncated: true`.
- The `/database-visualize` workbench is read-only: domain selection, bounded refresh, canvas pan/zoom/select, searchable list/detail equivalent, and URL state limited to opaque `domain` and `node` refs. Browser→LightRAG/runtime access and graph mutation APIs remain prohibited.

### FR-06 Conversations and grounded streaming chat

- Persist user-owned conversations and turns.
- Use `(conversation_id, client_request_id)` for idempotency; replay terminal turns without calling retrieval or model providers again.
- Server-classify no-domain requests as narrow direct general chat or reject domain-seeking requests without a domain.
- For domain RAG, perform bounded plan/retrieval/repair orchestration and synthesize only from mapped Evidence.
- Stream the versioned SSE event sequence and persist the safe terminal projection.
- If no grounded evidence exists for a domain question, do not answer from general model knowledge.

#### Closed Phase 1 chat capability manifest

This is the sole normative capability manifest for member chat. The server may classify a turn, produce a direct response for a server-classified `direct_llm` turn, retrieve from exactly one authorized domain and synthesize or refuse from mapped Evidence for `domain_rag`, replay a durable turn, process an explicit cancellation, and redact affected durable output. Phase 1 member chat has no open tool registry, plugins, terminal, filesystem access, browser automation, agent approval queue, or browser-selected model, provider, controller, or runtime target. Other guidance, plans, microcopy, tasks, and tests must link to this section rather than restate the set.

### FR-07 Governed context assembly

- Discover authorized context targets and return one-use/short-lived raw tokens; persist only SHA-256 hashes.
- Accept ordered refs of kind `source`, `evidence`, or `template`.
- Validate caller ownership, expiry, domain compatibility, target state, and duplicates before assembly.
- Persist only safe accepted-reference metadata and private linkage, never assembled prompts or raw context.

### FR-08 Deletion and redaction

- Block retrieval before deleting a source/domain.
- Fence and rebuild derived domain graph contribution with generation-aware reconciliation; graph reads during the gap return retryable `graph_refreshing`.
- Redact every affected turn as a unit: preserve the user question, clear assistant answer and public evidence/citation fields, retain internal redaction rows for audit.
- Public conversation and SSE replay must omit redacted evidence.
### FR-09 Operational safety and accountability

- Emit server-generated request IDs on every response and private trace IDs for newly executed chat turns.
- Write JSON logs using safe allowlisted fields.
- Write append-only audit events for protected mutations and authorization denials; protected mutations fail closed if their audit write fails.
- Expose only aggregate liveness/readiness needed to operate Phase 1. Audit browsing, runtime-log access, diagnostic browsing, usage analytics, live log streams, exports, retention controls, and observability dashboards are not Phase 1 APIs or UI.

### FR-10 Frontend workstation

- Use Next.js App Router with `/login`, `/chat`, `/documents`, `/database-visualize`, and `/settings` surfaces plus guarded navigation.
- Use the old Context Engine client for route/layout structure and Local Studio for tokens, primitives, compact geometry, and interaction styling.
- Default to the `zai-dark` layered-charcoal theme with Geist typography.
- Keep the client thin: all product truth and authorization come from versioned Context Engine APIs.
- Display the evidence for exactly one selected turn in the read-only Evidence Panel; keep the governed reference picker distinct from evidence inspection.
- Provide the read-only `/database-visualize` Knowledge Domain graph through the approved graph contract only, with keyboard/touch-accessible list/detail equivalent to the canvas.

### FR-11 Production delivery and recovery

- Ship reproducible, immutable web/API/worker artifacts with recorded build inputs, schema version, and contract version.
- Separate liveness, readiness, and safe dependency diagnostics; readiness includes migration state and required service availability.
- Drain active streams and worker claims on shutdown, recover expired leases, and expose safe retry/cancel operations.
- Run database migrations as an explicit release step using expand/migrate/contract for destructive evolution.
- Prove backup and restore for PostgreSQL, governed source objects, encryption keys, and required configuration metadata.
- Verify incremental SSE, reconnect/replay, authentication, redaction, audit failure behavior, and worker restart through the deployed ingress path.

## 6. Non-functional requirements

- **Security:** deny by default; no browser access to LightRAG, Docker, DB, storage paths, providers, controllers, runtime URLs, or credentials.
- **Privacy:** no raw prompt, answer, source text, raw hit, provider payload, secret, path, or stack trace in logs/audit/traces/public DTOs.
- **Consistency:** destructive state changes, audit writes, context-reference consumption, and generation fences are transactional.
- **Resilience:** leases, retries, idempotency keys, generation counters, bounded orchestration, and readiness checks prevent duplicate/stale work.
- **Traceability:** every requirement maps to tests and acceptance evidence.
- **Accessibility:** keyboard-operable controls, visible focus, semantic status not conveyed by color alone, and readable contrast.
- **Operability:** bounded-cardinality metrics, actionable health states, graceful shutdown, capacity limits, and documented recovery objectives.
- **Reproducibility:** pinned runtimes and lockfiles, deterministic builds, migration/contract snapshots, and a release evidence manifest.

## 7. Explicitly out of scope without a new approved contract

- Generic multi-tenant workspaces, plugin systems, workflow engines, Redis/RQ/Celery, or WebSocket migration.
- Browser-selected controller/runtime URLs, API keys, host paths, direct Docker/DB/storage/provider access, or browser-calculated cost/storage truth.
- A second retrieval stack or fallback to ungrounded model knowledge for domain questions.
- Graph entity/relation create, edit, rename, merge, or delete; browser-selected LightRAG/runtime ports; direct browser `/graphs` access; or exposure of raw vendor graph identifiers/properties.
- Logs, Usage, or Server observability screens; audit/diagnostic browsing; runtime-log session APIs; live log SSE; log download/deletion/retention UI; usage/cost/model analytics; operator exports; and observability-specific persistence. These require the Phase 2 feature branch and a separately approved contract; see `future/observability-layer.md`.
- Wiki pages, revisions, contributions, review/publication workflows, wiki composer refs, and wiki UI/API/schema scaffolding. These require the future feature branch and a separately approved contract; see `future/wiki-layer.md`.

## 8. Product acceptance outcomes

The product is rebuild-complete when an admin can configure providers/models, create and run a domain with immutable embedding and graph-extraction bindings, upload and prepare a document, index it so retrieval and the bounded domain graph are ready, and a member can receive a durable streamed answer whose citations map to safe authorized evidence and can open the read-only `/database-visualize` graph through the approved safe projection. Idempotent replay must avoid repeated external work; deleting the source/domain must block retrieval, refresh derived graph state, and redact derived chat state; audit/log output must remain safe; and the frontend must operate exclusively through the backend contract.

It is production-ready only when the same outcomes pass in the deployed topology with migration/rollback, backup/restore, lease recovery, graceful shutdown, capacity and failure tests, accessibility, and release evidence. A locally functional pilot is not production acceptance.

Detailed observable member/admin behavior, atomic transitions, stale-state handling, and multi-user races are normative in `interaction-behavior-prd.md`. Every applicable case ID must map to implementation tests before its feature is accepted.
