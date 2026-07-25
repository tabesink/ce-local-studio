# P6-02 Evidence Contract Decision

Date: 2026-07-25

Status: approved by the user on 2026-07-25

## Approved decision

The user approved the following public contract for the read-only
`POST /api/v1/domains/{domainId}/evidence` response before P6-02 changes the
route, service, generated artifacts, or browser client.

The recommended decision is:

1. Keep the endpoint read-only and non-persisting.
2. Add a distinct closed `RetrievalEvidenceItemDto` that has no evidence ID.
3. Return response-scoped `citationLabel`, `sourceLabel`, `excerpt`, `kind`,
   `documentRef`, `documentLabel`, and nullable `anchor`.
4. Preserve first-valid mapped-candidate order after block deduplication and
   assign dense citation labels `[1]`, `[2]`, and so on. Durable citation
   stability begins only when P7 persists turn evidence.
5. Treat authenticated membership plus current domain/source query eligibility
   as the Phase 1 authorization rule. Do not add a domain ACL model.
6. Map public failures only to the approved closed vocabulary:
   - unknown domain: `404 not_found`;
   - stopped, deleting, transitioning, runtime-not-ready, or no-eligible-source
     domain: `409 domain_not_query_eligible`;
   - retrieval admission saturation: `503 capacity_unavailable`;
   - retrieval timeout, unavailable dependency, or malformed dependency result:
     `503 dependency_unavailable`;
   - invalid question: `422 validation_error`;
   - a valid bounded retrieval with no surviving mapped Evidence:
     `200 {"result":"no_grounded_context","evidence":[]}`.
7. A nullable anchor means the server cannot prove a page/section/region for
   this stateless retrieval result. The service must not fabricate page 1 or a
   `fallback:"page"` anchor.

The rejected alternative was to remove or defer this standalone endpoint until P7 can
persist owner-bound turn evidence. Making the endpoint persist unattached
evidence is not recommended because it contradicts its approved no-mutation
contract and the conversation-owned evidence schema.

## Blocking contradiction

`docs/contracts/http-api-catalog.md` defines
`POST /domains/{domainId}/evidence` as a bounded safe projection with no
mutation. `docs/contracts/document-and-evidence-contract.md` defines the only
approved `EvidenceItemDto.id` as a random public reference stored on one
persisted, owner-bound turn evidence row. P7-01 owns that persistence boundary.

The read-only P6 endpoint has no turn and creates no evidence row. It therefore
cannot emit a compliant `EvidenceItemDto.id`. A database/block ID, a derived
hash, an ephemeral random value, or a source document ref would each violate the
reference contract or create an unresolvable evidence link.

No approved stateless retrieval item/result DTO exists in
`docs/contracts/dto-schema-catalog.md`. The lifted
`EvidenceItemResponse {excerpt,sourceLabel}` in
`app/context_engine/api/routes.py` and its generated OpenAPI component are
implementation evidence, not product authority.

## Secondary contract gaps

### Anchor truth

Canonical blocks have nullable page and section metadata. Source images have a
nullable page number but no normalized region. The full `EvidenceAnchorDto`
requires `pageNumber` and has no representation for "no page can be proved",
even though the document contract describes that fallback state. P6-02 cannot
invent page 1 as authoritative location data.

### Closed HTTP failures

The current service emits `domain_not_found`, `domain_runtime_unavailable`, and
`domain_no_eligible_sources`. None belongs to the approved Phase 1 HTTP
`ErrorCode` union. Exact route mapping must be approved with the projection so
the handler does not leak an internal lifecycle or dependency code.

### Durable evidence tail

The current `conversation_turn_evidence_refs` shape stores public ref, order,
private source/block linkage, citation label, source label, and excerpt. The
Evidence lifecycle contract also requires safe kind/anchor projection to be
copied for durable replay. That migration and ownership proof remain P7-01
work; P6-02 must not create unattached durable rows to work around the
stateless-endpoint conflict.

## Evidence reviewed

- `AGENTS.md` authority and public-contract stop conditions
- `docs/prd.md` FR-05 and member permissions
- `docs/interaction-behavior-prd.md` M-02, M-03, M-04, M-05, M-06, C-01,
  C-02, and C-03
- `docs/contracts/http-api-catalog.md`
- `docs/contracts/dto-schema-catalog.md`
- `docs/contracts/document-and-evidence-contract.md`
- `docs/database-schema.txt`
- `docs/architecture/data-and-lifecycle.md`
- `docs/architecture/as-built-gaps-and-decisions.md`
- `app/context_engine/api/catalog_schemas.py`
- `app/context_engine/api/routes.py`
- `app/context_engine/services/evidence.py`
- `app/context_engine/services/chat_turns.py`
- `app/context_engine/models.py`
- generated OpenAPI and browser types under `app/contracts/` and
  `app/client/src/lib/api/generated/`

## Implementation boundary after approval

After the decision, P6-02 can produce an implementation-ready plan covering:

- one closed authoritative response/request schema and generated-client update;
- allowlisted public mapping from P6-01 internal mapped Evidence;
- sanitized labels, canonical excerpt normalization and the 500-character cap;
- deterministic block deduplication/order/citation assignment;
- current query-eligibility reauthorization and private no-store response
  headers;
- approved error envelopes with no raw question, hit, private ID, provider
  detail, or exception text;
- unit, HTTP, generated-contract, privacy, and PostgreSQL fence/isolation proof.
