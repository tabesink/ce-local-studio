# HTTP API Catalog

This catalog is the production v1 browser contract. Paths are relative to `/api/v1` except health. Public fields/enums are closed by `dto-schema-catalog.md`; evidence/document fields are closed by `document-and-evidence-contract.md`. OpenAPI generated from registered routes must match them. A route absent here is not available to the frontend.

## Global contract

| Concern | Rule |
| --- | --- |
| Encoding | strict camelCase JSON; UTF-8; unknown fields rejected |
| Authentication | FastAPI `ce_session` HttpOnly cookie; never JSON/bearer storage |
| CSRF | every unsafe method requires valid Origin plus `ce_csrf`/`X-CSRF-Token` double submit |
| Request ID | server generates an opaque 1..80 value for every response, emits exactly `X-Request-ID`, ignores caller values as authority, and repeats the same value in errors |
| Error | `{ "error": { "code": "closed_code", "message": "Safe text.", "requestId": "req_...", "fields": {} } }`; all four inner fields are required |
| IDs/time | opaque case-sensitive refs; RFC 3339 UTC timestamps use `Z` at whole-second precision |
| Pagination | `limit` default 50, max 100; opaque `cursor`; stable `(createdAt,id)` ordering; `{items,nextCursor}` naming may be capability-specific |
| Concurrency | mutable records may return strong `ETag`; `If-Match` is required only where the endpoint row explicitly lists it; when required, missing is `428` and stale is `409 stale_revision` |
| Idempotency | chat uses `clientRequestId`; create/operation routes use `Idempotency-Key` where listed; same key+fingerprint reuses result, mismatch is `409 idempotency_conflict` |
| Caching | authenticated JSON, SSE, preview bytes, and errors are `private, no-store`; health may be `no-store` |
| Content | JSON bodies default 1 MiB; turn 4,000 chars; query 2,000; upload limit is configured and never below the accepted fixture size |

`401 unauthenticated`, `403 forbidden`, `404 *_not_found`, `409 *_conflict`, `422 validation_error`, `429 rate_limited`, and `503 capacity_unavailable` keep stable meanings. Ownership-sensitive resources return `404`, not `403`. `fields` names invalid public fields only and never echoes submitted content.

The production HTTP namespace is exactly `/api/v1`; it is not deployment-configurable and no alternate prefix or unversioned product alias is registered. Health remains outside that namespace. The closed HTTP `ErrorCode` union is defined in `dto-schema-catalog.md`.

Roles: `P` public, `M` authenticated member or administrator, `O` owning member, `A` administrator. Protected mutations write their audit row in the same transaction or return `503 audit_unavailable` with no product change.

## Health and identity

| Method/path | Role | Request -> success | Notes |
| --- | --- | --- | --- |
| `GET /health/live` | P | none -> `200 {status:"live"}` | process only |
| `GET /health/ready` | P/internal | none -> `200 {status:"ready"}` or `503` | safe aggregate; no topology |
| `GET /auth/csrf` | P | none -> `200 {csrfToken}` | sets/rotates pre-auth CSRF cookie |
| `POST /auth/login` | P | `{username,password}` -> `200 {user}` | pre-auth CSRF; rotates session+CSRF; generic failure |
| `GET /auth/me` | M | none -> `200 {user:{id,displayName,role}}` | authoritative navigation identity |
| `POST /auth/logout` | M | empty -> `204` | revoke then expire cookies |
| `GET /admin/users` | A | cursor filters -> `200 {users,nextCursor}` | safe identity/status only; no hashes/sessions |

## Runtime settings and domains

| Method/path | Role | Success | Preconditions/idempotency |
| --- | --- | --- | --- |
| `GET /admin/runtime-settings` | A | `200 {providers,modelProfiles,runtimeSettings}` | secrets project as configured/not configured |
| `PUT /admin/runtime-settings/providers/{kind}` | A | `200 {provider}` | `If-Match`; replacement credential only; A-01 |
| `POST /admin/runtime-settings/model-profiles` | A | `201 {modelProfile}` | `Idempotency-Key`; closed catalog |
| `PATCH /admin/runtime-settings/model-profiles/{id}` | A | `200 {modelProfile}` | `If-Match`; used embeddings immutable; A-02 |
| `DELETE /admin/runtime-settings/model-profiles/{id}` | A | `204` | unused/non-default only |
| `PATCH /admin/runtime-settings` | A | `200 {runtimeSettings}` | `If-Match`; provider readiness rechecked |
| `GET /domains` | M | `200 {domains}` | query-eligible domains only; M-02 |
| `POST /admin/domains` | A | `201 {domain}` | `Idempotency-Key`; starts `stopped` |
| `GET /admin/domains` | A | `200 {domains,nextCursor}` | safe lifecycle projection |
| `GET /admin/domains/{domainId}` | A | `200 {domain}` | includes `ETag` |
| `GET /admin/domains/{domainId}/status` | A | `200 {domain,activeOperation}` | polling DTO |
| `POST /admin/domains/{domainId}/start` | A | `202 {operation}` | key+lock; one generation; A-03/A-05 |
| `POST /admin/domains/{domainId}/stop` | A | `202 {operation}` | key+lock; immediate query fence; A-04 |
| `DELETE /admin/domains/{domainId}` | A | `202 {operation}` | `If-Match`+key; deleting fence; A-10 |
| `GET /admin/domains/{domainId}/operations` | A | `200 {operations,nextCursor}` | newest stable order |

Lifecycle conflicts return the current safe state and `domain_operation_in_progress` or `domain_state_conflict`; they never queue invisibly.

## Source administration and member library

| Method/path | Role | Success | Contract |
| --- | --- | --- | --- |
| `POST /admin/domains/{domainId}/sources` | A | `201 {source,operation}` | streaming multipart `file`; server hash/sniff; key; A-06 |
| `GET /admin/domains/{domainId}/sources` | A | `200 {sources,nextCursor}` | lifecycle/index summary |
| `GET /admin/domains/{domainId}/sources/{sourceId}` | A | `200 {source}` | safe metadata + `ETag` |
| `GET /admin/domains/{domainId}/sources/{sourceId}/outline` | A | `200 {items}` | structure, no canonical text |
| `GET /admin/domains/{domainId}/sources/{sourceId}/operations` | A | `200 {operations,nextCursor}` | preparation/delete history |
| `POST /admin/domains/{domainId}/sources/{sourceId}/retry` | A | `202 {operation}` | key; frozen parser; A-07 |
| `POST /admin/domains/{domainId}/sources/{sourceId}/cancel` | A | `200 {operation}` | `If-Match`; generation fence |
| `POST /admin/domains/{domainId}/sources/{sourceId}/index/retry` | A | `202 {source}` | key; stable rendered-content identity; A-08 |
| `POST /admin/domains/{domainId}/sources/{sourceId}/index/cancel` | A | `200 {source}` | remote absence verified before terminal |
| `DELETE /admin/domains/{domainId}/sources/{sourceId}` | A | `202 {operation}` | `If-Match`+key; fence/redact/cleanup; A-09 |
| `GET /documents` | M | `200 {documents,nextCursor}` | authorized/query-eligible library; `domainId`,`query`,`cursor`,`limit` |
| `GET /documents/{documentRef}` | M | `200 {document}` | opaque public ref; current access rechecked |
| `GET /documents/{documentRef}/content` | M | `200/206 application/pdf` | `Range`; governed preview; never redirect/object key |
| `GET /evidence/{evidenceRef}/location` | O | `200 {evidence,document,anchor}` | turn ownership + current source eligibility; M-04/M-05 |

Document/evidence DTOs and byte-range behavior are normative in `document-and-evidence-contract.md`.

## Retrieval, conversations, and governed context

| Method/path | Role | Success | Contract |
| --- | --- | --- | --- |
| `POST /domains/{domainId}/evidence` | M | `200 RetrievalEvidenceResponseDto` | `RetrievalEvidenceRequestDto`; authenticated membership plus current query eligibility; bounded safe projection; no mutation |
| `GET /conversations` | O | `200 {conversations,nextCursor}` | current user's rows only |
| `POST /conversations` | M | `201 {conversation}` | optional `{title}`; key supported |
| `GET /conversations/{conversationId}` | O | `200 {conversation,turns}` | redacted projections omit answer/evidence |
| `PATCH /conversations/{conversationId}` | O | `200 {conversation}` | `If-Match`; `{title}` |
| `DELETE /conversations/{conversationId}` | O | `204` | `If-Match`; serialize against submit; M-08 |
| `POST /conversations/{conversationId}/turns:stream` | O | `200 text/event-stream` | `{clientRequestId,message,domainId?,composerRefTokens?}`; CSRF; pre-stream errors JSON |
| `GET /conversations/{conversationId}/turns/{turnId}/events` | O | `200 text/event-stream` | `after` last applied sequence; active resume or replay |
| `POST /conversations/{conversationId}/turns/{turnId}:cancel` | O | `202 {turn}` | explicit cancel; idempotent; disconnect alone is not cancel |
| `POST /composer-refs:discover` | M | `200 {refs}` | domain/conversation-scoped opaque one-use tokens; max 25 |

The server computes the stream-start fingerprint from the normalized message, effective route/domain, and ordered resolved refs; no request fingerprint field is accepted. Same request ID/server-computed fingerprint attaches or replays without provider/retrieval work; different effective input returns `idempotency_conflict` (`M-10`). A domain question without a domain returns `domain_required`; no grounded evidence never falls back to direct LLM.

For `POST /domains/{domainId}/evidence`, mapped candidates retain first-valid order after block deduplication and receive dense response-local citation labels. A valid bounded retrieval with no surviving mapped Evidence returns `200 {"result":"no_grounded_context","evidence":[]}`. The closed failures are: unknown domain `404 not_found`; stopped, deleting, transitioning, runtime-not-ready, or no-eligible-source domain `409 domain_not_query_eligible`; admission saturation `503 capacity_unavailable`; dependency timeout, unavailability, malformed output, or health exception `503 dependency_unavailable`; and invalid input `422 validation_error`. Success and failure are `private, no-store`.

## Deferred operator surfaces

Phase 1 exposes no audit-browser, diagnostic-browser, raw/runtime-log, log-session, usage/cost, analytics, Server-status, runtime-node dashboard, export, or storage-browser endpoint. Internal transactional audit writes, safe structured logs, service metrics, and health checks are operational-safety controls rather than browser capabilities. Candidate Phase 2 contracts are isolated in `../future/observability-layer.md`.

There is no graph DTO in Phase 1. `/database-visualize` remains unavailable until a safe product-owned graph contract is approved; the frontend must show a deliberate unavailable state, not call LightRAG directly.

## Examples

```http
POST /api/v1/conversations/conv_demo/turns:stream
Content-Type: application/json
X-CSRF-Token: csrf_value

{"clientRequestId":"req-demo-001","message":"Where is the relief valve?","domainId":"domain_manuals"}
```

```json
{
  "error": {
    "code": "domain_not_query_eligible",
    "message": "The selected domain is not available.",
    "requestId": "req_server_01",
    "fields": {}
  }
}
```

Legacy pilot paths and event shapes are not aliases by default. If temporary compatibility is approved, it is server-side, visible in safe internal logs, time-bounded, and excluded from new frontend code.
