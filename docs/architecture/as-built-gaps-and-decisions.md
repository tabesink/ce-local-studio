# As-Built Gaps and Required Decisions

This file prevents a rebuild agent from treating either an approved specification or a lifted implementation seam as completion proof. The 2026-07-22 current-tree review in `docs/_scratch/code-docs-drift-review.md` is the evidence baseline; its 33 findings are dispositioned in `docs/brownfield-refactor-register.md`.

## Reusable but unverified brownfield foundations

- FastAPI application factory, Argon2 and opaque-token hashing, cookie-authentication scaffolding, role/ownership queries, request IDs, error translation, and allowlisted logging exist, but session, CSRF, cache, error-shape, audit, and bootstrap requirements remain unproven or drifted.
- SQLAlchemy models contain useful ownership, generation, lease, request-identity, provenance, and composer-reference concepts. The active Phase 1 schema is a clean-install target; legacy persistence removal is blocked by `legacy-persistence-retirement.md`.
- Domain/source/index state machines and vendored LightRAG boundaries are implementation evidence only; timeout, fairness, recovery, readiness, provenance, idempotency, and deletion proofs are outstanding.
- Conversations, pilot stream events, composer-reference persistence, deletion/redaction hooks, and audit-write services exist, but the durable canonical SSE, attach/replay/cancel, one-use, atomic audit, and privacy boundaries are not complete.
- Next.js shell, routes, themes, chat/evidence UI, document operations, settings, component trees, and tests exist, but handwritten contracts, BFF, state ownership, accessibility, import boundaries, and production acceptance remain open.

Every foundation stays `NOT_STARTED` until the targeted boundary proof in the brownfield register passes.

## Partial or scaffolded capabilities

- **Parsers:** current Docling adapter is a simple text fallback; Reducto fails as unimplemented. Choose and add real SDK/process integration, fixtures, timeouts, and typed errors.
- **Model providers:** OpenAI, Bedrock, and Ollama are represented in configuration/ports, but their SDK dependencies and production adapters are not proven by the root manifest.
- **LightRAG/runtime:** local Compose deliberately uses local client/controller modes. Native per-domain LightRAG and Docker lifecycle need separate integration evidence.
- **Tracing:** the optional tracer currently resolves to a disabled/no-op port and has no Langfuse dependency/configuration.
- **Frontend chat layout:** current UI has a timeline/composer and one Evidence aside. The approved persistent left discovery plus right Evidence/Refs/Source tabbed three-region workbench is not fully present.
- **Documents:** administrator source operations exist; member read-only library semantics and safe inline PDF preview remain unproven. Preview is disabled pending an opaque safe source-ref/content contract.
- **Graph:** `/database-visualize` is a placeholder because no approved graph DTO/API is implemented.
- **Deferred scope in reviewed code:** capabilities excluded from the Phase 1 contract are not implementation gaps and must not be scaffolded. Logs/Usage/Server and audit/diagnostic browsing are isolated in `../future/observability-layer.md`; wiki intent is isolated in `../future/wiki-layer.md`.
- **Reviewed observability screens:** existing log, usage/cost, Server-status, storage-summary, and node-dashboard code is reference evidence for Phase 2 only, even when locally functional.

## Specification drift to resolve before frontend rebuild

- Older F-009 UX notes describe a narrow icon rail, settings dialog, and two-column chat.
- The later approved F-009 specification and surviving code use a wide collapsible sidebar and full settings page.
- F-012 supersedes the chat workspace with governed context assembly and a three-region target.
- Record one authoritative layout decision in the active spec before implementation; do not blend all three designs.

## Delivery gaps

- P0-01 selected `app/context_engine/` as the canonical backend package and `app/client/` as the frontend path; the backend import, frozen image build, Compose syntax, and development-script path checks now pass. The Alembic baseline and runnable Compose startup remain later P1/P10 work; the root loop’s still-missing boundary coverage is listed below.
- The root CI now invokes the pinned verification loop. Its historical baseline was red for missing backend coverage and inherited frontend type/build/test failures; the current local loop passes lock integrity, backend import/lint and focused tests, deterministic OpenAPI/TypeScript live and stale-artifact checks, frontend typecheck/tests/build, the backend image build, and Compose configuration. HTTP catalog/response-model parity, canonical SSE schemas/fixtures, PostgreSQL migration tests, privacy scans, browser E2E, and deployed-ingress/load evidence remain outstanding.
- No production cloud/Kubernetes/Terraform environment is claimed. The target now requires governed object storage and database-leased workers, but vendor/topology, secret manager/KMS, TLS/ingress, backup retention implementation, and monitoring platform remain deployment decisions.
- The Bash development script assumes Linux tooling and is not directly portable to native Windows; provide cross-platform commands or declare WSL/container development as the supported path.

## Decision gates

Stop and obtain an explicit decision when:

1. a browser feature needs an unapproved backend field, source-content URL, runtime target, or private identifier;
2. real parser/provider behavior changes canonical block, Evidence, streaming, or error contracts;
3. native LightRAG cannot prove idempotent submit, readiness, provenance mapping, or deletion;
4. production deployment requires a queue, object store, orchestrator, or tenancy model not in the approved architecture;
5. a destructive migration or delete/redaction path lacks automated restore/recovery evidence.
