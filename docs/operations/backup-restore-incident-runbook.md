# Backup, Restore, Image Rollback, and Incident Drills (Compose Matrix)

**Altitude:** local Compose / MinIO + live LightRAG matrix only.  
**Authority:** FR-11; `docs/architecture/deployment-topology.md` (backup/DR); P12-04 plan/evidence.  
**Evidence:** `docs/_scratch/p12-04-backup-restore-evidence.md`  
**Not:** production RPO/RTO SLOs, KMS/escrow, HA/cloud failover, Path 2 contraction, TLS/stream-drain, SBOM, or browser E2E (see residuals).

Compose stack boot/smoke/single-worker reclaim remain in [`compose-stack-runbook.md`](./compose-stack-runbook.md). This runbook replaces the “restore current-head backup” placeholder with rehearsable F1–F5 procedures.

## Three-file matrix command

AE2 capture and AE4 rebuild require all three files (pairwise overlays alone are not DONE for rebuild):

```bash
cd app
docker compose --env-file .env.stack.local \
  -f compose.stack.yml \
  -f compose.stack.minio.yml \
  -f compose.stack.live.yml \
  config
```

Disposable restore projects must use a distinct `-p` project name and non-overlapping **resolved** postgres/minio/runtime volumes (Compose prefixes the project name — do not rely on bare logical `stack-*` names alone).

## Consistency unit (include / exclude)

| Included | Excluded |
| --- | --- |
| PostgreSQL dump (Phase 1 catalog/data) | `domain-runtimes` / LightRAG disk as backup authority |
| MinIO object **bytes** via S3 GetObject of PG→refs census keys (original, images, preview, page-map) | Metadata-only `stack_object_store_recon.py --mode export` |
| ETag + contentSha256 + objectTreeDigest in consistency manifest | Live MinIO data-dir tar while MinIO is running |
| Encryption-key **fingerprint** in manifest + separately pathed companion key file | Raw `CONFIG_ENCRYPTION_KEY` inside dump, object archive, git, or evidence |
| Alembic head + local image digests used in the drill | Staging/prod registry digests (P12-06/08) |

Filesystem object adapter is development-only and is **not** the DR boundary (`--require-s3` for AE green).

## Key custody

1. Capture records only a key fingerprint in the consistency manifest.  
2. Raw `CONFIG_ENCRYPTION_KEY` is written only to a **gitignored companion path outside the archive directory**.  
3. Restore injects the companion via env/file mount; wrong/missing key must fail decrypt proof closed.  
4. Success and failure paths **shred** the companion (`--shred-companion` on restore).  
5. Never co-package dump + object archive + raw key in one zip, CI artifact, or evidence attachment.

## F1 — Consistency-point capture

Preconditions: drill seed finished (`stack_drill_seed.py`); no unexpected put/publish writers.

1. Write-fence: stop **only** `api` and `worker` on the three-file matrix. Fail if other put/publish-capable services remain up.  
2. Under one fence episode (no restart between halves):  
   - PG→refs census (`stack_pg_object_refs_census.py`)  
   - S3 GetObject each census key into a portable key→bytes archive (`stack_backup_capture.py`)  
   - `pg_dump` into the same archive set  
   - Emit consistency manifest (PG digest, objectTreeDigest, ETag markers, key fingerprint, head, store kind)  
3. Write companion key to a separate path if requested (`--companion-key-out`).  
4. Release fence (restart api/worker).  
5. Record artifact paths and digests (not secret material) in operator notes.

```bash
cd app
# Seed BEFORE fence
uv run --frozen --python 3.12 python scripts/stack_drill_seed.py \
  --database-url "$CONTEXT_ENGINE_DATABASE_URL" --put-objects

# Capture (defaults to three-file compose list; requires S3/MinIO for AE green)
uv run --frozen --python 3.12 python scripts/stack_backup_capture.py \
  --archive-dir /path/to/ce-backup-archive \
  --require-s3 \
  --compose-env-file .env.stack.local \
  --companion-key-out /path/to/ce-backup-key.companion
```

## F2 — Isolated restore and recon

1. Boot a disposable Compose project (`-p` distinct; volumes non-overlapping with live).  
2. Restore PostgreSQL from the dump; run Path 1 `migrate_release` (accept exact current head only — refuse table in compose runbook).  
3. After `minio-init`, PutObject census keys with **app or MinIO-root** credentials (not `CE_S3_RECON_*`, which cannot Put).  
4. Reconcile every referenced key against restored MinIO bytes/ETag/sha256 (`stack_restore_recon.py`). Hard-fail on missing object, ETag mismatch, digest mismatch, or missing encryption key. Orphans warn only.  
5. Refuse restore targets that overlap the live project’s resolved volumes (`--refuse-live-project`).  
6. Prove key recoverability with companion injection + optional Fernet ciphertext; shred companion.

```bash
cd app
uv run --frozen --python 3.12 python scripts/stack_restore_recon.py \
  --archive-dir /path/to/ce-backup-archive \
  --companion-key /path/to/ce-backup-key.companion \
  --shred-companion \
  --refuse-live-project \
  --live-volumes "$LIVE_RESOLVED_VOLUMES" \
  --target-volumes "$TARGET_RESOLVED_VOLUMES" \
  --orphan-warn
```

## F3 — Post-restore continuity (pre-rebuild)

On the restored env, before LightRAG rebuild:

1. Fresh admin/member login (session/CSRF are re-login-only after restore).  
2. Redacted turns stay omitted (no answer reappearance).  
3. Invalidated/expired governed refs stay unusable.  
4. Audit count + ordered digest via **operator SQL** in the disposable env only (no public audit-read API).  
5. Authorized preview/range for seeded preview derivatives at Compose-matrix altitude.  
6. Deletion/tombstone or fenced-delete observables remain fail-closed.

```bash
cd app
uv run --frozen --python 3.12 python scripts/stack_restore_continuity.py \
  --database-url "$CONTEXT_ENGINE_DATABASE_URL" \
  --fetch-preview
```

Citations/anchors after domain rebuild are the rebuild half (F3/F6 below) — not this script.

## F3/F6 — LightRAG rebuild on empty runtime (three-file)

After F2 recon and F3 continuity:

1. Empty/clear the live host bind `CE_STACK_LIVE_RUNTIME_ROOT` (not only a named `stack-domain-runtimes` volume).  
2. Boot the three-file matrix against restored PG + MinIO objects.  
3. Drive product admin/worker **start_domain → index** paths (not a second synthetic runtime).  
4. Prove mapped Evidence/citations/anchors (or contracted absence) and that runtime disk was not required from backup.

```bash
cd app
uv run --frozen --python 3.12 python scripts/stack_lightrag_rebuild_drill.py \
  --dry-run \
  --runtime-root "$CE_STACK_LIVE_RUNTIME_ROOT"
# Live (opt-in): omit --dry-run against three-file disposable restore env.
```

Credit: P5-04 live pytest is topology/algorithm authority — operator digests for this drill remain the live residual when not captured in-session.

## F4 — Schema-compatible image rollback

1. Retain two locally built digests at the **same Alembic head**.  
2. Swap api/worker (and frontend if lockstep).  
3. Confirm `/health/ready` + `stack_smoke_core` (and worker smoke if inline-off) green.  
4. If prior image cannot ready against current head → **restore path (F1/F2)**, not force-down.

**Refuse:** improvised down migration / `alembic downgrade` as production rollback  
(credit `docs/architecture/deployment-topology.md`, `docs/architecture/security-operations-and-quality.md`, `docs/_scratch/p1-01-foundation-evidence.md`).

```bash
cd app
uv run --frozen --python 3.12 python scripts/stack_image_rollback_drill.py \
  --alembic-head <head> \
  --current-digest api=<digest> --prior-digest api=<digest> \
  --print-steps

# Explicit refuse path (must exit non-zero):
uv run --frozen --python 3.12 python scripts/stack_image_rollback_drill.py --attempt-downgrade
```

## F5 — Multi-failure / restore-coupled incident

Beyond P10-03 single-worker reclaim (still credited; do not re-own):

| Mode | Intent |
| --- | --- |
| `api_worker_kill` | Kill API+worker → wait shortened drill leases → restart → reclaim progresses; no double-complete |
| `restore_then_reclaim` | Capture/restore while leased/running row present → reclaim without scrubbing leases early |
| `missing_object` | After restore, delete/corrupt one MinIO object → document/content and worker paths fail safe (no eligibility restore, no silent empty success) |

Do **not** force-complete turns/ops, clear leases early, or bypass generation fences.

```bash
cd app
uv run --frozen --python 3.12 python scripts/stack_incident_reclaim_drill.py \
  --mode api_worker_kill --lease-seconds 10 --dry-run
uv run --frozen --python 3.12 python scripts/stack_incident_reclaim_drill.py \
  --mode restore_then_reclaim --lease-seconds 10 --dry-run
uv run --frozen --python 3.12 python scripts/stack_incident_reclaim_drill.py \
  --mode missing_object --object-key <key> --content-status 503
```

Shortened `CE_*_LEASE_SECONDS` is drill-only (mirror P10-03 smoke knobs).

## Go / no-go

| Check | Go | No-go |
| --- | --- | --- |
| Store kind for AE green | MinIO/S3 (`--require-s3`) | Filesystem-only as DR evidence |
| Archive | Portable key→bytes + PG dump + manifest | Metadata-only export; live MinIO volume-tar |
| Recon | All census keys match ETag/sha256; decrypt proof ok | Missing key/object/ETag/digest; wrong companion key |
| Volumes | Disposable `-p` with non-overlapping resolved volumes | Restore onto live project’s resolved volumes |
| Schema | Path 1 accepts exact current head | Improvised `alembic downgrade` / force-down |
| Continuity | Redaction omitted; refs denied; audit digest match; preview/range ok | Answer reappears; silent empty content; eligibility restored after missing object |
| Rebuild | Empty runtime bind rebuilt via product paths | Treating runtime disk as restored from backup |
| Secrets | Companion shredded; no dump+key co-package | Secrets in git, CI logs, or evidence |

When Path 1 migrate refuse codes fire (`partial_schema`, `revision_behind`, etc.), use this runbook’s restore path or recreate an empty volume — see compose runbook refuse table.

## Temp cleanup

Verified cleanup is part of drill success:

1. Shred companion key first (or independently of dump deletion).  
2. Delete PG dump and object byte archive from temp paths.  
3. Tear down disposable Compose project and its volumes.  
4. Confirm no secret-class material remains under the workspace or CI artifacts.

## Non-claims / residuals

| Concern | Owner |
| --- | --- |
| Production RPO/RTO, KMS/escrow, HA/cloud failover, staging/prod digests | **P12-08 only** |
| Path 2 populated upgrade/contraction | Future / P12-08 release decision |
| TLS / stream-drain / deployed byte-range | P12-05 |
| SBOM / immutable release digests | P12-06 |
| Browser E2E / governed-preview navigation / capacity | P12-07 |
| Single-worker kill+reclaim runbook | P10-03 credit (compose runbook) |
| Filesystem object adapter as production/DR | Development-only residual |
| Opt-in three-file live operator digests when not captured in-session | Attach under P12-04 evidence residual |
