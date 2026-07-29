# Compose Stack Operator Runbook (Development Matrix)

**Altitude:** local Compose / development matrix only.  
TLS / `testing=false` HTTPS / stream-drain: opt-in P12-05 overlay (`compose.stack.tls.yml`) — see § TLS ingress (P12-05).  
**Not** production HA.  
Local-production MinIO object store: opt-in `compose.stack.minio.yml` (P10-04).  
Parser/provider packaging and support matrix: `docs/operations/provider-deployment-profiles.md` (P10-05).  
Governed preview (DOCX/Markdown/text→PDF): worker preview slot after prepare; optional image gate `CE_STACK_PREVIEW_IMAGE=1` / `--extra preview-renderer` (P10-06).  
Credential-gated provider staging smoke: `scripts/provider_staging_smoke.py` with `CE_PROVIDER_STAGING_SMOKE=1` (never default verify).  
Full upload→Evidence Compose live path: opt-in `CE_P10_05_PIPELINE_LIVE=1` plus live/minio overlays; P5-04 remains topology credit only.  
Backup/restore/incident drills (Compose matrix): [`backup-restore-incident-runbook.md`](./backup-restore-incident-runbook.md) (P12-04).  
Production KMS/escrow/HA/RPO-RTO acceptance: **P12-08 only**.

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
| `partial_schema` / `renamed_object` / `unknown_object` / `catalog_mismatch` | Restore via [`backup-restore-incident-runbook.md`](./backup-restore-incident-runbook.md) (F1–F2) or recreate empty volume |
| `revision_behind` / `revision_ahead` / `unknown_history` | Restore via [`backup-restore-incident-runbook.md`](./backup-restore-incident-runbook.md) (F1–F2); do not force upgrade |
| `extension_refused` / `snapshot_head_mismatch` | Fix cluster extensions / ship matching snapshot+head; recreate if unsure |

Path 2 supported legacy upgrade is **not** available. Backup/restore drills: [`backup-restore-incident-runbook.md`](./backup-restore-incident-runbook.md).

### One-command local demo (P12-07 U11)

Prefer the repository entrypoint for the full local-demo matrix (base + MinIO + live runtime):

```bash
bash scripts/dev.sh
```

This preflights Docker/Compose and env completeness, generates `CE_GRAPH_REF_KEY` into the gitignored env file when absent (mode 0600; value never printed), starts `compose.stack.yml` + `compose.stack.minio.yml` + `compose.stack.live.yml`, waits for API readiness, and prints only the public login URL, admin username, service roles, and status/log/stop commands. Host-native hot reload remains available as `CE_DEV_MODE=host bash scripts/dev.sh` and is not the full-stack demo path.

```bash
cd app
docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d
```

**MinIO local-production overlay (P10-04; included by `scripts/dev.sh` demo path):**

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
| `GET /health/ready` (default) | DB + schema head + catalog match + enabled admin + filesystem store put+delete; outside testing also requires `CE_GRAPH_REF_KEY` (≥32 bytes) |
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
This drill is single-worker Compose-matrix reclaim — not multi-failure / restore-coupled incident recovery (see [`backup-restore-incident-runbook.md`](./backup-restore-incident-runbook.md) F5).

## TLS ingress (P12-05)

Opt-in evidence lane (not default `scripts/verify.sh`). Canonical cwd is `app/` with `--env-file .env.stack.local`.

**Three-file matrix** (`compose.stack.yml` + `compose.stack.live.yml` + `compose.stack.tls.yml`) is the AE1–AE3 authority. Two-file TLS-only may be used only for AE4 compose/unpublished checks when live is unavailable — do not claim AE1 from two-file.

### Boot

```bash
python app/scripts/generate_stack_tls_certs.py
# In app/.env.stack.local (env names only; never commit keys):
#   CE_STACK_PUBLIC_ORIGIN=https://127.0.0.1:8443
#   CONTEXT_ENGINE_TESTING=false
#   CE_SESSION_COOKIE_SECURE=true
#   CE_INLINE_TURN_WORKERS=false
#   CE_STACK_TLS_CERT_DIR=<absolute app/.stack-tls>
#   CE_STACK_LIVE_RUNTIME_ROOT=<host-abs live runtime root>
#   OPENAI_API_KEY or CE_OPENAI_API_KEY (host/env-file; never logged)
cd app
docker compose --env-file .env.stack.local \
  -f compose.stack.yml -f compose.stack.live.yml -f compose.stack.tls.yml \
  up --build -d
```

### AE1 preflight (synthesis + domain)

Host env key presence is necessary but not sufficient. Install/activate sealed OpenAI synthesis on the stack via the contracted admin runtime-settings provider path (`PUT /api/v1/admin/runtime-settings/providers/{kind}` — see `docs/contracts/http-api-catalog.md` and `docs/operations/provider-deployment-profiles.md`). Seed/index a query-eligible Knowledge Domain per `docs/quality/seeded-demo-and-test-data.md` and P5-04 live overlay; record the public opaque `--domain-id` (never private DB ids).

### Proof commands

```bash
cd app
python scripts/stack_ingress_trust_proof.py --env-file .env.stack.local
# Requires ca=yes (CE_STACK_TLS_CERT_DIR/cert.pem). Digests must not show ca=insecure-local.
python scripts/stack_ingress_sse_proof.py --env-file .env.stack.local --domain-id <opaque-domain-id>
# Drain-hold: SIGUSR1 on api (listen stays up) → live 503 capacity_unavailable → worker stop_claim
python scripts/stack_ingress_drain_proof.py --env-file .env.stack.local
```

API drain-hold: `SIGUSR1` → `enter_drain_hold` / `api.stop_new_turns` while the process still serves; new `turns:stream` returns contracted `503 capacity_unavailable`. Unit altitude: `tests/test_api_shutdown_drain.py`. Lifespan teardown remains a backstop.

## P12-07 @release capacity / pipeline lane (U4)

Opt-in only. **Not** part of `scripts/verify.sh` or the PR job `verify-playwright-pr-fast`.

```bash
# 1) Freeze budgets + in-process graph L/L+1 shed (no Docker required for unit mode)
CE_P12_07_RELEASE=1 python app/scripts/p12_07_release_capacity_probe.py check
CE_P12_07_RELEASE=1 python app/scripts/p12_07_release_capacity_probe.py unit

# 2) Full demo topology (base + MinIO + live) when claiming live graph/RAG
bash scripts/dev.sh
# or: docker compose --env-file .env.stack.local \
#        -f compose.stack.yml -f compose.stack.minio.yml -f compose.stack.live.yml up --build -d

# 3) Browser @release matrix (requires CE_P12_07_RELEASE=1 or specs skip)
CE_P12_07_RELEASE=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
  npm --prefix app/client run test:e2e:release
```

Evidence checklist: `docs/_scratch/p12-07-release-evidence-checklist.md`.  
Credential-gated provider/parser live smoke remains `CE_PROVIDER_STAGING_SMOKE=1` / `CE_P5_04_LIVE=1` — do not conflate with the capacity unit probe.

## Residuals (do not claim from this runbook)

| Concern | Owner |
| --- | --- |
| Deployed PDF byte-range through ingress | P12-07 |
| Ingress adversarial deletion | P12-07 |
| Playwright / browser CSRF product / two-user cache | P12-07 |
| Hard provider-I/O abort beyond cooperative drain | P12-08 |
| Cloud AWS-only / KMS / HA object-store | **P12-08 only** |
| Combined live + MinIO three-file stack matrix (operator digests) | P12-04 residual / operator attach |
| Compose backup/restore/incident drill procedures | P12-04 — [`backup-restore-incident-runbook.md`](./backup-restore-incident-runbook.md) |
| Production HA / RPO-RTO / KMS/escrow acceptance | **P12-08 only** |
| Browser CSRF product fix | P9-05 residual / P12-07 |
