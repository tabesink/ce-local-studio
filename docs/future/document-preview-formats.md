# Future: Extended Document Preview Formats

Status: non-normative future brief. Not part of Phase 1 production build beyond
what P10-06 already closed.

## Phase 1 closed (P10-06)

Governed PDF preview is the only browser representation:

- Validated PDF originals may be the governed preview (pass-through).
- DOCX, Markdown, and plain text receive deterministic server-generated PDF
  previews before `previewKind=pdf`; originals never reach the inline PDF renderer.
- Evidence: `docs/_scratch/p10-06-governed-preview-evidence.md`.

## Still deferred

A later release may add:

1. PowerPoint / other non-allowlisted formats (requires upload allowlist + contracts).
2. An approved text or slide preview kind with matching HTTP/DTO/security
   contracts before any browser body is served (would expand closed `previewKind`).
3. OCR, editable HTML previews, multimodal embedding, and preview annotation authoring.

## Activation gate (for deferred items)

Requires coordinated updates to the document-and-evidence contract, HTTP/DTO
catalogs, upload/parser allowlist, preview object/version/page-map persistence,
privacy tests, and frontend viewer states. Until then, do not scaffold browser
text/slide renderers or invent `previewKind` values.
