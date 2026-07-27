# Future: Non-PDF Document Preview Formats

Status: non-normative future brief. Not part of Phase 1 production build.

## Intent

Phase 1 (`P9-03`) ships governed PDF preview only: validated PDF originals are
the preview bytes; DOCX, Markdown, and plain text remain listable with
`previewKind=unavailable` / `409 document_preview_unavailable`. PowerPoint is
not in the Phase 1 upload allowlist.

A later release may add:

1. Deterministic server-generated PDF previews for DOCX/Markdown/text (preferred —
   keeps the closed `previewKind: "pdf" | "unavailable"` contract), and/or
2. An approved text or slide preview kind with matching HTTP/DTO/security
   contracts before any browser body is served.

## Activation gate

Requires coordinated updates to the document-and-evidence contract, HTTP/DTO
catalogs, upload/parser allowlist (if PPTX), preview object/version/page-map
persistence, privacy tests, and frontend viewer states. Until then, do not
scaffold browser text/slide renderers or invent `previewKind` values.
