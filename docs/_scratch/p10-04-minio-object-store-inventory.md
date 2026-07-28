# P10-04 Local-Production MinIO Object Store Inventory

Date: 2026-07-28

Owner: P10-04

Status: DONE — implemented 2026-07-28; evidence `docs/_scratch/p10-04-minio-object-store-evidence.md`

Plan: `docs/plans/2026-07-28-011-feat-p10-04-minio-object-store-plan.md`

Authority: AGENTS.md; `docs/architecture/deployment-topology.md` object-store decision
(2026-07-28); `docs/architecture/production-adaptation-blueprint.md`; DRIFT-15;
`docs/master-build-plan.md` P10-04; P12-04 hook consumer.

## Scope

- One S3-compatible adapter behind existing `ObjectStorage` Protocol, exercised
  against Compose MinIO in an opt-in overlay.
- Closed `CE_OBJECT_STORE_KIND=filesystem|s3` + shared
  `object_store_from_settings` for `SourceStorage`, API readiness, and worker
  readiness.
- Credential tiers: init admin vs least-privilege app `CE_S3_*` (no ListBucket)
  vs operator recon List credentials.
- Operator recon/export hooks for P12-04; PostgreSQL keys+hashes remain
  inventory authority.
- Filesystem adapter remains development/default-CI only.

## Out of scope

- Cloud AWS-only hardening, multi-cloud SDKs, bucket UI, HA/replication.
- Upload orphan compensation worker.
- Write-fenced backup/restore drills (P12-04).
- Preview key census SQL (P10-06).
- Private-endpoint allowlist beyond Compose network isolation (parked Open
  Question — rely on private DNS + documented overlay).
- Combined `live.yml` + `minio.yml` stacking matrix freeze (parked Open
  Question — pairwise overlays in P10-04; combined matrix P12-04).

## Disposition register

| Surface | Current evidence | Disposition | P10-04 action |
| --- | --- | --- | --- |
| `ObjectStorage` Protocol + `FilesystemObjectStore` | `adapters/object_storage.py`; `test_object_storage.py` | retain-and-reverify | Keep port shape; filesystem default/dev |
| `object_store_from_root` | Hardwired in sources/readiness | modify | Add `object_store_from_settings`; keep root helper for filesystem |
| `SourceStorage` / `storage_from_settings` | Implicit filesystem via `object_store_from_root` | modify | Inject `store=object_store_from_settings(settings)` |
| `probe_object_store(root)` | Filesystem-only put+delete | modify | Accept Settings / composed store; S3 path via factory |
| Settings `CE_SOURCE_STORAGE_ROOT` only | `config.py` | add | `CE_OBJECT_STORE_KIND`, `CE_S3_*` (`repr=False` secrets) |
| S3 adapter | Absent | add | `adapters/s3_object_store.py` + boto3 optional extra |
| `pyproject.toml` extras | `lightrag-runtime` only | add | `object-store` extra (boto3) |
| Dockerfile | `CE_STACK_LIVE_IMAGE` gate | modify | Parallel `CE_STACK_OBJECT_STORE_IMAGE` (or combined) for MinIO overlay |
| `compose.stack.yml` | Shared `stack-source-storage` volume | retain | Default filesystem profile unchanged |
| MinIO Compose overlay | Absent | add | `compose.stack.minio.yml` + init job |
| Dual-root layout | Root hosts `objects/` + `domains/` | modify | S3: bytes in MinIO; slim local root for domain paths; drop shared object volume |
| Credential model | N/A | add | Init `MINIO_ROOT_*`; app CRUD no List; recon List separate |
| Recon/export hooks | Absent; P12-04 waits | add | `stack_object_store_recon.py` verify/export/orphan-warn |
| Runbook readiness table | Claims filesystem store | modify | Split default vs MinIO profiles |
| DRIFT-15 | Filesystem readiness DONE; production store residual | modify | Close local-production MinIO residual |
| Public URLs / port list API | Forbidden by architecture | retain-absence | No presign; no `list` on runtime port |
| Default `verify.sh` / CI | Filesystem | retain | MinIO opt-in evidence only |

## Retained invariants

- Opaque flat `obj_*` keys; reject `/`, `\`, `..`, empty.
- Inclusive HTTP Range semantics; idempotent delete; closed `ObjectStorageError`
  strings (`Object unavailable.`, etc.).
- Object keys/paths/hashes never in public DTOs.
- Ready probe = ephemeral put+delete through product composition (capability),
  not referential integrity.
- PostgreSQL `original_object_key` / `source_images.object_key` + hashes are
  inventory authority for recon.

## Implementation resolution of parked Open Questions

| Question | Resolution for this slice |
| --- | --- |
| Private endpoint allowlist | Compose private network + documented internal DNS; no settings CIDR allowlist in P10-04 |
| live + MinIO multi-overlay | Pairwise overlays proven; combined three-file matrix deferred to P12-04 inventory |

## Gaps closed by task-owned evidence (target)

1. U2: S3 adapter contract + factory + Settings probe wiring + packaging extra.
2. U3: MinIO overlay, credential/volume compose tests, readiness S3 negatives.
3. U4: Recon hook contract tests, AE3 content fail-closed, evidence + DRIFT-15.
