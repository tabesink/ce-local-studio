# API and Integration Flows

## Public transport contract

- Health: `GET /health/live`, `GET /health/ready`.
- Version prefix: `/api/v1`.
- Errors: one canonical safe JSON envelope containing the server request ID.
- Authentication: opaque HttpOnly cookie; no browser token persistence.
- Streaming start/attach: fetch-stream `POST /conversations/{id}/turns:stream` uses a client request ID and request fingerprint.
- Streaming resume/replay: `GET /conversations/{id}/turns/{turn_id}/events?after={sequence}`; an expired cursor returns `410 cursor_expired` and may include a safe terminal snapshot.

## Route groups

### Authentication

`POST /auth/login`, `GET /auth/me`, `POST /auth/logout`; administrator user listing is read-only at `/admin/users`.

### Member domains, evidence, chat, and governed context

- `GET /domains`
- `POST /domains/{domain_id}/evidence`
- conversation CRUD under `/conversations`
- streamed turn start/attach at `/conversations/{conversation_id}/turns:stream`
- authorized turn resume/replay at `/conversations/{conversation_id}/turns/{turn_id}/events`
- safe context discovery at `POST /composer-refs:discover`

### Runtime and content administration

- Runtime settings/model-profile CRUD under `/admin/runtime-settings`.
- Domain create/list/detail/status/start/stop/delete/operations under `/admin/domains`.
- Source upload/list/detail/outline/operations/retry/cancel/delete under each admin domain.
- No audit, diagnostic, runtime-log, usage, or Server-status read route is registered in Phase 1; those operator surfaces are deferred to Phase 2.

## Ingestion sequence

```text
Admin UI -> API: multipart source upload
API -> Postgres/storage: validate and persist pending source + operation
Worker -> parser: parse with frozen parser kind and private live credential
Worker -> Postgres: replace canonical blocks/images atomically, mark prepared
Index worker -> LightRAG: idempotent versioned block handoff
Index worker -> Postgres: poll and persist ready/failure under lease+generation fence
```

## Chat sequence

```text
Member UI -> API: message, optional domainId, clientRequestId, composer tokens
API -> Postgres: ownership, idempotency, ref validation, running turn
API -> intent gate: select direct_llm or domain_rag
domain_rag -> eligibility -> LightRAG -> local provenance mapper -> Evidence
API -> provider: private bounded prompt assembly and synthesis
API -> UI: safe SSE events
API -> Postgres: durable terminal projection for replay/redaction
```

## Delete sequence

```text
Admin -> API: delete source/domain
API -> Postgres: immediately fence queries and create/claim operation
Service -> chat/context: redact affected turns and invalidate governed refs
Service -> LightRAG/runtime/storage: delete derived and original artifacts
Service -> Postgres: remove remaining owned rows and write audit outcome
```

## Integration adapter contracts

- Parser adapters return one canonical parser-independent representation.
- LightRAG adapter accepts rendered blocks and returns private retrieval candidates; only mapped Evidence crosses into product services.
- Model adapter accepts backend-assembled prompts and streams tokens/terminal metadata.
- Runtime controller receives trusted backend configuration only.
- Tracing is optional and content-free; failure must not change product correctness.
