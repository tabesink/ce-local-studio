# P4-05 Figure and Table Region Provenance Evidence

Date: 2026-07-28

Slice: P4-05

Status: DONE (unit/HTTP/component/focused altitude)

Plan: `docs/plans/2026-07-28-008-feat-p4-05-region-provenance-plan.md`

Inventory: `docs/_scratch/p4-05-region-provenance-inventory.md`

Authority: `docs/contracts/document-and-evidence-contract.md`,
`docs/frontend/document-viewer-spec.md`, M-04/M-05/M-06, C-03/C-04.

## What landed

- Expand-only migration `c9e4b2d17a60` adds optional normalized
  `region_x/y/width/height` on `source_blocks` with CHECK constraints.
- Parser adapters (Docling/Reducto) normalize native bbox → crop-box 0..1;
  raw `bbox` remains forbidden on prepared payloads.
- `publish_prepared_source` persists region columns; seeds upsert figure/table
  blocks for `ev_mina_figure_valve` and torque fixtures.
- Shared live projector `project_persisted_evidence_anchor` (page-join reuse
  from retrieval `_evidence_anchor`) serves:
  - `GET /evidence/{evidenceRef}/location` (U3a)
  - turn detail `_turn_evidence_items` and SSE `_public_evidence_items` (U3b)
- Retrieval `RetrievalEvidenceAnchorDto` stays region-free.
- PDF viewer passes full authorized anchor: region highlight, containing-block
  cue, section/page fallback, generation fence, reduced-motion scroll; deep
  links never encode region coordinates.

## Post-migration acceptance boundary

M-04/AE1–AE5 apply to sources prepared after the region-column migration and
to seeded fixtures. Pre-migration corpora keep `region: null` until re-prep
(deferred residual).

## Commands

### Backend focused

```text
cd app
.venv/bin/pytest tests/test_parser_adapters.py \
  tests/test_documents_service.py \
  tests/test_documents_http_contract.py \
  tests/test_turn_evidence_region_projection.py \
  tests/test_authoritative_dto_components.py \
  tests/test_evidence_http_contract.py -q
```

Result (2026-07-28): all passed in this focused set.

### Frontend focused

```text
cd app/client
npx vitest run tests/pdfAnchorFocus.test.ts \
  tests/documentsDeepLink.test.ts \
  tests/parity/react/document-viewer.test.tsx
npx tsc --noEmit -p tsconfig.json
```

Result (2026-07-28): 21 Vitest passed; typecheck clean.

## Interaction-case trace

| Case | Outcome proved |
| --- | --- |
| M-04 | Figure location returns region; viewer focuses highlight after locating state |
| M-05 | Table region path + section/page fallback without crash |
| C-04 | Unknown / cross-owner / admin-on-member location → stable `evidence_not_found` 404; no region leak |
| M-06 | Stale/cleared anchor generation drops highlight; late location after clear ignored via `locationGenerationRef` |

## Privacy assertions

- Location/turn/SSE success bodies with non-null region scanned for block IDs,
  object keys, and `region_x` column names.
- Denial 404/410 bodies omit region coordinates and private IDs.
- Coordinate query params on location → 422 (`x`, `region`, …).
- Deep-link builders/parsers drop/forbid region coordinate query keys.
- Retrieval list still rejects `region` / `fallback:"region"`.

## Residuals

- P12-07 Playwright on deployed ingress for end-to-end figure focus.
- Non-PDF viewers remain unavailable (P9-03 credit).
- Pre-migration corpus re-prep workflow (no silent fabricated regions).
- Disposable PostgreSQL migration regenerate of schema snapshot when CI has PG
  (surgical snapshot edit landed with U2; regenerate preferred).

## Git commits (slice)

- `93b6d05` deepen plan + inventory
- `92d4da7` persist regions (U2)
- `3f71638` location projector (U3a)
- `bcfdf18` turn/SSE projector (U3b)
- `48736fc` viewer focus/fallback (U4)
- (this evidence + tracker) U5
