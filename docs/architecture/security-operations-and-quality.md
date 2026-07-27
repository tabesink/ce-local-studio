# Security, Operations, and Quality

## Trust boundaries

The browser is untrusted. It may submit opaque IDs/tokens and user content, but it cannot choose provider credentials, runtime targets, storage paths, LightRAG endpoints, Docker targets, controller commands, or authorization scope. Every route re-derives identity, ownership, role, target state, and domain compatibility from server data.

## Security controls

- Argon2 password hashes; hashed opaque session and composer tokens.
- HttpOnly cookie sessions with expiry/revocation and Secure/SameSite validation.
- Encrypted provider credentials with a required deployment encryption key.
- Admin and owner guards at route/service boundaries.
- Strict input lengths, MIME/size/hash checks, closed enums, and safe error mapping.
- Retrieval provenance validation prevents raw or cross-domain LightRAG results from becoming Evidence.
- CSP/same-origin proxy behavior should accompany the frontend deployment.
- Destructive operations are fenced and audited; protected mutations roll back when audit persistence fails.
- Conversation create, rename, and delete use the closed internal audit events `conversation.created`, `conversation.renamed`, and `conversation.deleted`; audit metadata excludes titles and conversation content.

## Phase 1 operational-safety baseline

Allowed operational dimensions include server request ID, private trace ID, safe operation/product IDs, route template, elapsed time, outcome, closed status/error code, and allowlisted numeric/boolean metadata. Exclude usernames/emails, filenames/titles when disallowed, prompts, questions, answers, excerpts, source text, provider payloads, raw hits, credentials, runtime targets, paths, stack traces, and browser bodies.

This baseline is server-side only: allowlisted logs, bounded service metrics, health/readiness, and transactional audit writes. Phase 1 does not build an observability store or expose logs, audit records, diagnostics, usage analytics, streams, exports, dashboards, or retention controls to the browser. Those capabilities require the Phase 2 contract in `../future/observability-layer.md`.

## Reliability model

- Database transactions protect multi-row invariants.
- Idempotency prevents duplicate chat/provider/retrieval work.
- Leases allow worker recovery; generations reject stale completions.
- Readiness is distinct from liveness and checks database/bootstrap viability.
- Query eligibility composes authorization, lifecycle, index, deletion, and runtime readiness.
- External integrations fail through safe stable error codes and never leak raw exceptions.

## Verification strategy

1. Unit-test pure validation, routing, state transitions, token hashing, redaction projection, and safe-field policies.
2. Service/DB tests prove ownership, constraints, transactions, leases/generations, idempotency, governed-ref consumption, and audit rollback.
3. API tests freeze OpenAPI and SSE payloads and exercise role/ownership denials.
4. Adapter contract tests use pinned parser/LightRAG/provider fixtures, including provenance and delete behavior.
5. Docker integration starts PostgreSQL, migrates, seeds, serves API/frontend, and proves health plus one core vertical path.
6. Frontend tests cover auth redirects, API error mapping, SSE state/replay, evidence selection, and role-aware navigation; production build and TypeScript checks are mandatory.
7. Security/privacy tests scan responses, logs, audit rows, traces, snapshots, and fixtures for forbidden fields/content.

## Deployment order and rollback

- Back up PostgreSQL and persistent source/runtime storage.
- Apply forward-compatible migrations before starting the matching API.
- Start API and verify readiness/bootstrap seeds before exposing frontend.
- Validate one administrator login, one member denial on admin routes, one domain lifecycle operation, and protected-mutation rollback when its required audit write fails.
- Roll back application images only while schema remains backward compatible. Destructive migration rollback requires an explicit restore plan; do not improvise down migrations for redaction/deletion data.
