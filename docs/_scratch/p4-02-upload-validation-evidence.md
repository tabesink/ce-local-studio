# P4-02 Upload Validation, Dedup, and Parser-Kind Freeze Evidence

Date: 2026-07-25

Slice: P4-02

Requirements: FR-04; A-06; A-07 parser freeze; DRIFT-13; catalog codes
`content_rejected` / `duplicate_source`.

Status: DONE - implemented and proven 2026-07-25

## Implemented and retained behavior

- Admin upload no longer calls `await request.body()`. It uses multipart
  `UploadFile` chunked reads with early Content-Length denial and
  `content_rejected` on oversize.
- `source_upload.validate_upload_bytes` sniffs PDF/DOCX/text/markdown from
  bytes/structure; declared multipart Content-Type is never authoritative.
- DOCX/ZIP containers are checked for entry count, uncompressed total, and
  compression ratio before accept.
- Domain SHA-256 uniqueness emits `duplicate_source`; unsupported/bomb/oversize
  emit `content_rejected`.
- Upload freezes `parser_kind` from runtime defaults; retry reassigns the same
  frozen value and does not re-read active parser defaults.

## Proof-first evidence

1. `tests/test_source_upload_validation.py` was added for sniff/bomb/oversize.
2. PostgreSQL suite extended for rejected spoof (zero rows), duplicate_source,
   sniffed PDF content type, and parser freeze across runtime change + cancel/retry.

## Verification

```text
cd app
python -m pytest tests/test_source_upload_validation.py tests/test_object_storage.py tests/test_sources_service.py -q
# 12 passed

CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres
python -m pytest tests/test_postgres_sources_schema.py tests/test_source_upload_validation.py -q
# 7 passed
```

## Residuals / deferred

- Real Docling/Reducto adapters → P4-03.
- Outline/retry/cancel/delete closed envelopes → P4-04.
- Broader uncataloged source state conflict codes cleanup → residual with P4-04.
- Member document routes → P6/P9.
