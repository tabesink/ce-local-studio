# Architecture Overview

## System shape

```text
Browser -> Next.js web/BFF
    |
    | same-origin HTTP + cookie; versioned JSON and SSE
    v
FastAPI application
    |-- auth / ownership / admin policy
    |-- domain, source, chat, composer services
    |-- audit writes, safe logging, health
    |
    +--> PostgreSQL (product authority)
    +--> governed object storage
    +--> parser adapters (Docling / Reducto)
    +--> per-domain private LightRAG runtimes
    +--> model providers (OpenAI / Bedrock / Ollama)
    +--> optional tracing sink
    +--> leased async workers
```

## Architectural style

The application is a modular monolith with explicit outbound ports and an explicit dependency container. FastAPI routes translate versioned DTOs and enforce dependencies; capability modules own domain rules and transactions; SQLAlchemy repositories persist authoritative state; workers execute leased asynchronous operations; adapters isolate parsers, LightRAG, model providers, storage, tracing, and runtime controllers. The Next.js layer supplies the web shell and narrow BFF routes for same-origin transport and server-only configuration; it never becomes an alternate product backend.

## Authority boundaries

- PostgreSQL owns identity, sessions, configuration metadata, lifecycle state, operation state, canonical blocks, chat history, evidence mappings, governed refs, and audit history.
- Governed object storage owns uploaded binaries and durable derived objects. A filesystem adapter is development-only; per-domain runtime directories are private, ephemeral, and rebuildable.
- LightRAG owns retrieval internals only. Context Engine owns eligibility, provenance mapping, evidence, citations, and deletion correctness.
- Provider/parser systems perform computation but do not define public DTOs or persisted product state.
- The browser owns transient presentation state only.

## Key design decisions

1. One private LightRAG runtime per Knowledge Domain prevents cross-domain retrieval leakage.
2. Embedding profile and vector dimensions are immutable for an existing domain.
3. Canonical Source Blocks decouple citations from parser-native output and LightRAG chunk identities.
4. HTTP plus SSE is sufficient; no WebSocket or generic workflow engine is required.
5. Database-backed operations use leases and generation fencing for retryable async work.
6. Public evidence is a safe projection; private source/block IDs stay below the API layer.
7. Deletion includes downstream redaction/invalidation, not merely storage removal.
8. HTTP contracts are generated from registered routes; SSE envelopes are separately versioned and replayed through the same client reducer used for live events.
9. Production web, API, and workers are independently deployable artifacts but share one contract release and migration compatibility policy.

See `production-adaptation-blueprint.md` for the Local Studio reuse/adapt/reject matrix and the production target.

## Source evidence

- root `AGENTS.md`, `docs/prd.md`, and the versioned contracts in this package;
- `docs/_scratch/code-docs-drift-review.md` and `docs/brownfield-refactor-register.md`;
- `app/context_engine/{app,db,models}.py`, `app/context_engine/api/*`, and `app/context_engine/services/*`;
- `app/client/src/*`, `app/client/tests/*`, and the current package/lock files;
- `app/vendor/lightrag/*`, `app/compose.stack.yml`, `app/Dockerfile`, and `scripts/dev.sh`.

These paths are current-tree evidence only. Their known red build/import/type/test baseline prevents any claim that the target architecture is already implemented.
