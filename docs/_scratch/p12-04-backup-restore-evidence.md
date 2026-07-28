# P12-04 Backup Restore Image Rollback and Incident Drills — Evidence

Date: 2026-07-28  
Owner: P12-04  
Status: DONE at scripted **unit-test altitude** + operator runbook; **opt-in three-file Compose live capture/restore/rebuild matrix operator digests remain residual**  
Plan: `docs/plans/2026-07-28-005-feat-p12-04-backup-restore-drills-plan.md`  
Inventory: `docs/_scratch/p12-04-backup-restore-inventory.md`  
Runbook: `docs/operations/backup-restore-incident-runbook.md`  
Artifact revision at evidence write: `4e22d9b` (`feat/p12-04-backup-restore-drills`; U6 helpers in `9c7b20b`)

## Prerequisites cited (DONE — do not re-prove)

| Prerequisite | Evidence revision |
| --- | --- |
| P5-04 real private LightRAG runtime | `docs/_scratch/p5-04-lightrag-real-runtime-evidence.md` |
| P10-04 MinIO + S3 adapter + recon hooks | `docs/_scratch/p10-04-minio-object-store-evidence.md` |
| P10-06 governed preview derivatives | `docs/_scratch/p10-06-governed-preview-evidence.md` |
| P12-01 Path 1 preflight/readiness | `docs/_scratch/p12-01-populated-compatibility-evidence.md` |

Additional credit: P10-03 single-worker reclaim (`docs/_scratch/p10-03-worker-lifecycle-evidence.md`); P1-01 refuse-downgrade language; PG lease suites as reclaim algorithm authority.

## Delivered

1. **Inventory** — `docs/_scratch/p12-04-backup-restore-inventory.md` (U1).
2. **Capture / census / restore-recon** — `stack_backup_capture.py`, `stack_pg_object_refs_census.py`, `stack_restore_recon.py` + `test_stack_backup_restore_recon.py` (U2).
3. **Drill seed + R13 continuity** — `stack_drill_seed.py`, `stack_restore_continuity.py` + `test_stack_restore_continuity.py` (U3; pre-rebuild half of AE4).
4. **Schema-compatible image rollback** — `stack_image_rollback_drill.py` + `test_stack_image_rollback_drill.py` (U4); refuse improvised down migration / `alembic downgrade`.
5. **Multi-failure / restore-coupled reclaim** — `stack_incident_reclaim_drill.py` + `test_stack_incident_reclaim_drill.py` (U5); credit P10-03 single-worker path.
6. **LightRAG rebuild drill (R14)** — `stack_lightrag_rebuild_drill.py` + `test_stack_restore_lightrag_rebuild.py` (U6); P5-04 live pytest topology/algorithm credit only.
7. **Operator runbook** — `docs/operations/backup-restore-incident-runbook.md`; linked from compose runbook (U7).

**Not claimed green in this session:** three-file Compose live AE2 capture, AE3 disposable restore digests, AE4 preview/range + LightRAG rebuild-on-empty-runtime operator digests (scripts exist; live digests residual-or-manual).

## Commands / results (unit-test altitude)

```bash
cd app
uv run --frozen --python 3.12 --extra test pytest \
  tests/test_stack_backup_restore_recon.py \
  tests/test_stack_restore_continuity.py \
  tests/test_stack_image_rollback_drill.py \
  tests/test_stack_incident_reclaim_drill.py \
  tests/test_stack_restore_lightrag_rebuild.py \
  -q
```

Observed (2026-07-28): **46 passed** (11 backup/restore/recon + 10 continuity + 5 image-rollback + 13 incident-reclaim + 7 LightRAG rebuild helpers).

Downgrade refuse path (AE5 documentation assert):

```bash
cd app
uv run --frozen --python 3.12 python scripts/stack_image_rollback_drill.py --attempt-downgrade
```

Expected: non-zero exit; stderr prints refuse of improvised down migration / `alembic downgrade` and points to restore path.

## Acceptance examples

| AE | Altitude | Result |
| --- | --- | --- |
| AE1 | Inventory + prerequisite citations | **pass** — inventory frozen; Path 2 / P12-05/06/07/08 / filesystem-dev / KMS/HA named residuals |
| AE2 | Write-fenced S3 key-centric capture helpers | **unit pass** — fence/manifest/census/byte-archive helpers green; **Compose live three-file capture = residual-or-manual** (not invented green) |
| AE3 | Isolated restore + key/ETag recon | **unit pass** — companion-key/decrypt proof, live-volume refuse, ETag hard-fail helpers green; **Compose live disposable restore digests = residual-or-manual** |
| AE4 | Continuity + LightRAG rebuild | **unit pass (R13 + R14 helpers)** — continuity + rebuild dry-run/helpers green; **Compose live preview/range + empty-runtime rebuild digests = residual-or-manual** (P5-04 live pytest topology credit only) |
| AE5 | Prior image @ same head + downgrade refuse | **unit pass** — digest record/go-no-go/refuse paths green; live prior-image swap ready+smoke = residual-or-manual |
| AE6 | API+worker kill / restore-then-reclaim / missing-object | **unit pass** — mode plans + fail-safe observables green; Compose live kill/reclaim digests = residual-or-manual |
| AE7 | Tracker + runbook + residual honesty | **pass** — this evidence + runbook + master-build-plan P12-04 DONE with named Compose-live residual |

## Absorbed upstream “→ P12-04” residuals (cite-close)

Closed **at drill-procedure / unit altitude** under this evidence (do not reopen adapter/schema work). Live Compose operator digests remain residual where noted.

| Upstream residual | Source | Cite-close |
| --- | --- | --- |
| Empty-volume rebuild / backup-restore drills | P5-04 | Closed under P12-04 scripts/runbook; **Compose live rebuild digest residual** |
| Opt-in live MinIO put/get/range; three-file live+minio matrix | P10-04 | Closed under P12-04 capture/restore/recon procedures; **live matrix operator digests residual** |
| Backup/restore of preview derivatives; combined live+minio+preview matrix | P10-06 | Closed under P12-04 census (preview/page-map) + continuity seed/checks; **live preview/range digests residual** |
| Backup/restore, image rollback, failed-worker incident drills | P12-01 | Closed under P12-04 U2/U4/U5 + runbook; Path 2 still unsupported |
| Backup/restore of redactions + audit continuity | P12-03 | Closed under P12-04 U3 continuity (R13) at unit altitude; **Compose live continuity digests residual** |
| Production HA / incident drills (P10-03 half) | P10-03 | Multi-failure Compose scripts landed; HA remains P12-08; single-worker reclaim stays P10-03 credit |

## Privacy checklist (evidence must stay clean)

- [x] No committed PG dumps, object byte archives, or companion key files  
- [x] No paste of `CONFIG_ENCRYPTION_KEY`, MinIO/S3 access keys, or temporary export credentials  
- [x] No full `docker compose config` or full env dumps in this file  
- [x] Commands redacted to digests/fingerprints/ETag markers language only  
- [x] Dump/archive and companion key documented as separately pathed; shred on restore success/failure  
- [x] Runtime / `domain-runtimes` excluded from backup unit (topology precedence)

## Non-claims

- Not production RPO≤15m / RTO≤4h acceptance (P12-08).  
- Not Path 2 supported populated upgrade/contraction.  
- Not KMS/escrow, HA/cloud failover, or staging/prod registry digests (P12-08).  
- Not TLS / stream-drain / deployed byte-range (P12-05).  
- Not SBOM / immutable release digests (P12-06).  
- Not browser E2E / governed-preview navigation / capacity (P12-07).  
- Not filesystem object adapter as DR final boundary.  
- Not metadata-only `stack_object_store_recon.py --mode export` as restore archive.  
- Not live MinIO data-dir tar as AE2 success.  
- Local drill digests ≠ P12-06 release manifest.

## Residuals handed forward

| Residual | Owner |
| --- | --- |
| Opt-in three-file live capture / restore / continuity / rebuild matrix operator digests | Operator / this slice residual (attach digests when run) |
| TLS / stream-drain / direct-API denial / deployed byte-range PDF | P12-05 |
| SBOM / immutable release digests | P12-06 |
| Browser E2E / a11y / capacity / governed-preview navigation | P12-07 |
| Production acceptance digests, real RPO/RTO, KMS/escrow, HA/cloud failover, Path 2 release decision | P12-08 |
| Filesystem object adapter as production/DR boundary | Development-only — never AE green |
| MinIO bucket versioning / `versionId`-pinned GetObject | Optional future — not Phase-1 DONE |

## Tracker

- P12-04 → DONE (unit altitude + runbook; Compose live residual named above)  
- Phase P12 remains NOT_STARTED until remaining P12 tasks and production gates close  
- DRIFT-15 production-store claim stays with P10-04; P12-04 does not reopen filesystem-as-DR
