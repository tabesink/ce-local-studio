# P4-03 Docling/Reducto Adapters and Canonical Blocks Transaction Evidence

Date: 2026-07-25

Slice: P4-03

Requirements: FR-04; A-07; A-13; C-02; DRIFT-22 (parser half); DRIFT-30;
architecture parser port + lease/generation conventions.

Status: DONE - implemented and proven 2026-07-25

## Implemented and retained behavior

- `DocumentParser` port lives in `adapters/parsers.py` with Docling (local
  optional SDK) and Reducto (optional `reducto` SDK) adapters. Injectable
  converter/transport supports fixtures; missing SDK/credentials/timeouts
  fail closed with typed codes (`parser_unavailable`, `parser_not_ready`,
  `parser_timeout`, `parser_malformed_response`).
- UTF-8 text stand-ins are removed from the production adapter path.
- Normalizers map vendor payloads to ordered text/table/figure blocks and
  safe image metadata; privacy scan omits `job_id` / `pdf_url` /
  `studio_link` / URLs.
- Alembic head `a8d3f1c62e90` adds `source_images.object_key`; publish stores
  image bytes via the governed object-store port and atomically replaces
  blocks/images.
- Preparation worker heartbeats under one-third lease; publish requires
  matching lease owner, unexpired lease, and preparation generation.
  Cancel/fail clears lease fields.

## Proof-first evidence

1. `tests/test_parser_adapters.py` — normalize happy/malformed/URL-result,
   timeout mapping, credential denial, privacy dump.
2. `tests/test_postgres_source_preparation.py` — worker publish, expired-lease
   reclaim race (stale owner no-op), generation fence, image object-key
   storage on PostgreSQL 16.

## Verification

```text
cd app
python -m pytest tests/test_parser_adapters.py tests/test_sources_service.py tests/test_source_upload_validation.py tests/test_object_storage.py -q
# 18 passed

CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres
python -m pytest tests/test_postgres_source_preparation.py tests/test_postgres_sources_schema.py -q
# 2 passed
```

## Residuals / deferred

- Outline/retry/cancel/delete closed envelopes → P4-04.
- Synthesis provider stand-ins → P7-03 (remaining DRIFT-22 half).
- Installing optional `parsers` extras (`docling`, `reductoai`) for live
  worker environments; CI uses injectable fixtures without network.
- Member document routes → P6/P9.
