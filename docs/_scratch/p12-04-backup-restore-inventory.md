# P12-04 Backup Restore Inventory

Date: 2026-07-28  
Status: U1 inventory complete; P12-04 tracker closure under `docs/_scratch/p12-04-backup-restore-evidence.md` (unit altitude + runbook; Compose live digests residual).  
Plan: `docs/plans/2026-07-28-005-feat-p12-04-backup-restore-drills-plan.md`  
Authority: `docs/master-build-plan.md` P12-04; FR-11; `docs/architecture/deployment-topology.md` (backup/DR; topology precedence: LightRAG/runtime disk is not backup authority); prerequisite evidence revisions below.

## Disposition legend

| Value | Meaning |
| --- | --- |
| `retain` | Already correct; keep |
| `modify` | Change in this slice |
| `add` | New script/test/doc/wiring in this slice |
| `credit` | Proven elsewhere; cite — do not re-own |
| `defer` | Explicit residual (other P12 / future / development-only) |

## Prerequisites (DONE — cite, do not re-prove)

| Prerequisite | Evidence | What P12-04 consumes |
| --- | --- | --- |
| P5-04 real private LightRAG runtime | `docs/_scratch/p5-04-lightrag-real-runtime-evidence.md` | Empty-runtime rebuild topology; live overlay; submit→ready→retrieve credit |
| P10-04 MinIO + S3 adapter + recon hooks | `docs/_scratch/p10-04-minio-object-store-evidence.md` | Store kind, recon CLI, ETag+sha256+objectTreeDigest policy |
| P10-06 governed preview derivatives | `docs/_scratch/p10-06-governed-preview-evidence.md` | Preview/page-map keys, cleanup, preview-derivative restore residual |
| P12-01 Path 1 preflight/readiness | `docs/_scratch/p12-01-populated-compatibility-evidence.md` | Refuse→restore/recreate migrate go/no-go |

## Tracker deliverable → lane map

| Tracker phrase | Lane | Owner unit |
| --- | --- | --- |
| backup/restore | Capture + restore/recon | U2 |
| MinIO original/preview/derived-object consistency | Restore/recon (PG→refs + ETag/sha256) | U2 |
| image rollback | Image rollback | U4 |
| failed-worker recovery and incident drills | Multi-failure | U5 |
| rebuild/reconciliation of private per-domain LightRAG | LightRAG rebuild | U6 |
| (continuity implied by topology DR) | Continuity | U3 |
| inventory / evidence / runbook | Closure | U1 + U7 |

## Lane: Backup capture (byte archive)

| Seam | Fact today | Disposition |
| --- | --- | --- |
| Write-fence script | Absent — only Compose `stop` / worker grace pattern | `add` (U2) |
| Allowed writers during capture | Not enumerated in tooling | `add` — api/worker only; seed before fence |
| Capture order | Undocumented | `add` — idle → S3 Get census bytes → `pg_dump` → manifest (one fence episode) |
| S3 key-centric byte archive | **Absent** | `add` (U2) — DONE path per KTD5 |
| `stack_object_store_recon.py --mode export` | Metadata JSON only (sha256/etag/objectTreeDigest) | `credit` digest helpers; **not** byte archive |
| Live MinIO data-dir tar while MinIO runs | Would tear; not key-centric | refuse — non-DONE |
| Consistency manifest (PG + objectTreeDigest + key fingerprint + head + digests) | Absent | `add` (U2) |
| Runtime / `domain-runtimes` in backup unit | Must be excluded (topology precedence) | `retain` exclusion — prove by archive listing |
| Filesystem object adapter as DR boundary | Development-only residual | `defer` — not AE2 green |

## Lane: Restore / recon (ETag/sha256 + PG→refs)

| Seam | Fact today | Disposition |
| --- | --- | --- |
| PG→refs census (original, images, preview, page-map) | **Absent** — recon needs hand-built `--refs` | `add` (U2) |
| Preview/page-map columns + delete cleanup | Landed (P10-06) | `credit` |
| `verify` mode | sha256/size only — **no ETag compare** | `credit` + `modify`/extend in U2 for ETag hard-fail |
| `orphan-warn` | Warn-only | `credit` |
| Disposable Compose project / volume refuse | Absent | `add` — refuse by live project resolved volumes |
| PutObject restore credentials | Recon policy has Get/List only | `add` — app or MinIO-root after minio-init |
| Three-file matrix boot proof | Deferred by P10-04/P10-06 | `add` precondition before AE2/AE4 |

## Lane: Key recoverability

| Seam | Fact today | Disposition |
| --- | --- | --- |
| Fernet / `CONFIG_ENCRYPTION_KEY` | Landed (P2-02) | `credit` |
| Matrix companion-key custody + shred | Absent | `add` (U2) |
| Dump+key co-packaging forbid | Absent | `add` (R11 / Constraints) |
| KMS/escrow | Not in product | `defer` → P12-08 |

## Lane: Continuity (incl. preview/range)

| Seam | Fact today | Disposition |
| --- | --- | --- |
| Drill seeder (source, preview, redacted turn, invalid ref, audit) | Absent | `add` (U3) |
| Continuity script (login, redaction, refs, audit SQL, preview/range, tombstones) | Absent | `add` (U3) — R13 pre-rebuild only |
| Citations/anchors after rebuild | Requires U6 | `add` under R14 / U6 |
| Topology continuity binding | deployment-topology DR checklist | `retain` — U3 in-slice for this reason |
| Deployed-ingress range | Not this slice | `defer` → P12-05 |
| P12-03 redaction/audit after backup | Deferred to P12-04 | absorb via U3/U7 cite-close |

## Lane: Image rollback

| Seam | Fact today | Disposition |
| --- | --- | --- |
| Live prior-digest swap drill | Absent | `add` (U4) |
| Improvised down migration / `alembic downgrade` refuse | Documented in topology, security-ops, P1-01 | `credit` + assert in U4/U7 |
| Release digests / SBOM | Not this slice | `defer` → P12-06/08 |

## Lane: Multi-failure

| Seam | Fact today | Disposition |
| --- | --- | --- |
| P10-03 single-worker kill+reclaim | Runbook + PG suites | `credit` — do not re-own |
| `stack_smoke_worker.py` | Present | `credit` |
| API+worker death + restore-then-reclaim + missing-object fail-safe | Absent | `add` (U5) |
| HA / multi-replica | Not this slice | `defer` → P12-08 |

## Lane: LightRAG rebuild (three-file matrix)

| Seam | Fact today | Disposition |
| --- | --- | --- |
| `compose.stack.live.yml` + native client | Landed (P5-04) | `credit` |
| P5-04 live pytest submit→ready→retrieve | Present | `credit` topology/algorithm — not the drill |
| Empty-volume/bind rebuild Compose drill | **Absent** (P5-04 residual → P12-04) | `add` (U6) |
| Empty `CE_STACK_LIVE_RUNTIME_ROOT` bind (not only named volume) | Required by plan | `add` (U6) |
| Product start→index paths | `start_domain` / `SourceIndexWorker` | `retain` product paths |

## Compose overlays

| File | Role | Disposition |
| --- | --- | --- |
| `app/compose.stack.yml` | Base stack | `retain` |
| `app/compose.stack.minio.yml` | MinIO + S3 kind | `credit` / use |
| `app/compose.stack.live.yml` | Real LightRAG | `credit` / use |
| Three-file combined matrix | Deferred; required for AE2/AE4 | `add` proof in U2/U6 |

## Runbook / evidence / tracker

| Seam | Fact today | Disposition |
| --- | --- | --- |
| `docs/operations/compose-stack-runbook.md` “restore current-head backup” | Placeholder | `modify` (U7) |
| `docs/operations/backup-restore-incident-runbook.md` | Absent | `add` (U7) |
| `docs/_scratch/p12-04-backup-restore-evidence.md` | Absent | `add` (U7) |
| Tracker P12-04 | `NOT_STARTED` | `modify` only at U7 with AE1–AE7 |

## Residuals (honest non-claims)

| Residual | Owner |
| --- | --- |
| Path 2 populated upgrade/contraction | Future / P12-08 release decision |
| TLS / stream-drain / direct-API denial / deployed byte-range | P12-05 |
| SBOM / immutable release digests | P12-06 |
| Browser E2E / a11y / capacity / governed-preview navigation | P12-07 |
| KMS/escrow, HA/cloud failover, production RPO/RTO, staging/prod digests | P12-08 |
| Filesystem object adapter as production/DR boundary | Development-only — never AE green |
| MinIO bucket versioning / `versionId`-pinned GetObject | Optional future — not Phase-1 DONE |
| Orphan-count hard fail threshold | Advisory — warn-only remains default unless drill go/no-go later tightens |

## Explicit gaps for U2 (not credited as complete)

1. No write-fence / ordered capture script.  
2. `export` ≠ byte archive — S3 key-centric Get/Put not implemented.  
3. No PG→refs census (incl. preview/page-map).  
4. No ETag hard-fail in recon (verify is sha256/size only).  
5. No three-file Compose smoke/proof.  
6. No `docs/_scratch/p12-04-*` evidence yet (inventory only).  
7. No companion-key custody/shred helper.

## Non-goals in this inventory

- No DONE language for P12-04.  
- No Path 2, TLS, SBOM, browser E2E, KMS/HA, or filesystem-as-production-store as in-scope DONE.  
- No reopening of P5-04/P10-04/P10-06 adapter/schema work under residual absorption.
