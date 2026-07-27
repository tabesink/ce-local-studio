# Data and Lifecycle Architecture

## Domain lifecycle

```text
create -> stopped -> start operation -> running
running -> stop operation -> stopped
stopped/running -> deleting -> delete worker -> removed
```

Every control operation records its generation. Workers may complete only while their lease and generation remain current. Delete first makes the domain ineligible, then removes remote/runtime and local derived state, redacts dependent chat state, and finally removes authoritative domain rows.

## Source and index lifecycle

```text
upload -> pending -> prepare operation -> prepared
prepared + domain running -> index queued -> processing -> ready
processing -> failed | cancelled | ready
any live source -> deleting -> redaction/invalidation -> remote/local removal
```

Preparation produces stable ordered Source Blocks. Indexing renders a versioned handoff containing local provenance markers, then maps retrieval results back through those markers. Generation counters and content hashes make retry safe and prevent stale completions.

## Grounded turn lifecycle

1. Authorize conversation ownership and validate `client_request_id`.
2. Resolve and validate composer refs; compute a stable fingerprint.
3. Determine effective route: explicit domain means `domain_rag`; otherwise the server intent gate may allow `direct_llm`.
4. Persist a running turn with private trace ID and bounded-operation counters.
5. For domain RAG, validate domain/source eligibility, retrieve and map Evidence, then synthesize only from the authorized context.
6. Stream safe plan/status/evidence/token/terminal events.
7. Persist terminal answer, stop reason, safe error, Evidence refs, and accepted composer refs.
8. On an identical terminal retry, replay persisted state without external calls; mismatched inputs return conflict.

## Redaction invariant

Deleting any cited source or the selected domain redacts the whole derived turn. Preserve `user_message`; set turn status/stop reason to redacted; clear assistant answer and public evidence labels/excerpts; retain redacted evidence rows for internal audit. Public mappers treat them as absent.

## Authoritative data ownership

| Resource | Authoritative owner and isolation key | Phase 1 access rule |
| --- | --- | --- |
| users and sessions | FastAPI/PostgreSQL; user identity | a user receives only the approved current-user projection; administrators receive only contracted safe user summaries and never session/token material |
| runtime settings and model profiles | FastAPI/PostgreSQL; deployment singleton | administrators mutate through services; credentials remain write-only and encrypted |
| domains, sources, blocks, images and index state | FastAPI/PostgreSQL plus governed object storage; `domain_id` | administrators curate; members receive only authorized, query-eligible safe projections |
| conversations, turns, Evidence and accepted refs | FastAPI/PostgreSQL; `owner_user_id` through conversation ownership | only the owning member; administrator role grants no implicit read access |
| operations, leases and generations | FastAPI/PostgreSQL; target resource and generation | services/workers only; public DTOs expose only approved safe operation projections |
| audit events | FastAPI/PostgreSQL; system-owned append-only history | transactional writes remain mandatory; Phase 1 has no product read/export surface |
| browser URL/store/component state | current identity and tab/route epoch | presentation only; it never authorizes, owns product state or survives beyond its contracted lifetime |

PostgreSQL is authoritative for identity, authorization, lifecycle, operation intent, private linkage and durable product state. Governed object storage owns source bytes and durable derived objects referenced by PostgreSQL metadata. Per-domain runtime directories and LightRAG state are private rebuildable derivatives, never ownership or backup authority. Repositories persist within a service-supplied scope and never decide authorization.

Conversation CRUD uses dedicated cryptographically random `conv_`/`turn_` public refs and stable `(created_at,id)` keyset order; private primary keys never cross HTTP, SSE, composer, or newly persisted safe-event projections. Append-only legacy accepted events remain byte-for-byte intact and the authorized replay projector substitutes current public refs before emission. Migration-first rollout retains database-side public-ref defaults so the previous application remains insert-compatible through deploy and rollback. Rename and delete lock the owner-scoped conversation row, revalidate the current enabled session/user inside the committing transaction, compare the persisted positive version, and commit the protected mutation with `conversation.created`, `conversation.renamed`, or `conversation.deleted` audit intent. Conversation creation does not accept durable `Idempotency-Key` semantics until the separately approved shared create-idempotency record contract exists.

## Privacy classes and allowed sinks

| Class | Examples | Browser/API | Product database/object storage | logs, metrics, audit and traces |
| --- | --- | --- | --- | --- |
| `public_safe` | approved opaque refs, display labels, safe excerpts, closed status/error values, timestamps | only through a closed authorized DTO/event/byte contract | allowed when required by the schema | only explicitly allowlisted bounded-cardinality values |
| `private_operational` | database IDs, block IDs, private linkage, trace IDs, object keys, runtime/controller/provider identifiers | forbidden | allowed only for the owning invariant or recovery workflow | only the explicit operational/audit allowlist; never metric labels when identity-bearing |
| `content_sensitive` | questions, answers, source bytes/text, template bodies, assembled context, raw hits/provider payloads | only the specifically authorized safe projection or governed document bytes; raw internal forms are forbidden | only where the schema/object contract explicitly requires it; assembled prompts and raw external payloads are never persisted | forbidden |
| `secret` | passwords, credential plaintext, session/composer tokens, encryption keys | forbidden | only approved password/token hashes or encrypted credential ciphertext; keys remain outside product tables | forbidden |

Classification follows the value through copies, failures, fixtures and derived artifacts; renaming a field never downgrades it. Unknown values default to the more restrictive class. A public mapper is an allowlist and may not serialize an ORM model, adapter payload or exception wholesale.

## Outbound port catalog

| Port | Typed responsibility | Required boundary behavior |
| --- | --- | --- |
| clock and ID providers | UTC time, opaque product IDs, request/trace/operation IDs | injectable and deterministic in tests; no browser-supplied authority |
| credential cipher | encrypt/decrypt configured provider credentials | plaintext is call-scoped, never logged, and safe failure reveals no configuration detail |
| governed object store | stream put/get/range/delete for versioned source and derived objects | bounded I/O, opaque keys, integrity metadata, idempotent delete and reconciliation |
| parser | source bytes plus frozen parser input -> canonical prepared result | typed normalized blocks/images only; bounded timeout; raw provider payload stays private |
| domain runtime controller | start/stop/delete/readiness for one domain generation | stable operation key, bounded timeout, typed uncertain outcome and generation-aware reconciliation |
| LightRAG index | submit/readiness/cancel/delete of a provenance-marked handoff | per-domain isolation, stable content identity, idempotency and mapped safe failures |
| scoped retrieval | one authorized domain/query -> private typed candidates | bounded result/time budget; no raw hit crosses the service/public boundary |
| synthesis | approved model input -> bounded token/result stream | timeout/cancel semantics and typed safe failure; provider payload and assembled context stay private |
| operational telemetry | allowlisted log/metric/trace emission | best-effort only where permitted, bounded cardinality, no product read API and no content/secret values |

Adapters implement ports and never authorize, commit product state, choose a domain, or expose provider/runtime payloads. Services freeze inputs and commit operation intent before an external call; the call runs outside the database transaction with bounded timeouts and a stable idempotency key. Timeout or transport loss with an unknown remote outcome enters reconciliation before retry. Selecting a concrete production object store, parser/provider behavior, controller topology or unsupported queue requires the owning architecture decision.

## State-machine convention

1. Each persisted state/status field has one closed vocabulary and one owning service; routes, repositories, adapters and browser code do not assign transitions.
2. The service reauthorizes and locks current state in the committing transaction, validates the transition, advances the generation/fence, persists operation intent and required audit atomically, then returns an authoritative projection.
3. External work occurs after intent commit. Workers claim with PostgreSQL locking, lease owner/expiry and the frozen generation; stale or lease-lost completion is a no-op.
4. Success, failure and cancellation finalize only from an allowed active state and current generation. An uncertain remote outcome is non-terminal until reconciliation.
5. Delete transitions fence reads/retrieval first and never restore access during cleanup retry. Redaction/invalidation precedes destructive remote/object/local cleanup.
6. Invalid or concurrent transitions return the contracted conflict/error and current safe state where specified; they never queue invisibly or infer success from absence.
7. Public DTO/SSE state is projected from committed server truth. Client optimism is limited to reversible presentation state and must reconcile after every mutation.

The diagrams above define the shared Phase 1 lifecycle vocabulary. Exact transition tables, error codes, retry limits and PostgreSQL race proof land with P3-P7. Existing constants, protocols and state assignments in the lifted code are characterization evidence only until those packages map them to this convention.
