# P1-07 Idempotency and Pagination Inventory

Date: 2026-07-28

Owner: P1-07

Status: DONE — inventory freeze before schema/service

Plan: `docs/plans/2026-07-28-007-feat-p1-07-idempotency-pagination-plan.md`

## Disposition legend

| Disposition | Meaning |
| --- | --- |
| retain-and-reverify | Existing behavior matches contract; re-prove in this slice |
| modify | Existing seam needs contract-aligned change |
| add | Missing seam; create in this slice |
| credit | Proven elsewhere; no change required beyond citation |
| residual | Named follow-up; not a P1-07 blocker |

---

## Credit (already present)

| Surface | Evidence | Disposition |
| --- | --- | --- |
| Chat turn `(conversation_id, client_request_id)` + fingerprint | `chat_turns._matching_existing_turn`; PG `test_postgres_turn_leases` M-10 | credit — out of HTTP Idempotency-Key scope |
| Error codes `idempotency_conflict`, `cursor_expired` | `api/public_schemas.py`; OpenAPI ErrorCode | credit |
| BFF forwards `idempotency-key` | `app/client/src/lib/server/bff-proxy.ts` | credit |
| `GET /conversations` keyset + owner-filter | `services/conversations.py` `list_conversations`; `test_conversations_service.py` | retain-and-reverify |
| `GET /documents` keyset | `services/documents.py` `list_documents`; `test_documents_service.py` | retain-and-reverify |
| Protected mutation helper | `services/audit.py` `commit_protected_mutation` | credit — replay must not re-call |

### Documents ordering residual

Catalog global rule: stable `(createdAt,id)`. Documents list uses `(updatedAt,id)` for library freshness. Disposition: **residual** — credit current keyset; do not re-sort in P1-07 unless trivial; name in evidence.

---

## Closed `route_class` enum (KTD9)

| route_class | Method/path | Fingerprint inputs (canonical JSON, then SHA-256) |
| --- | --- | --- |
| `conversation.create` | `POST /conversations` | `{"title": <normalized or null>}` |
| `model_profile.create` | `POST /admin/runtime-settings/model-profiles` | closed create body fields (name, profileKind, providerKind, modelName, vectorDimensions) |
| `domain.create` | `POST /admin/domains` | closed create body (id, displayName, embeddingProfileId) |
| `domain.start` | `POST /admin/domains/{domainId}/start` | `{"domainId": <id>}` |
| `domain.stop` | `POST /admin/domains/{domainId}/stop` | `{"domainId": <id>}` |
| `domain.delete` | `DELETE /admin/domains/{domainId}` | `{"domainId": <id>, "ifMatchVersion": <int>}` |
| `source.upload` | `POST /admin/domains/{domainId}/sources` | `{"domainId", "contentSha256", "displayFilename", "parserKind"}` — never raw bytes |
| `source.retry` | `POST .../sources/{sourceId}/retry` | `{"domainId","sourceId"}` |
| `source.index_retry` | `POST .../index/retry` | `{"domainId","sourceId"}` |
| `source.delete` | `DELETE .../sources/{sourceId}` | `{"domainId","sourceId","ifMatchVersion": <int>}` |

Principal scope: authenticated `users.id` (never session id). Header optional: absent → today’s non-keyed behavior.

---

## Idempotency-Key surfaces

| Route | Handler | Service | Current | Disposition |
| --- | --- | --- | --- | --- |
| `POST /conversations` | `post_conversation` | `create_conversation` | No header; always inserts | add |
| `POST .../model-profiles` | `admin_create_model_profile` | `create_model_profile` | No header | add |
| `POST /admin/domains` | `admin_create_domain` | `create_domain` | Natural id dedup only | add |
| `POST .../start` | `admin_start_domain` | `start_domain` | Active-op lock; no key replay | add |
| `POST .../stop` | `admin_stop_domain` | `stop_domain` | Active-op lock; no key replay | add |
| `DELETE .../domain` | `admin_delete_domain` | `enqueue_delete_domain` | If-Match only | add |
| `POST .../sources` | `admin_upload_source` | `upload_source_bytes` | SHA-256 `duplicate_source` | add |
| `POST .../retry` | `admin_retry_source` | `retry_source` | Always new op | add |
| `POST .../index/retry` | `admin_retry_source_index` | `retry_source_index` | Always new op | add |
| `DELETE .../source` | `admin_delete_source` | `enqueue_delete_source` | If-Match only | add |

**Not in set:** source/index cancel (`If-Match` only per catalog).

Shared store: **add** — no `http_idempotency_records` table/model/migration today. Alembic head to revise: `f1a8c3d04e92`.

---

## nextCursor list surfaces

| Route | Handler | Service | Current | Disposition |
| --- | --- | --- | --- | --- |
| `GET /conversations` | `get_conversations` | `list_conversations` | Real keyset; cursor+limit | retain-and-reverify |
| `GET /documents` | member documents | `list_documents` | Real keyset; `(updatedAt,id)` residual | retain-and-reverify |
| `GET /admin/users` | `admin_users` | inline select | Full list; **no** `nextCursor` | modify |
| `GET /admin/domains` | `admin_list_domains` | `admin_domain_list` | Stub `"nextCursor": None` | modify |
| `GET .../operations` (domain) | `admin_domain_operations` | `domain_operations` | Stub null | modify |
| `GET .../sources` | `admin_list_sources` | `list_sources` | Stub null | modify |
| `GET .../sources/.../operations` | `admin_source_operations` | `source_operations` | Stub null | modify |

### Cursor anchors

| List | Opaque cursor payload |
| --- | --- |
| conversations | `{version:1, conversationRef}` (existing) |
| documents | `{version:1, documentRef}` (existing) |
| admin users | `{version:1, userId}` — approved safe anchor = public `safe_user.id` |
| admin domains | `{version:1, domainId}` |
| domain operations | `{version:1, operationId}` (public operation id/ref as projected) |
| admin sources | `{version:1, sourceId}` / `documentRef` as projected |
| source operations | `{version:1, operationId}` |

Ordering target for admin lists: `(createdAt, id) DESC` per catalog.

---

## Counts

| Category | Count |
| --- | --- |
| Idempotency-Key catalog routes | 10 — all **add** |
| List routes with nextCursor | 7 — 2 retain-and-reverify, 5 modify |
| Durable HTTP idempotency store | **add** (greenfield) |

## Stop / non-goals frozen

- No user admin mutations
- No Redis/RQ
- No browser list UX
- No chat `clientRequestId` redesign
- Source cancel stays If-Match-only
