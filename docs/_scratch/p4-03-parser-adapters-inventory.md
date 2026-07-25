# P4-03 Docling/Reducto Adapters and Canonical Blocks Transaction Inventory

Date: 2026-07-25

Owner: P4-03

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-04; A-07; A-13 frozen inputs; C-02;
DRIFT-22 (parser half); DRIFT-30; architecture parser port and
lease/generation conventions.

## Scope

- Replace UTF-8 text stand-in Docling/Reducto adapters with typed
  `DocumentParser` port implementations that return one canonical
  parser-independent `PreparedSource`.
- Docling = optional local SDK (`docling`); Reducto = optional SDK
  (`reducto`) with injectable transport; both fail closed when the
  runtime or credentials are unavailable (`parser_unavailable` /
  `parser_not_ready` / `parser_timeout` / `parser_malformed_response`).
- Drive existing `normalize_docling_document` /
  `normalize_reducto_parse_response` from real adapters; never persist
  raw provider payloads, URLs, job IDs, or confidence fields.
- Atomic replace of `source_blocks` / `source_images` on publish;
  store image bytes under opaque object keys (new
  `source_images.object_key`).
- Preparation lease heartbeat under one-third lease; publish only when
  lease owner, unexpired lease, and preparation generation match
  (DRIFT-30).

## Out of scope

- Outline / retry / cancel / delete closed HTTP envelopes (P4-04).
- Synthesis provider stand-ins (P7-03 owns remaining DRIFT-22).
- Member document / preview routes (P6/P9).
- Production object-store vendor selection.
- Live network calls in CI; fixtures use injectable transports.

## Disposition register

| Surface | Current evidence | Disposition | P4-03 action |
| --- | --- | --- | --- |
| `ParserAdapter` Callable + text stand-ins in `sources.py` | DRIFT-22 | replace | `DocumentParser` Protocol + Docling/Reducto adapters in `adapters/parsers.py` |
| `normalize_*` helpers | Unused but correct mapping | retain-and-reverify | Unit fixtures for happy/malformed/privacy |
| `_simple_text_prepared_source` | Hidden prod path | remove-from-prod-path | Tests-only fixture helper if needed; not default adapters |
| `publish_prepared_source` | Atomic replace; generation only | modify | Owner + unexpired lease + generation fence; clear lease on terminal |
| `SourcePreparationWorker` | Claim/reclaim; no heartbeat | modify | Mid-parse heartbeat; abort publish when heartbeat fails |
| `source_images` storage | Filesystem under domain layout | modify | `object_key` column + governed object-store put/delete |
| Retry/cancel generation bump | Present (P4-02) | retain-and-reverify | Late gen-1 publish remains no-op |

## Adapter decision (approved for this slice)

1. **Docling** — local optional dependency. Adapter imports
   `docling.document_converter.DocumentConverter` (or an injected
   converter). Missing package or conversion failure → typed safe
   error; no UTF-8 binary decode fallback.
2. **Reducto** — external parse via optional `reducto` SDK (upload +
   `parse.run`) behind an injectable transport. Missing SDK, missing
   credential, timeout, auth failure, or malformed/URL-result fetch
   failure → typed safe error. Response normalization strips
   `pdf_url` / `studio_link` / `job_id` / confidence fields.
3. **CI/dev without SDKs** — workers fail closed with
   `parser_unavailable` until dependencies are installed; tests inject
   transports/converters and never require network.

## Retained invariants

- Parser kind remains frozen at upload (P4-02).
- Credentials resolve only at execution for Reducto.
- Adapters never authorize or commit product state.
- Cancel/retry bumps generation so late completions cannot publish.
- Public DTOs stay closed; private object keys never project.

## Gaps closed by task-owned evidence

1. Unit: normalizer fixtures, timeout/auth/malformed, forbidden-key privacy.
2. PostgreSQL: atomic block/image replace with object keys; expired-lease
   publish no-op; reclaim race; generation fence.
