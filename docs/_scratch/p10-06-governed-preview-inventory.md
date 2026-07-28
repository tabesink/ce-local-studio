# P10-06 Governed Preview Generation Inventory

Date: 2026-07-28

Owner: P10-06

Status: DONE — inventory complete before behavior changes

Plan: `docs/plans/2026-07-28-017-feat-p10-06-governed-preview-generation-plan.md`

Authority: `docs/contracts/document-and-evidence-contract.md`;
`docs/architecture/data-and-lifecycle.md`; `docs/frontend/document-viewer-spec.md`;
P4-05 / P9-03 / P10-04 evidence; `docs/master-build-plan.md` P10-06.

## Scope

- Freeze retain/modify/add/defer for PDF-original delivery, non-PDF
  `previewKind=unavailable`, source generations, region/anchor projector,
  object storage derivatives, worker claim/publish, and delete cleanup.
- Keep public DTOs closed (`previewKind: pdf | unavailable`); never expose
  object keys, paths, renderer versions, page maps, or original non-PDF bytes.
- Gate production-supported formats on deterministic fixtures + opt-in smoke;
  defer PPT and unproven kinds.

## Out of scope

- Browser-side conversion, original-office inline rendering, presigned URLs.
- PPT / non-allowlisted formats; OCR; editable HTML; annotation authoring.
- Historical corpus re-prep solely to improve anchors.
- P12-04 backup/restore drills; P12-06 renderer SBOM pin; P12-07 browser E2E.

## Current behavior (frozen)

| Seam | Today | Contract target |
| --- | --- | --- |
| `preview_kind_for_source` | `pdf` iff `content_type == application/pdf`, else `unavailable` | `pdf` after committed governed preview readiness (PDF original or generated) |
| Content bytes | Serve `original_object_key` for PDFs only | Serve committed preview object (may equal original for validated PDF) |
| ETag | `sha256(ce-preview:original_sha256:version:size)` | Opaque ETag from committed preview checksum/version (`previewVersion`) |
| Page count | Max of SourceBlock page fields | Prefer committed preview page count when published; else retain block-derived |
| Location / Evidence | Requires `previewKind=pdf`; projects block page/region without page-map generation | Project only through committed page-map generation; degrade ladder |
| Schema | No preview columns on `source_documents` | Private preview object/checksum/version/page-map/renderer/source-hash |
| Worker | Prepare + delete ops; no preview operation | Preview claim/publish fenced by preparation generation |
| Delete | Deletes original (+ images/index); no preview census | Fence reads; idempotent preview + page-map cleanup + reconcile |
| Future brief | `docs/future/document-preview-formats.md` still describes DOCX as future | Superseded for DOCX/MD/text by this task; PPT remains deferred |

## Disposition register

| Surface | Current evidence | Disposition | P10-06 action |
| --- | --- | --- | --- |
| Closed `previewKind` / content DTOs | `catalog_schemas.py`; document contract | retain | No new public kinds or fields |
| PDF-original as preview | `documents.get_document_content` uses original key | retain-and-extend | Explicit PDF pass-through adapter; record private preview identity pointing at original when permitted |
| Non-PDF `unavailable` + `409 document_preview_unavailable` | `preview_kind_for_source`; content + location | modify | Flip to `pdf` only after atomic publish for DOCX/MD/text |
| Opaque ETag / no-store / range / If-Range | `preview_etag`; content path | modify | Bind ETag to committed preview version/checksum, not original size alone |
| `content_disposition` forces `.pdf` | `content_disposition_for_label` | retain | Keep governed PDF disposition |
| SourceBlock regions / `project_persisted_evidence_anchor` | P4-05 evidence service | modify | Remap through committed page map; explicit region→section→page→unavailable ladder |
| `SourceDocument.preparation_generation` / `version` | models + prepare publish | retain | Fence preview publish CAS on preparation generation |
| `source_preparation_operations` prepare/delete | one active op per source | modify or add | Prefer dedicated preview operation/lease state; do not widen public admin DTO with renderer details |
| Preview metadata columns / table | absent | add | Private preview object key, sha256, size, page_count, renderer_version, source_hash, page_map generation/object, preview_version |
| Page-map persistence | absent | add | Private derived object or structured private blob; never public |
| `PreviewRenderer` port | absent | add | Bounded killable adapter; typed safe errors; no auth/persist authority |
| Deterministic fixtures | PDF library tests exist; no DOCX→PDF | add | DOCX/MD/text fixtures under `tests/fixtures/documents/` |
| Object store put/get/range/delete | P10-04 `ObjectStorage` | retain | Write preview derivatives via same port; no List/presign |
| Source delete cleanup | `delete_source_files` originals (+ legacy paths) | modify | Fence preview reads; delete preview + page-map keys idempotently; reconcile orphans |
| Domain delete | cascades sources | retain-and-extend | Preview cleanup rides source/domain delete fence |
| Worker claim loop | `worker.py` source cleanup then domain delete | modify | Claim preview ops after/before prepare per lease design; external render outside DB txn |
| Packaging / Dockerfile | P10-05 parser/embedding gates | add | Separate renderer image/extra pin; default CI fixture-only |
| Opt-in production smoke | P10-05 staging smoke pattern | add | Credential/profile-gated real conversion smoke |
| `docs/future/document-preview-formats.md` | Marks DOCX preview as future | modify (docs only in U5) | Note Phase-1 DOCX/MD/text closed by P10-06; keep PPT/future kinds deferred |
| PPT / OCR / HTML preview | Future / outside upload allowlist | defer | Not in this slice |
| Browser viewer changes | P9-03 PdfPreview | retain | Consume existing PDF contract only; no original-format renderer |
| P12-04 / P12-06 / P12-07 | Depend on P10-06 | defer | Backup, SBOM, browser matrix residuals |

## Module inventory

| Path | Role |
| --- | --- |
| `app/context_engine/services/documents.py` | previewKind, ETag, content range, location gate |
| `app/context_engine/services/evidence.py` | `project_persisted_evidence_anchor` fallback ladder |
| `app/context_engine/services/sources.py` | prepare publish, delete fence/cleanup, storage |
| `app/context_engine/models.py` / `docs/database-schema.txt` | SourceDocument + prep ops; preview columns absent |
| `app/context_engine/adapters/object_storage.py` (+ S3) | Derivative byte I/O |
| `app/context_engine/adapters/parser_runtime.py` | Pattern for killable bounded subprocess |
| `app/context_engine/worker.py` | Claim/lease loop to extend for preview ops |
| `app/context_engine/api/catalog_schemas.py` | Closed public DTOs |
| `app/client` documents feature | PdfPreview only; no change required for new kinds |
| `docs/contracts/document-and-evidence-contract.md` | Normative preview + page-map generation rules |
| `docs/future/document-preview-formats.md` | Stale vs P10-06 for DOCX/MD/text — align in U5 |

## Contract field ownership

| Field / behavior | Owner | Disposition |
| --- | --- | --- |
| `previewKind` | documents service after publish | modify readiness rule |
| `pageCount` | documents summary/location | modify when preview page_count committed |
| `previewVersion` (private → ETag) | preview publish | add private; ETag material only |
| Content full/range PDF bytes | documents + ObjectStorage | modify key resolution to preview object |
| `document_preview_unavailable` | documents/location | retain code; narrower trigger |
| Anchor `pageNumber` / `region` / `fallback` | evidence projector + page map | modify remap |
| Renderer version / source hash / checksum | private schema | add; never DTO |
| Object keys / paths | private schema + store | retain-absence in public |

## Implementation order (from plan)

1. U2 — PreviewRenderer port + PDF pass-through + deterministic non-PDF adapters
2. U3 — Schema/migration + atomic publication worker + PostgreSQL races
3. U4 — Delivery + anchor mapping through committed map
4. U5 — Delete/recovery, runbook, evidence, tracker

## Open resolutions for implementation (not blockers)

| Question | Decision for this slice |
| --- | --- |
| Preview as new `operation_type` vs post-prepare step | Prefer dedicated preview operation/lease fenced by `preparation_generation` so prepare publish stays atomic for blocks while preview can retry independently |
| Page map storage shape | Private derived object (JSON) + checksum; generation tied to preview_version |
| PDF pass-through object | Reuse `original_object_key` when content_type is validated PDF; still persist private preview metadata row/columns |
| Default CI | Fixture renderer / canned PDF+map; real LibreOffice/weasy-style tool only behind packaging gate + opt-in smoke |

## Gaps this task must close

- Generated DOCX/Markdown/text PDF with deterministic checksum + page map
- Atomic preview publication under generation fence
- Content/location serve committed preview only
- Anchor remapping / explicit degrade
- Idempotent preview derivative cleanup + orphan reconcile hooks
- Honest supported-format evidence (no unproven kinds)
