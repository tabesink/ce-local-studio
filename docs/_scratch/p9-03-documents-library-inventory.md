# P9-03 Documents Library Preview Inventory

Date: 2026-07-27

Owner: P9-03

Status: DONE — inventory complete before behavior changes

Requirements and decisions: R1–R13; KTD1–KTD10; M-04/M-05/M-06/M-11;
C-03; FR-04/FR-05/FR-10; DRIFT-04/DRIFT-14;
`docs/plans/2026-07-27-010-feat-documents-library-preview-plan.md`.

## Scope

- Inventory retain/modify/replace/add/defer for member document routes,
  documents UI, BFF Range/`If-Range`, graph fetch, chat Library flag, admin
  outline, object-store range, delete fences, and DRIFT-04/14 before U2–U7.
- Pin KTD1 (backend member APIs in slice), KTD2 (dual-role `/documents`),
  KTD3 (admin outline in), KTD4 (PDF-original preview; non-PDF unavailable),
  KTD5 (DOCX/MD/text/PPT viewers → future), KTD6 (member list SoT + admin
  ops by `documentRef`), KTD7 (return URL `conversation`/`turn`/`evidence`),
  KTD8 (local proof altitude), KTD9 (graph zero product-data requests),
  KTD10 (inventory-first; one OpenAPI regen with four routes).
- Confirm four catalog GETs are the only `authoritative - registered`
  contract-gate delta.
- Flag blockers: none — `get_range` and admin outline exist.

## Disposition register

| Surface | Prior evidence | Disposition | P9-03 target |
| --- | --- | --- | --- |
| `GET /documents` (+ detail/content) | Catalogued; unregistered in `routes.py` / OpenAPI paths | add | Thin handlers → `services/documents.py`; `DocumentSummaryDto` only |
| `GET /evidence/{evidenceRef}/location` | Catalogued; unregistered; no service | add | Ownership + non-redaction + eligibility + preview readiness |
| `test_generated_contract_gate.py` delta | Exactly those 4 GETs allowed as missing | modify | Empty after registration + OpenAPI regen |
| Admin outline route | `admin_get_source_outline` registered | retain | Admin-only; no member outline API |
| `source_outline()` | Structure only, no canonical text | retain | Wire UI on dual-role page |
| `object_storage.get_range` | Protocol + filesystem + unit tests | retain | Stream PDF `200/206/416` |
| `DocumentSummaryDto` | In `catalog_schemas.py` / OpenAPI components | retain | Wire list/detail; PDF→`previewKind=pdf`; else `unavailable` |
| Location response envelope | Spec JSON only; no catalog class | add | Closed envelope for OpenAPI regen |
| `DocumentsPage.tsx` | Admin monolith; members unavailable; preview stubbed | replace | Member library+PDF primary; admin ops/outline gated |
| `features/documents/api.ts` | Lifted `SourceDocument` (hashes, private id) | replace | Generated `AdminSourceDto` / `DocumentSummaryDto`; If-Match |
| `PdfPreview.tsx` | Present; unused by page | retain | Wire for `previewKind=pdf`; parent owns blob lifecycle |
| `libraryDeepLink.ts` | Chat-return `conversationId`/`turnId` only | modify | Parse `document`/`evidence`/`page`; align return href |
| `LIBRARY_SURFACE_AVAILABLE` | `false` in `documentsDeepLink.ts` | modify | Flip in U6 after content/location work |
| `GraphPage.tsx` | Calls `listMemberDomains` + selector | replace | Static unavailable; zero product-data requests |
| BFF `bff-proxy.ts` | `range` allowlisted; **`if-range` absent** | modify | Add `if-range`; keep Range/`206`/`ETag` passthrough |
| `documents-preview.spec.ts` | Asserts deliberate unavailability | replace | Library, PDF preview, denial, graph no-request |
| DRIFT-04 | `IN_PROGRESS` graph no-request open | modify | Close no-request half after GraphPage rewrite |
| DRIFT-14 | `IN_PROGRESS` member routes remain | modify | Close member half after routes + Range proofs |
| Delete fence (P7-05) | State=deleting + redact before cleanup | retain | Location/content fail closed (M-11) |
| Upload allowlist | pdf / plain / markdown / docx — no pptx | retain | Non-PDF/PPT viewers deferred (KTD5) |
| Member documents service | Absent | add | `services/documents.py` list/detail/content/location |
| Non-PDF / PPT viewers | Contract: `unavailable` / `409` | defer | Future brief |
| Region highlight fidelity | Anchors often lack `region` | defer | Page/section fallback OK for exit |
| P12 ingress / visual matrix | Focused browser only | defer | P12 |
| Master-build-plan P9-03 | `NOT_STARTED` | modify | Flip DONE after evidence |

## Module inventory

| Path | Role |
| --- | --- |
| `app/context_engine/api/routes.py` | Admin outline registered; member document GETs absent |
| `app/context_engine/services/sources.py` | Admin sources, outline, delete enqueue |
| `app/context_engine/services/documents.py` | **Absent** — create in U2/U3 |
| `app/context_engine/adapters/object_storage.py` | `get_range` ready |
| `app/context_engine/api/catalog_schemas.py` | `DocumentSummaryDto` present; location envelope missing |
| `app/client/src/features/documents/DocumentsPage.tsx` | Admin-ops page; member unavailable |
| `app/client/src/features/documents/api.ts` | Lifted admin source adapter |
| `app/client/src/features/documents/PdfPreview.tsx` | Unused PDF canvas |
| `app/client/src/features/documents/libraryDeepLink.ts` | Return-to-chat only |
| `app/client/src/features/chat-shell/documentsDeepLink.ts` | Opaque Library href; surface gated off |
| `app/client/src/features/graph/GraphPage.tsx` | Unavailable copy + domain fetch |
| `app/client/src/lib/server/bff-proxy.ts` | Range yes; If-Range no |
| `app/client/tests/e2e/documents-preview.spec.ts` | Unavailability assertions |
| `app/tests/test_generated_contract_gate.py` | Four-GET missing delta |

## Contract-gate delta (pre-U2)

Exact `authoritative - registered` allowlist today:

1. `GET /api/v1/documents`
2. `GET /api/v1/documents/{}`
3. `GET /api/v1/documents/{}/content`
4. `GET /api/v1/evidence/{}/location`

## Session-settled constraints

1. Backend member APIs in this slice (KTD1).
2. Dual-role `/documents` (KTD2).
3. Admin outline in (KTD3).
4. PDF originals as governed preview; non-PDF → `previewKind=unavailable` / `409` (KTD4).
5. DOCX/MD/text/PPT body viewers deferred to future (KTD5).

## Residuals (explicit)

| Residual | Owner |
| --- | --- |
| DOCX/MD/text/PPT governed viewers | Future brief |
| Figure region highlight when anchors lack `region` | Residual OK under page fallback |
| Deployed-ingress Range/cache/two-user isolation | P12 |
| Broader import-boundary CI | P9-05 |
| Settings Domain accordion | P9-04 BLOCKED |

## Sequencing

U1 (this inventory) → U2 list/detail → U3 content/location + BFF If-Range + OpenAPI regen → U4 member UI → U5 admin ops/outline → U6 graph + Library enable → U7 evidence/DRIFT/tracker.

## Blockers before U2

None. `get_range` and admin outline are present.
