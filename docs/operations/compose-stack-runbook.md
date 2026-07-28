# Compose Stack Operator Runbook (Development Matrix)

**Altitude:** local Compose / development matrix only.  
**Not** TLS, `testing=false` HTTPS, production HA, or P12-05 stream-drain evidence.  
Local-production MinIO object store: opt-in `compose.stack.minio.yml` (P10-04).  
Parser/provider packaging and support matrix: `docs/operations/provider-deployment-profiles.md` (P10-05).  
Credential-gated provider staging smoke: `scripts/provider_staging_smoke.py` with `CE_PROVIDER_STAGING_SMOKE=1` (never default verify).  
Full upload→Evidence Compose live path: opt-in `CE_P10_05_PIPELINE_LIVE=1` plus live/minio overlays; P5-04 remains topology credit only.  
Production incident/HA recovery: P12-04 / P12-08.

## Boot order

1. `postgres` healthy  
2. `migrate` (`python -m context_engine.migrate_release`) completed — Path 1 preflight accepts only empty DB or exact current catalog/head, then upgrades and re-verifies  
3. `bootstrap` (insert-only admin; `CE_ADMIN_*` only here) completed  
4. `api` `/health/ready` → `{status:ready}`  
5. `worker` internal readiness (DB + exact Alembic head + catalog match + object-store probe) then claim loop; Compose `healthy` = heartbeat after ready  
6. `frontend` `/login` healthy (not BFF trust proof)

**Default profile** uses filesystem object store (`CE_SOURCE_STORAGE_ROOT` / `stack-source-storage`).  
**MinIO profile** (opt-in): after postgres/migrate/bootstrap, `minio` healthy → `minio-init` completed → api/worker with `CE_OBJECT_STORE_KIND=s3`.

### Migrate refuse codes (Path 1)

Closed stderr reason → action. Do **not** run bare `alembic upgrade head` on an unknown volume.

| Reason | Action |
| --- | --- |
| `empty_ok` / `current_target_ok` (success line) | Continue bootstrap |
| `legacy_database_refused` | Decommission / export outside product; provision fresh DB |
| `partial_schema` / `renamed_object` / `unknown_object` / `catalog_mismatch` | Restore current-head backup or recreate empty volume |
| `revision_behind` / `revision_ahead` / `unknown_history` | Restore current-head backup; do not force upgrade |
| `extension_refused` / `snapshot_head_mismatch` | Fix cluster extensions / ship matching snapshot+head; recreate if unsure |

Path 2 supported legacy upgrade is **not** available. Backup/restore drills: P12-04.

```bash
cd app
docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d
```

**MinIO local-production overlay (P10-04; not default CI):**

```bash
cd app
docker compose --env-file .env.stack.local \
  -f compose.stack.yml -f compose.stack.minio.yml up --build -d
```

Recreate `.env.stack.local` from `.env.stack.example` for the ingress-wired HTTP profile (`CONTEXT_ENGINE_TESTING=true` + full `CE_*`). MinIO overlay also requires `MINIO_ROOT_*`, `CE_S3_*`, and `CE_S3_RECON_*` (recon keys stay off api/worker).

## Readiness probes

| Probe | Meaning |
| --- | --- |
| `GET /health/live` | Process up only |
| `GET /health/ready` (default) | DB + schema head + catalog match + enabled admin + filesystem store put+delete |
| `GET /health/ready` (MinIO overlay) | Same aggregate, but object-store probe uses S3 adapter against MinIO |
| Worker Compose `healthy` | Heartbeat file fresh **after** internal worker readiness |
| Worker claim-ready | In-process gate before first claim (not the heartbeat alone) |

Ready proves **capability** (ephemeral put+delete), not referential integrity. P12-04 recon is a separate gate.

## Smokes

**Core path (P10-02; default may inline turns under testing):**

```bash
python app/scripts/stack_smoke_core.py --env-file app/.env.stack.local
```

**Worker path (P10-03; Compose-leased turns):**

1. Set `CE_INLINE_TURN_WORKERS=false` in `.env.stack.local`  
2. Recreate `api` (and keep `worker` up)  
3. Run:

```bash
python app/scripts/stack_smoke_worker.py --env-file app/.env.stack.local
```

Green bar: BFF SSE allowed terminal **and** `execution_generation >= 1` **and** worker logs mention the smoke `clientRequestId`.  
Lease owner is cleared on terminal by product design — do not require post-terminal `lease_owner`.

Restore `CE_INLINE_TURN_WORKERS` unset/true when returning to default inline testing helpers.

## Graceful stop / drain

```bash
cd app
docker compose --env-file .env.stack.local -f compose.stack.yml stop -t 60 worker
```

Expect log event `stack_worker.stop_claim`, then process exit within `stop_grace_period` (60s).  
Busy drain finishes the current `run_once_pass` only; hung work may be SIGKILLed by Docker and recovered via lease expiry (do not force-complete).

## Kill + single-worker turn-lease reclaim

1. With a claimable/running leased turn (or after citing PG reclaim suites), `docker kill` the worker container.  
2. Wait at least `CE_TURN_LEASE_SECONDS` (shorten only in smoke-only env).  
3. `docker compose ... start worker` (or `up -d worker`).  
4. Confirm a new worker claims/reclaims work; stale generation completions are no-ops.

Algorithm authority: PostgreSQL suites `test_postgres_turn_leases.py`, domain/index reclaim tests.  
This drill is single-worker Compose-matrix reclaim — not P12-04 HA/incident recovery.

## Residuals (do not claim from this runbook)

| Concern | Owner |
| --- | --- |
| TLS / `testing=false` HTTPS / deployed API denial | P12 |
| Deployed ingress stream-drain | P12-05 |
| Cloud AWS-only / KMS / HA object-store | P12-04 / P12-08 |
| Combined live + MinIO three-file stack matrix | P12-04 |
| Production HA / backup / incident drills | P12-04 / P12-08 |
| Browser CSRF product fix | P9-05 residual |
| Completed synthesis without live provider | needs credentials / later proof |
