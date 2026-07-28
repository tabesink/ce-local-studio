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

- **Parsers:** P4-03 lands a `DocumentParser` port with Docling/Reducto adapters, injectable fixtures, bounded timeouts, and typed fail-closed errors. Live workers still require optional `parsers` extras (`docling`, `reductoai`); CI proves behavior via injected transports without network. Production packaging and credential-gated staging smoke are owned by P10-05.
- **Model providers:** P7-03 proves an OpenAI synthesis outbound adapter with injectable transport, timeout/output bounds, and fail-closed typed errors; Bedrock/Ollama synthesis kinds remain fail-closed registry entries until P10-05 packaging and staging smoke claim them. Live OpenAI calls still require the optional `synthesis` extra (`openai`); CI proves behavior without network. Embedding and other provider SDK paths remain unproven by the root manifest.
- **LightRAG/runtime:** default Compose stays `local`/`local`. P5-04 proves the production `docker`+`native` private per-domain vendored LightRAG path via opt-in `compose.stack.live.yml` (`docs/_scratch/p5-04-lightrag-real-runtime-evidence.md`). P12-04/05/06/07 consume that proof for rebuild, ingress SSE, SBOM, and capacity.
- **Object storage:** filesystem adapter is development-only. Phase 1 local-production uses MinIO through one S3-compatible adapter (P10-04). Do not promote host-filesystem storage to production.
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
- No Kubernetes/Terraform environment is claimed. Phase 1 local-production topology is Compose-deployed PostgreSQL, MinIO (S3-compatible), API/workers, Next BFF, and private per-domain LightRAG runtimes (P10-04, P5-04). Secret manager/KMS, TLS/ingress, backup retention implementation, and monitoring platform remain deployment decisions under P12.
- The Bash development script assumes Linux tooling and is not directly portable to native Windows; provide cross-platform commands or declare WSL/container development as the supported path.

## Decision gates

Stop and obtain an explicit decision when:

1. a browser feature needs an unapproved backend field, source-content URL, runtime target, or private identifier;
2. real parser/provider behavior changes canonical block, Evidence, streaming, or error contracts;
3. native LightRAG cannot prove idempotent submit, readiness, provenance mapping, or deletion;
4. production deployment requires a queue, object store, orchestrator, or tenancy model not in the approved architecture;
5. a destructive migration or delete/redaction path lacks automated restore/recovery evidence.
