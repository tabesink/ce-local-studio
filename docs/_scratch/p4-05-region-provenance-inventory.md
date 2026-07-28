# P4-05 Figure and Table Region Provenance Inventory

Date: 2026-07-28

Owner: P4-05

Status: DONE — inventory complete before behavior changes

Requirements and decisions: R1–R8; KTD1–KTD7; AE1–AE5; M-04/M-05;
C-04; M-06; `docs/plans/2026-07-28-008-feat-p4-05-region-provenance-plan.md`.

## Scope

- Inventory retain/modify/replace/add/defer for parser bbox extraction,
  `source_blocks` region columns, location + turn/SSE projection, PDF
  viewer focus/fallback, and seed `SourceBlock` upserts before U2–U5.
- Pin greenfield bbox extraction (not “already persisted, just wire”).
- Pin post-migration acceptance boundary: M-04/AE1–AE5 for sources
  prepared after the region-column migration and for seeded fixtures.
- Flag blockers: none — location route, `EvidenceRegionDto`, and P9-03
  PDF preview infrastructure exist.

## Disposition register

| Surface | Prior evidence | Disposition | P4-05 target |
| --- | --- | --- | --- |
| `PreparedBlock` / `PreparedImage` | No region fields; page only | modify | Optional normalized region on `PreparedBlock` |
| `_FORBIDDEN_PREPARED_KEYS` includes `"bbox"` | Privacy fence | retain | Keep raw `bbox` forbidden; map to normalized fields |
| `_page_from_native` | Reads `bbox` only for page | modify | Also extract rect → crop-box 0..1 |
| `normalize_reducto_parse_response` | Blocks get page; coords discarded | modify | Map native block `bbox` when present |
| `normalize_docling_document` | Page from `prov`; coords discarded | modify | Map Docling `prov[].bbox` when present |
| `validate_prepared_source` | No region bounds | modify | Reject partial/out-of-range rects before publish |
| `publish_prepared_source` | Atomic block replace; no region | modify | Map region columns inside existing txn |
| `source_blocks` schema / ORM | page/section only | add | Expand-only `region_x/y/width/height` + CHECKs |
| `source_images` | page_number only | retain | Not layout-authority for region (KTD4) |
| `EvidenceRegionDto` / `EvidenceAnchorDto` | Already in catalog/OpenAPI/TS | retain | Project stored region; no regen unless validation tightens |
| `RetrievalEvidenceAnchorDto` | Region-free; tests fail-closed | retain | Must stay region-free (R5/KTD2) |
| `get_evidence_location` | Hardcodes `"region": None` | modify | U3a shared projector |
| `_evidence_anchor` | Page/section; figure linked-image page join | modify | Reuse page-join rules; no region on retrieval path |
| `_turn_evidence_items` | `"region": None` | modify | U3b shared projector |
| `_public_evidence_items` | Omits region; `page_start or 1` | modify | U3b; eliminate page-1 fabrication |
| Seed `ev_mina_*` evidence refs | Refs `block_valve_figure`; no SourceBlock upsert | modify | Upsert blocks with seed region constants |
| `DocumentsPage` location orchestration | Page only; ignores region | modify | Pass full anchor; pending/focused states |
| `PdfPreview` | `initialPage` only | modify | Region fit/highlight + transform |
| Deep-link builders | No region query keys | retain | Keep region out of URLs |
| Non-PDF viewers / P12 Playwright | Deferred | defer | Future / P12-07 |
| Pre-migration prepared corpora backfill | No re-prep workflow | defer | Follow-up re-prep |

## Parser bbox field shapes (U1 research)

| Provider | Native path | Coordinate space (expected) | Page source | Normalize to |
| --- | --- | --- | --- | --- |
| Reducto | Block dict `bbox` (and nested under page keys via `_page_from_native`) | Often pixel/page-box; confirm in fixture | `page` / `page_no` / `page_number` on block or bbox | Unrotated crop-box relative `[0,1]` `{x,y,width,height}` |
| Docling | Item `prov` list entries with `bbox` / page fields | Docling provenance bbox; confirm in fixture | `_page_from_native(item.get("prov") or item)` | Same crop-box 0..1 |
| Missing bbox | — | — | Page may still resolve | `region: null` success |

U2 must land representative native-bbox fixtures in `test_parser_adapters.py` before claiming AE1 for live prep paths.

## Module inventory

| Path | Role |
| --- | --- |
| `app/context_engine/adapters/parsers.py` | Normalize + validate; greenfield region extract |
| `app/context_engine/services/sources.py` | `publish_prepared_source` atomic replace |
| `app/context_engine/models.py` | `SourceBlock` / `SourceImage` ORM |
| `docs/database-schema.txt` | Authority schema (no region columns today) |
| `app/migrations/versions/` | New expand-only region migration |
| `app/context_engine/services/documents.py` | Location projection hardcodes null region |
| `app/context_engine/services/evidence.py` | Retrieval `_evidence_anchor` (page join credit) |
| `app/context_engine/services/chat_turns.py` | Turn detail + SSE public evidence projection |
| `app/context_engine/api/catalog_schemas.py` | `EvidenceRegionDto` already present |
| `app/context_engine/dev/seed_composer_refs.py` | Evidence refs without matching blocks |
| `app/client/src/features/documents/DocumentsPage.tsx` | Location → page open only |
| `app/client/src/features/documents/PdfPreview.tsx` | Page navigation; no highlight |
| `docs/quality/seeded-demo-and-test-data.md` | Figure `(0.12,0.24,0.66,0.41)` p18; table `(0.10,0.30,0.80,0.34)` p12 |

## Seed constants (authority)

| Evidence ref | Kind | Page | Region | Section |
| --- | --- | --- | --- | --- |
| `ev_mina_figure_valve` | figure | 18 | `(0.12,0.24,0.66,0.41)` | `4.2 Relief valve` |
| `ev_mina_table_torque` | table | 12 | `(0.10,0.30,0.80,0.34)` | — |
| `ev_mina_text_lockout` | text | 7 | absent | `2.1 Lockout` |
| `ev_mina_page_only` | figure | 20 | absent | absent; fallback `page` |

## Session-settled constraints

1. Regions optional proven metadata — never fabricate (KTD1).
2. Location + turn/SSE project region; retrieval stays closed (KTD2).
3. Adapters normalize once to crop-box 0..1; viewer transforms rotation/zoom (KTD3).
4. Persist on `source_blocks` columns with CHECKs (KTD4).
5. Shared live projector; reuse `_evidence_anchor` page-join; fallback region → block → section → page (KTD5).
6. Viewer highlights only after authorized location; no region in URL (KTD6).
7. U4 unblocked by U3a location green; U3b required before DONE (KTD7).
8. Deploy migration before app reads `region_*`; rollback app first then drop columns.
9. Stop if browser becomes region authority or retrieval gains region without contract amendment.

## Gaps closed by later units

1. U2 — migration, adapter extract, publish, seeds, native-bbox fixtures.
2. U3a — location projector, figure page join, C-04/admin≠owner/timing/denial leak scans.
3. U3b — turn/SSE projector parity + SSE leak scans.
4. U4 — PdfPreview region focus, stale-anchor, a11y highlight, pending state.
5. U5 — evidence + master-build-plan DONE.
