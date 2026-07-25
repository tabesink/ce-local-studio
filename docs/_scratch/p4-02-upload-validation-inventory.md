# P4-02 Upload Validation, Dedup, and Parser-Kind Freeze Inventory

Date: 2026-07-25

Owner: P4-02

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-04; A-06; A-07 parser freeze; A-13 frozen
inputs; DRIFT-13; HTTP source codes `duplicate_source` / `content_rejected`.

## Scope

- Replace `await request.body()` multipart buffering with UploadFile chunked
  read under `MAX_SOURCE_FILE_SIZE_BYTES`, aborting before full consume when
  the limit is exceeded.
- Sniff allowlisted content from magic/structure (PDF, DOCX, text/markdown);
  ignore declared multipart Content-Type as authority.
- Reject DOCX/ZIP decompression bombs (uncompressed total/ratio) with
  `content_rejected` and zero partial DB/object commit.
- Keep server-side SHA-256 and domain `(domain_id, sha256)` uniqueness;
  emit catalog code `duplicate_source`.
- Prove parser kind frozen at upload: retry after runtime parser change does
  not rewrite `source.parser_kind`.

## Out of scope

- Real Docling/Reducto adapters and atomic block publish (P4-03).
- Outline/retry/cancel/delete closed operation envelopes (P4-04).
- Member document routes (P6/P9).
- Production object-store vendor.

## Disposition register

| Surface | Current evidence | Disposition | P4-02 action |
| --- | --- | --- | --- |
| `admin_upload_source` + `_multipart_file_from_request` | `await request.body()` then parse | replace | Chunked UploadFile ingest + early Content-Length reject |
| Declared MIME allowlist in `upload_source_bytes` | Trusts multipart type | replace | Magic/structure sniff → allowlist |
| Size check after full buffer | Post-buffer `len(data)` | modify | Streaming counter + 413 `content_rejected` |
| Domain hash dedup | Present; uncataloged `source_duplicate` | modify | Keep uniqueness; use `duplicate_source` |
| Unsupported codes | `source_file_unsupported` / `source_file_too_large` | replace | Catalog `content_rejected` |
| DOCX bomb checks | Absent | add | Zip uncompressed/ratio gates |
| Parser freeze on retry | Implicit (retry does not set parser) | retain-and-reverify | Explicit unit + PG proof vs runtime change |

## Retained invariants

- Filename is sanitized display metadata only.
- Object keys remain opaque (P4-01).
- Interrupted/failed validation commits neither source nor prepare operation.
- Client-supplied digests are never accepted.

## Gaps closed by task-owned evidence

1. Unit proofs for sniff, bomb reject, oversize abort, declared-type spoof denial.
2. Parser-freeze proof across runtime settings change + retry.
3. PostgreSQL proof of duplicate_source and no partial row after rejected content.
