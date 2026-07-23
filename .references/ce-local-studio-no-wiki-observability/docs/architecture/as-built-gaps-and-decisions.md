# As-Built Gaps and Required Decisions

This file prevents a rebuild agent from treating every approved specification as already proven by the reviewed implementation.

## Proven or materially implemented

- FastAPI application factory, cookie authentication, role/ownership dependencies, canonical error handling, request IDs, and safe structured logging.
- Reviewed SQLAlchemy models cover 22 tables; Phase 1 contracts retain 18 and ignore the four deferred-feature tables.
- Domain/source/index worker state machines with leases and generation fencing.
- Vendored LightRAG import boundary, deterministic block rendering, retrieval provenance mapping, and local/fake integration paths.
- Durable conversations, SSE projection/replay, governed composer-ref persistence, deletion redaction, and transactional audit-write services.
- Thin Next.js API/SSE client, authentication shell, wide navigation, chat/evidence UI, document operations, and settings.

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

- The dirty checkout omits tracked root manifests, migrations, tests, scripts, CI, Dockerfile, and Compose files; recover them from Git `HEAD` or recreate them from this package.
- Existing CI emphasizes backend Docker-controller and Pytest coverage. Add frontend build/typecheck/tests, PostgreSQL migration tests, secret/safety scans, browser E2E, and bounded load tests.
- No production cloud/Kubernetes/Terraform environment is claimed. The target now requires governed object storage and database-leased workers, but vendor/topology, secret manager/KMS, TLS/ingress, backup retention implementation, and monitoring platform remain deployment decisions.
- The Bash development script assumes Linux tooling and is not directly portable to native Windows; provide cross-platform commands or declare WSL/container development as the supported path.

## Decision gates

Stop and obtain an explicit decision when:

1. a browser feature needs an unapproved backend field, source-content URL, runtime target, or private identifier;
2. real parser/provider behavior changes canonical block, Evidence, streaming, or error contracts;
3. native LightRAG cannot prove idempotent submit, readiness, provenance mapping, or deletion;
4. production deployment requires a queue, object store, orchestrator, or tenancy model not in the approved architecture;
5. a destructive migration or delete/redaction path lacks automated restore/recovery evidence.
