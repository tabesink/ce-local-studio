# P4-01 Source Schema, Opaque Refs, and Storage Adapter Evidence

Date: 2026-07-25

Slice: P4-01

Requirements: FR-04; document-and-evidence `documentRef`; `AdminSourceDto`;
DRIFT-14 opaque-ref foundation; governed object-store port.

Status: DONE - implemented and proven 2026-07-25

## Implemented and retained behavior

- Alembic head `f4b2c9e18a70` adds `source_documents.version`,
  `source_preparation_operations.version`, and private
  `source_documents.original_object_key` (unique).
- `public_ref` generation uses `doc_` + `secrets.token_urlsafe`.
- `safe_source` projects closed `AdminSourceDto` including `documentRef`,
  maps internal index states to public `IndexState`, and omits hashes,
  object keys, counts, and index error detail.
- `adapters/object_storage.py` provides the governed object-store Protocol
  and development `FilesystemObjectStore` (put/get/inclusive-range/delete,
  opaque keys, path-escape rejection, idempotent delete).
- Upload commits DB intent, writes originals by opaque key under
  `{source_storage_root}/objects/`, and deletes the object on storage failure
  after write.

## Proof-first evidence

1. Added `tests/test_object_storage.py` and `tests/test_sources_service.py`
   before production wiring; collection failed with missing module/symbols
   (red baseline).
2. After implementation, both suites passed green.

## Verification

```text
cd app
python -m pytest tests/test_object_storage.py tests/test_sources_service.py -q
# 6 passed

CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres
python -m pytest tests/test_postgres_sources_schema.py tests/test_object_storage.py tests/test_sources_service.py -q
# 7 passed

python -m pytest tests/test_postgres_foundation.py tests/test_postgres_domains.py tests/test_health_contract.py -q
# 13 passed
```

## PostgreSQL assertions

- Head `f4b2c9e18a70` single-head upgrade.
- Version CHECKs on `source_documents` / `source_preparation_operations`.
- Unique indexes: `public_ref`, `original_object_key`, domain hash, one active prep.
- Upload stores opaque `obj_*` bytes and projects `documentRef` without key/hash leak.
- Domain hash uniqueness and one-active-prep partial unique reject second inserts.

## Residuals / deferred

- Streaming sniff/bomb/limit hardening and parser freeze proof → P4-02.
- Image object-key columns and parser adapter races → P4-03.
- Outline/retry/cancel/delete `202`/ETag API closure → P4-04.
- Member `/documents*` content routes → P6-02 / P9-03.
- Internal index_state CHECK collapse to public vocabulary → P5.
- Production object-store vendor selection → architecture decision.
