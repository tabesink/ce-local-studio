# P10-04 Local-Production MinIO Object Store Evidence

Date: 2026-07-28

Owner: P10-04

Status: DONE at unit/compose-config altitude (opt-in live MinIO smoke residual)

Plan: `docs/plans/2026-07-28-011-feat-p10-04-minio-object-store-plan.md`

Inventory: `docs/_scratch/p10-04-minio-object-store-inventory.md`

## Delivered

1. **S3 adapter + factory** — `adapters/s3_object_store.py`, `object_store_from_settings`,
   `CE_OBJECT_STORE_KIND` / `CE_S3_*` settings, `storage_from_settings` and
   `probe_object_store(Settings)` share composition.
2. **Packaging** — optional `object-store` extra (boto3); Dockerfile
   `CE_STACK_OBJECT_STORE_IMAGE=1` gate (parallel to live LightRAG image).
3. **Compose overlay** — `compose.stack.minio.yml`: MinIO + minio-init (init admin vs
   app CRUD vs recon List tiers), api/worker `kind=s3`, slim `stack-source-local`
   (not shared object-bytes volume). Default `compose.stack.yml` unchanged.
4. **Recon hooks** — `scripts/stack_object_store_recon.py` modes verify / export /
   orphan-warn; export manifests gitignored; closed CLI errors.
5. **AE3** — missing referenced object → `503 document_content_unavailable` without key leak.

## Commands / results

```bash
cd app
uv run --extra test pytest \
  tests/test_s3_object_store.py \
  tests/test_object_storage.py \
  tests/test_health_contract.py \
  tests/test_worker_readiness.py \
  tests/test_compose_stack_config.py \
  tests/test_stack_object_store_recon.py \
  tests/test_documents_service.py::test_get_document_content_missing_object_is_safe_503 \
  -q
```

Focused result: green (2026-07-28).

Compose config altitude also covered by `test_compose_*minio*` (requires Docker CLI for
`docker compose config`).

## Version-marker policy (for P12-04)

Export manifest `schemaVersion=1` records per-object `etag` and optional `versionId`
from S3 HeadObject when available. Default MinIO overlay does not require bucket
versioning; ETag + `contentSha256` + `objectTreeDigest` are the Phase-1 consistency
fields. If versioning is enabled later, `versionId` populates without schema change.

## Non-claims / residuals

| Item | Owner |
| --- | --- |
| Opt-in live MinIO put/get/range smoke against running overlay | operator evidence / P12-04 drills |
| Combined `live.yml` + `minio.yml` three-file matrix | P12-04 (Open Question) |
| Private endpoint CIDR allowlist in Settings | deferred (Compose network isolation) |
| Cloud AWS-only / KMS / HA | P12-08 |
| Upload orphan compensation worker | deferred follow-up |
| Bucket UI / multi-cloud / port-level list API | out of scope (AE4) |
| Default CI / `verify.sh` MinIO | deliberately filesystem-only |

## Tracker

- P10-04 → DONE
- DRIFT-15 → local-production MinIO + S3 readiness closed; filesystem remains
  development/default-CI only
