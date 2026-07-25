# Document and Evidence Contract

This contract makes evidence-to-viewer navigation implementable without exposing source storage or retrieval internals. It is normative for `M-04`, `M-05`, `M-06`, `M-11`, `C-02`, and `C-03`.

## Reference model

| Reference | Scope | Lifetime | Rule |
| --- | --- | --- | --- |
| `documentRef` | one Source Document | stable while the source exists | random URL-safe public identifier stored separately from private `source_documents.id`; never encodes object key/path |
| `evidenceRefId` | one persisted turn evidence row | conversation owner | random public ref stored separately from the private evidence-row ID; resolves privately to document/block |
| `previewVersion` | one governed PDF representation | until replaced/deleted | opaque version used only for safe `ETag`; not an object-store version/key |

Add unique non-null `public_ref` columns to `source_documents` and `conversation_turn_evidence_refs` before enabling member document routes. Backfill with cryptographically random values; do not expose either row primary key as a shortcut. A ref grants no access by itself.

## Evidence item

Chat, conversation detail, and evidence-location responses use the same projection:

```json
{
  "id": "ev_figure_01",
  "citationLabel": "[1]",
  "sourceLabel": "Pump Service Manual",
  "excerpt": "Figure 4 shows the relief valve downstream of the pump.",
  "kind": "figure",
  "documentRef": "doc_7m1y...",
  "documentLabel": "pump-service-manual.pdf",
  "anchor": {
    "pageNumber": 18,
    "region": {"x":0.12,"y":0.24,"width":0.66,"height":0.41},
    "sectionLabel": "4.2 Relief valve",
    "fallback": "page"
  }
}
```

| Field | Rule |
| --- | --- |
| `id` | turn-scoped evidence ref; unique within turn |
| `citationLabel` | `[1]`, `[2]`, ... stable for persisted turn |
| labels | sanitized safe display metadata; never used as keys |
| `excerpt` | mapped canonical text, max 500 characters; not raw LightRAG text |
| `kind` | `text`, `table`, or `figure` |
| `documentRef` | approved opaque ref for authorized viewer navigation |
| `anchor.pageNumber` | one-based integer in governed preview |
| `anchor.region` | optional normalized preview-page rectangle |
| `anchor.sectionLabel` | optional safe label, max 160 characters |
| `anchor.fallback` | `region`, `section`, or `page`; strongest anchor the server can prove |

Coordinates use the rendered page crop box with origin at top-left. `x`, `y`, `width`, and `height` are decimals in `[0,1]`; width/height are positive; the rectangle must remain within the page. They are presentation hints, not authorization or persistence identities.

### Stateless retrieval Evidence

`POST /domains/{domainId}/evidence` returns `RetrievalEvidenceItemDto`, not the persisted `EvidenceItemDto` above. It has the same safe `citationLabel`, labels, canonical excerpt, kind, document ref, and anchor projection but no `id`. The endpoint creates no Evidence row and its dense citation labels are stable only inside one response; durable citation stability begins when P7 persists turn Evidence.

Its `anchor` is nullable. Text, table, and figure blocks may project a one-based canonical block page; a bounded safe section label is included only when a page is provable. A figure without a block page may use linked Source Image page metadata only when all usable linked image page numbers agree. Conflicting or missing page metadata produces `anchor:null`; the server never fabricates page 1 or a region.

## Document metadata

`GET /documents/{documentRef}` returns:

```json
{
  "document": {
    "ref": "doc_7m1y...",
    "label": "pump-service-manual.pdf",
    "domain": {"id":"domain_manuals","displayName":"Equipment Manuals"},
    "contentType": "application/pdf",
    "previewKind": "pdf",
    "pageCount": 24,
    "updatedAt": "2026-07-17T12:00:00Z"
  }
}
```

Member library/document reads include only sources whose domain is authorized and query-eligible and whose source is not deleting. Admin lifecycle DTOs remain under `/admin/*`; member DTOs omit parser/index errors, hashes, storage, private IDs, and operations. `previewKind` is `pdf` or `unavailable`.

Original PDFs may be the governed preview after validation. DOCX/Markdown/text require a deterministic server-generated PDF preview before `previewKind=pdf`; the original format is never sent to an inline PDF renderer. Preview generation records source hash, renderer version, page mapping, object checksum, and version privately.

## Evidence location resolution

`GET /evidence/{evidenceRefId}/location` rechecks conversation ownership, evidence non-redaction, source/domain access, source query eligibility, and preview availability, then returns:

```json
{
  "evidence": {"id":"ev_figure_01","citationLabel":"[1]","kind":"figure"},
  "document": {"ref":"doc_7m1y...","label":"pump-service-manual.pdf","previewKind":"pdf","pageCount":24},
  "anchor": {"pageNumber":18,"region":{"x":0.12,"y":0.24,"width":0.66,"height":0.41},"sectionLabel":"4.2 Relief valve","fallback":"region"}
}
```

The evidence card may carry this same safe projection for immediate navigation; the document route still resolves it again. URL state is `/documents?document=<documentRef>&evidence=<evidenceRefId>&page=18`. The server ignores browser-supplied page/region for authority. The client prefers the freshly resolved anchor and treats URL page as a loading hint only.

Fallback order:

1. valid region: open page, fit region with margin, draw non-content-obscuring highlight;
2. valid page plus section: open page and focus the matching safe section marker;
3. page only: open page and show `Exact location unavailable`;
4. no provable page: open document at page 1 and show `Location unavailable`.

Never guess another document, fuzzy-match a filename, or use raw PDF text search as authoritative evidence mapping.

## Governed PDF delivery

`GET /documents/{documentRef}/content` returns only the authorized governed PDF preview.

| Request/result | Required response |
| --- | --- |
| no `Range` | `200`, `Content-Type: application/pdf`, bounded full body |
| valid single byte range | `206`, exact `Content-Range`, `Content-Length`, `Accept-Ranges: bytes` |
| unsatisfiable/multiple range | `416`, `Content-Range: bytes */<length>` |

Headers include `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff`, sanitized `Content-Disposition: inline; filename="...pdf"`, and a strong opaque `ETag` derived from the governed preview checksum/version. The API streams from object storage through its authorized boundary; it never returns a presigned URL, redirect, bucket name, object key, filesystem path, or storage error.

The BFF preserves range and abort semantics. Browser code releases PDF workers, requests, `ArrayBuffer`s, and blob URLs when the viewer closes, identity changes, or evidence becomes unavailable.

## Atomic mapping and lifecycle

- Preparation publishes blocks, image metadata, preview, page map, and preview version as one generation. A reader sees the prior complete generation or the new complete generation, never mixed pages/anchors.
- Index handoff embeds private provenance markers; retrieval candidates become Evidence only after mapping to an eligible local block in the selected domain.
- Evidence persistence copies safe labels/excerpt/kind/anchor projection and retains private linkage for authorization/redaction. Citation labels are assigned after final deterministic evidence ordering.
- Replacing a preview without changing source content is allowed only if anchor remapping succeeds or affected locations degrade explicitly to page fallback.
- Deletion first fences library/content/location reads, then redacts turns and invalidates governed refs, then performs remote/object cleanup. Cleanup retry never restores access.

## Errors and browser behavior

| Situation | HTTP/code | UI result |
| --- | --- | --- |
| unknown or cross-owner evidence | `404 evidence_not_found` | safe unavailable state |
| unknown/unauthorized document | `404 document_not_found` | close viewer; no existence leak |
| stopped/deleting source or changed authorization | `410 evidence_unavailable` | `Evidence no longer available`; invalidate blob |
| preview not ready/unsupported | `409 document_preview_unavailable` | metadata remains visible; viewer closed |
| object/preview dependency failure | `503 document_content_unavailable` | retry action + request ID |
| malformed range | `416 range_not_satisfiable` | PDF client retries without invalid range once |

Opening evidence moves focus to the viewer heading/anchor. Return-to-turn records only `{conversationId,turnId,evidenceRefId}` in safe history state and returns focus to the originating card. Viewer position is per tab and never written to shared server state (`C-03`).

## Required tests

- `M-04`: figure card changes route, opens page 18, focuses the normalized region, and returns to the card.
- `M-05`: text/table anchors use semantic page/section fallback across viewport changes.
- `M-06`: a late location response cannot replace the current turn selection.
- `M-11`: deletion makes location/content unavailable, redacts replay, closes the viewer, and defeats browser/BFF/CDN cache.
- `C-03`: two users/tabs open different anchors without state or byte leakage.
- Contract tests cover 200/206/416, `If-Range`, abort, content headers, filenames with control characters, wrong-domain refs, altered URL coordinates, partial object-store failure, and preview generation swap.
