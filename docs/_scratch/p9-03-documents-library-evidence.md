# P9-03 Documents Library Preview Evidence

Date: 2026-07-27

Slice: P9-03

Status: DONE (unit/HTTP/component/focused altitude; disposable-PG and P12 ingress deferred)

Plan: `docs/plans/2026-07-27-010-feat-documents-library-preview-plan.md`

Inventory: `docs/_scratch/p9-03-documents-library-inventory.md`

Authority: `docs/contracts/document-and-evidence-contract.md`,
`docs/contracts/http-api-catalog.md`, `docs/frontend/document-viewer-spec.md`,
`docs/frontend/route-and-workspace-spec.md`; FR-04/FR-05/FR-10; M-04/M-05/M-06/M-11; C-03.

## What landed

- Member APIs registered: `GET /documents`, `GET /documents/{documentRef}`,
  `GET /documents/{documentRef}/content`, `GET /evidence/{evidenceRef}/location`
  via `services/documents.py` + thin `routes.py` handlers.
- PDF originals serve as governed preview (`previewKind=pdf`) with `200/206/416`
  through object-store `get_range`; non-PDF → `previewKind=unavailable` /
  `409 document_preview_unavailable`.
- Location rechecks ownership, non-redaction, eligibility, preview readiness;
  wrong-owner `404`; deleting/redacted `410`.
- BFF forwards `If-Range` (plus existing `Range` / `Content-Range` / `ETag`).
- OpenAPI/TS regenerated; contract-gate delta for the four GETs is empty.
- Dual-role `/documents`: member library + PDF blob lifecycle primary; admin
  ops/outline role-gated with `If-Match` and structure-only outline.
- Inbound opaque deep links + return `/chat?conversation=&turn=&evidence=`.
- Chat `LIBRARY_SURFACE_AVAILABLE=true`; Open in Library navigates.
- `/database-visualize` static unavailable with zero product-data requests
  (DRIFT-04 no-request half).

## Commands

### Backend unit / HTTP / contract

```text
cd app
python -m pytest tests/test_documents_service.py tests/test_documents_http_contract.py tests/test_generated_contract_gate.py tests/test_authoritative_dto_components.py -q
```

Result (2026-07-27): all passed (41 tests in this focused set).

### BFF proxy

```text
cd app/client
node --experimental-strip-types --test tests/bff-proxy.test.mjs
```

Result: 5/5 passed (includes Range + If-Range).

### Frontend focused

```text
cd app/client
node --experimental-strip-types --test tests/documents-deep-link.test.mjs tests/graph-unavailable.test.mjs
npx vitest run tests/documentsDeepLink.test.ts tests/chat-inspector.test.tsx
node --test tests/chat.test.mjs
npx tsc --noEmit -p tsconfig.json
```

Result: 5 node deep-link/graph + 11 Vitest + 10 chat structural + clean typecheck.

Playwright e2e specs rewritten (`documents-preview.spec.ts`,
`source-ref-inspector.spec.ts`) but not executed against a live stack in this
closure (focused altitude; stack smoke remains P10/P12).

## Privacy assertions

- Member DTOs omit private source IDs, object keys, hashes, and paths
  (unit/HTTP leak checks).
- Library URLs carry only opaque `document` / `evidence` / `page` (and return
  `conversation` / `turn` / `evidence`).
- Admin outline items are structure-only (kind/label/level/pageNumber).
- PDF content responses use `Cache-Control: private, no-store`.

## Interaction-case trace (this altitude)

| Case | Evidence |
| --- | --- |
| M-04 / M-05 deep-link viewer | Location resolve + page fallback + Library enable + unit/UI tests |
| M-06 late location | DocumentsPage generation fence on location/content loads |
| M-11 open-panel denial | HTTP mapping for deleting/redacted location/content |
| C-03 tab isolation | Per-tab viewer state; no shared storage of blobs/selection |
| FR-04 / FR-05 | Opaque refs + reauth content/location |
| FR-10 graph unavailable | GraphPage zero-fetch + graph-unavailable test |

## Residuals / non-claims

| Residual | Owner |
| --- | --- |
| DOCX/MD/text/PPT governed viewers (PDF generator or approved text/slide preview) | Future brief — `docs/future/document-preview-formats.md` |
| Figure region highlight when anchors lack `region` | Residual OK (page/section fallback) |
| Disposable PostgreSQL documents race suite | Optional follow-up; unit/HTTP proven |
| Deployed-ingress Range/cache/two-user isolation | P12 |
| Import-direction / barrel CI validators | P9-05 |
| Settings Domain accordion / remaining DRIFT-04 navigation | P9-04 |
| Full visual matrix | P12-07 |
| Live Playwright stack run for rewritten e2e | P10/P12 |

## Tracker / DRIFT updates

- `docs/master-build-plan.md` P9-03 → DONE with this evidence link.
- DRIFT-14 member document/content/location half → DONE (this evidence).
- DRIFT-04 graph-unavailable no-request half → closed by P9-03; row stays
  IN_PROGRESS until P9-04 finishes remaining navigation residuals.
