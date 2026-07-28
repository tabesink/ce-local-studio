---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P10-04 Local-Production MinIO Object Store - Plan
type: feat
date: 2026-07-28
deepened: 2026-07-28
---

# P10-04 Local-Production MinIO Object Store - Plan

## Goal Capsule

- **Objective:** Close P10-04 by adding one S3-compatible governed object-store adapter exercised against locally deployed MinIO, with readiness, range/delete/reconciliation hooks, Compose overlay wiring, and backup/recon contracts for P12-04 — while keeping the filesystem adapter development-only and default for CI.
- **Authority:** AGENTS.md; docs/architecture/deployment-topology.md object-store decision (2026-07-28); docs/architecture/production-adaptation-blueprint.md; docs/tech-stack.md; DRIFT-15; docs/master-build-plan.md P10-04; P12-04 hook consumer contract.
- **Execution profile:** Reuse existing `ObjectStorage` port; kind-selector + opt-in Compose overlay; YAGNI — no multi-cloud, bucket UI, replication, HA, or port-level list API.
- **Readiness checkpoint:** Implementation-ready after 2026-07-28 deepening.
- **Stop conditions:** Stop if promoting filesystem adapter to production, inventing a second storage API/port, requiring cloud S3 for DONE, adding `list` to the runtime port, or claiming DRIFT-15 closed from filesystem-only readiness.
- **Tail ownership:** P12-04 backup drills consume recon hooks; P10-06 preview keys extend the same census shape; P12-06 digests; P12-08 production acceptance.

---

## Product Contract

### Summary

Local-production and test environments use MinIO behind one S3-compatible adapter implementing the existing governed object-store port. Development and default Compose/CI keep filesystem. API/workers share MinIO for concurrent multi-user access.

Product Contract preservation: Product Contract unchanged during deepening (planning sections only).

### Problem Frame

Only the filesystem adapter exists; architecture forbids filesystem as production store. Without MinIO, concurrent multi-replica workers cannot safely share source bytes and P12-04 cannot prove production-like object version/key consistency.

### Actors

| Actor | Role |
| --- | --- |
| Operator | Runs Compose with MinIO overlay; runs recon/export scripts |
| API/Worker | Put/get/range/delete via port |
| Coding agent | Adapter, Compose, readiness, tests, evidence |

### Key Flows

**F1 — Compose MinIO.** Opt-in overlay starts private MinIO + one-shot bucket bootstrap → API/worker configured with `CE_OBJECT_STORE_KIND=s3` and S3 endpoint/credentials → ready probe (ephemeral put+delete through composed factory) succeeds.

**F2 — Object lifecycle.** Upload put → DB metadata → get/range → delete; path traversal rejected; keys opaque flat `obj_*`; missing object fails closed on content routes.

**F3 — Reconciliation hook.** Operator scripts verify/export DB-referenced keys vs store (hard-fail missing/mismatch; warn orphans) for P12-04 — PostgreSQL remains inventory authority.

### Requirements

- R1. Inventory `docs/_scratch/p10-04-minio-object-store-inventory.md`.
- R2. One S3-compatible adapter implementing existing `ObjectStorage` port (put/put_key/get/get_range/delete/exists, integrity metadata, S3-native range, sanitized errors).
- R3. Opt-in Compose MinIO overlay (private network; loopback publish only if ops need); filesystem remains default for pure-dev and default CI; least-privilege single-bucket bootstrap; no public/anonymous ACL.
- R4. `/health/ready` and worker readiness include object-store capability when S3 adapter selected, via the same composed factory (ephemeral put+delete); private reason `object_store_unavailable`; safe 503 with no store leaks.
- R5. Contract/unit tests for success, range, delete idempotency, traversal rejection, missing object, error sanitization — against mocked S3 and/or opt-in MinIO; default CI keeps filesystem.
- R6. Document env vars and operator recon/export hooks (verify / export / orphan-warn / store-kind / version-marker policy) for P12-04; recon output is operator-confidential.
- R7. Evidence + tracker; advance DRIFT-15; mark P10-04 DONE only with MinIO/S3 path proven — not filesystem residual alone.

### Acceptance Examples

- AE1. Compose MinIO overlay ready; upload→range→delete succeeds across API/worker.
- AE2. Filesystem still works in development / default Compose profile.
- AE3. Missing or mismatched referenced object fails closed for content routes (`503 document_content_unavailable`).
- AE4. No bucket management UI, multi-cloud abstraction, port-level list API, or default-CI MinIO requirement added.

### Scope Boundaries

#### In scope

- S3 adapter; MinIO Compose overlay; readiness; contract tests; operator recon/export hooks; docs/evidence; privacy matrix for store failures

#### Deferred to Follow-Up Work

- Cloud AWS-only hardening beyond S3 API
- Upload orphan compensation task
- Write-fenced backup/restore orchestration (P12-04)
- Preview key census SQL (P10-06 extends hook input)

#### Outside this product's identity

- Multi-cloud SDK sprawl; Redis; public object URLs; browser/BFF access to MinIO; KMS/secret-manager product surface

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale | Units |
| --- | --- | --- | --- |
| KTD1 | One S3-compatible adapter; MinIO as local-production target | Architecture decision 2026-07-28; YAGNI | U2 |
| KTD2 | Reuse `ObjectStorage` Protocol; never add `list`/admin to the runtime port | Port stays upload/content/delete-shaped; recon uses operator-side S3 APIs | U2, U4 |
| KTD3 | Dev/default-Compose filesystem retained | Fast loop and default CI; does **not** close P10-04 or DRIFT-15 production residual | U1, U3 |
| KTD4 | Closed `CE_OBJECT_STORE_KIND=filesystem\|s3` + one `object_store_from_settings` factory | Mirrors LightRAG/controller kind selectors; `SourceStorage`, API readiness, and worker readiness must share the factory | U1, U2 |
| KTD5 | MinIO lives in opt-in overlay (e.g. `compose.stack.minio.yml`); base stack unchanged | Parallel to `compose.stack.live.yml`; default CI/`verify.sh` stay filesystem | U1, U3 |
| KTD6 | One-shot `minio-init` after MinIO healthy; **init admin creds** (`MINIO_ROOT_*` or equivalent) never mounted on api/worker; distinct least-privilege app `CE_S3_*` for runtime | No lifespan bucket creation; credentials never in DTOs/logs/evidence | U3 |
| KTD7 | boto3 only via optional `object-store` extra; MinIO overlay uses a build arg (mirror `CE_STACK_LIVE_IMAGE`) so api/worker images install the extra; default image/CI stay slim | Reject minio SDK / aioboto3 in product adapter / hand-rolled SigV4 / multi-cloud layer | U2, U3 |
| KTD8 | One bucket; S3 object key == port key (`obj_*`); reject `/`, `..`, empty | Same semantics as filesystem adapter and DB `original_object_key` | U2 |
| KTD9 | Readiness = ephemeral put+delete through composed store | MinIO container health ≠ capability; never substitute directory/root checks when kind=s3 | U2, U3 |
| KTD10 | Operator recon/export hook contract for P12-04 | verify / export / orphan-warn / store-kind; PG keys+hashes authoritative; version marker pinned (ETag and/or versionId); no HTTP route | U4 |
| KTD11 | Two-tier S3 credentials: runtime Put/Get/Delete/Head on object keys **without** `ListBucket`; recon/export uses separate operator List+Head credentials (host/sidecar env, never api/worker) | Keeps orphan-warn listing off the product runtime trust surface | U3, U4 |

### Assumptions

- boto3 lands as optional `object-store` extra; MinIO overlay image build installs it (parallel to live LightRAG image gate); default Dockerfile/CI stay slim.
- Single-bucket design is enough for Phase 1, including later P10-06 preview objects in the same bucket.
- Env name `CE_OBJECT_STORE_KIND` (not inventing a second selector family).
- Export manifests are secret-class operator material (aligned with P12-04); evidence may cite digests/counts/policy only.

### High-Level Technical Design

```mermaid
flowchart TB
  subgraph default [Default Compose / CI]
    FS[FilesystemObjectStore]
    VOL[stack-source-storage volume]
    FS --> VOL
  end
  subgraph overlay [Opt-in MinIO overlay]
    INIT[minio-init bucket bootstrap]
    MINIO[MinIO private network]
    S3[S3ObjectStore boto3]
    INIT --> MINIO
    S3 --> MINIO
  end
  CFG[CE_OBJECT_STORE_KIND]
  FACTORY[object_store_from_settings]
  CFG --> FACTORY
  FACTORY -->|filesystem| FS
  FACTORY -->|s3| S3
  SRC[SourceStorage / content routes]
  READY[API + worker readiness probe]
  SRC --> FACTORY
  READY -->|ephemeral put+delete| FACTORY
  PG[(PostgreSQL keys + hashes)]
  RECON[Operator recon/export scripts]
  PG -->|referenced census| RECON
  RECON -->|verify/export/orphan-warn| MINIO
```

Readiness proves **capability**. Recon proves **referential integrity**. Partial restore can pass ready and fail recon — P12-04 owns the stricter gate.

### System-Wide Impact

- **Composition:** Today `storage_from_settings` and `probe_object_store` hardwire `object_store_from_root`. Both must move to the shared factory or product and readiness diverge.
- **Dual-root residual:** When kind=s3, governed bytes live in MinIO. Overlay **drops the shared `stack-source-storage` object-bytes volume** but retains a **slim per-replica (or ephemeral) `CE_SOURCE_STORAGE_ROOT` mount** for legacy domain sizing/cleanup paths — inventory and compose tests must pin this layout.
- **Multi-replica:** All replicas share one MinIO bucket/endpoint and the same least-privilege app credentials; keys stay globally unique via `new_object_key()` + DB uniqueness.
- **Failure propagation:** Missing/mismatched referenced objects → `503 document_content_unavailable` on content/prep reads; never redirect, presign, empty success, or restore query eligibility.
- **Torn windows:** Put-after-flush / crash-before-commit can orphan objects (warn-only in recon); DB row without object is hard-fail on verify/content.
- **Downstream:** P12-04 U2 consumes hook contract; P10-06 adds preview keys to the same verify/export input shape without a second inventory model.
- **Non-DR boundary:** Filesystem adapter and host volume walks are explicitly non-DR; P12-04 refuses filesystem-only drill stacks.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| CI flakiness / scope creep with MinIO | Opt-in overlay + marker; default `verify.sh` stays filesystem |
| Credential / infrastructure leakage | Fail-closed S3 settings; env/Compose-secrets only; privacy scans for access/secret keys, Authorization, endpoint/bucket/key in errors/logs/ready 503 |
| Raw botocore errors leak keys/endpoints | Map all failures to closed `ObjectStorageError` strings matching filesystem adapter; contract tests with sentinel strings |
| Readiness probe overshares | Probe uses product factory put+delete only — no ListObjects/HeadBucket inventory in ready path |
| Full-object fetch on range | `get_range` must use S3 Range header; tests cover inclusive bounds and unsatisfiable ranges |
| Over-broad MinIO policy / published ports | Single app bucket, deny anonymous; init admin vs app CRUD vs recon List tiers; MinIO not on browser-facing network; frontend never receives store secrets |
| Recon script dumps secrets or becomes a product API | Operator-only CLI; closed errors; export manifests ephemeral/gitignored; evidence records digests/policy only; no HTTP/BFF route |
| Runtime inherits ListBucket | App policy excludes List; recon uses separate list-capable operator credentials |
| Composition drift | Factory shared by sources + readiness; compose tests assert overlay env and volume drop |
| P12-04 blocked on vague hooks | Freeze verify/export/orphan-warn/store-kind + version-marker policy in U4 |

### Open Questions

#### Resolved During Planning

- Store kind selector name → `CE_OBJECT_STORE_KIND` (mirror existing kind-selector family).
- Client library → boto3 only (optional extra).
- Compose shape → opt-in overlay; base stack filesystem.
- Runtime port list API → rejected; operator-side listing only.
- Inventory authority → PostgreSQL keys+hashes; MinIO is byte/version backing.

#### Deferred to Implementation

- Exact MinIO versioning on vs ETag-only marker field names in the export manifest (pin one policy in U4 evidence; both plans already allow etag/versionId).

---

## Implementation Units

### U1. Object-store inventory

**Goal:** Freeze port/Compose/settings seams and dispositions.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `docs/_scratch/p10-04-minio-object-store-inventory.md`

**Approach:** Disposition retain filesystem for default/dev; add S3 adapter + kind factory; opt-in Compose overlay; readiness factory rewiring; recon hooks for P12-04. Document dual-root residual (slim local `CE_SOURCE_STORAGE_ROOT` vs S3 bytes), credential tiers (init/app/recon), and MinIO overlay Dockerfile/`object-store` extra install path (mirror live image gate).

**Patterns to follow:** `docs/_scratch/p4-01-source-storage-inventory.md`; kind-selector inventories from P5-04/P3-02

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Inventory complete with retain/modify/add/defer rows for every seam named above, including packaging and credential-tier rows.

---

### U2. S3-compatible adapter and settings factory

**Goal:** Implement S3 adapter behind existing port and one settings factory.

**Requirements:** R2, R5 (adapter contract parity), R6 (settings/env surface); KTD1, KTD2, KTD4, KTD7, KTD8, KTD9

**Dependencies:** U1

**Files:**
- Create: `app/context_engine/adapters/s3_object_store.py`
- Modify: `app/context_engine/adapters/object_storage.py` (factory; keep filesystem + protocol)
- Modify: `app/context_engine/config.py` (`CE_OBJECT_STORE_KIND`, `CE_S3_*` with secrets `repr=False`)
- Modify: `app/context_engine/services/sources.py` (`storage_from_settings` → factory)
- Modify: `app/context_engine/services/readiness.py` (`probe_object_store` → factory, including S3 probe path)
- Modify: `app/pyproject.toml` (optional `object-store` extra for boto3)
- Modify: `app/Dockerfile` (MinIO/object-store install gate mirroring `CE_STACK_LIVE_IMAGE` pattern)
- Create: `app/tests/test_s3_object_store.py`
- Optionally extend: `app/tests/test_object_storage.py` (shared contract parametrize)

**Approach:** Minimal boto3 S3 client wrapper with MinIO endpoint/path-style; opaque keys; S3-native Range GET; idempotent delete; reject traversal before remote call; map all botocore failures to closed `ObjectStorageError` strings. Fail closed when kind=s3 and required env missing/malformed. No public/presigned URLs. Wire `storage_from_settings` as `SourceStorage(settings.source_storage_root, store=object_store_from_settings(settings))` — do not leave the implicit `object_store_from_root` default path. Change `probe_object_store` to accept `Settings` (or the composed store) so readiness cannot stay root-only. Pin `object-store` optional extra + Dockerfile build arg so MinIO overlay images install boto3 without bloating default CI.

**Patterns to follow:** `FilesystemObjectStore` contract; `controller_from_settings` / `index_client_from_settings` kind selection; `app/tests/test_object_storage.py`

**Execution note:** Start from filesystem contract parity tests, then S3 adapter with mocked client; live MinIO optional later in U3/U4.

**Test scenarios:**
- Happy: put/get/get_range/delete/`exists` false after delete for known bytes (match filesystem test shape).
- Happy: `StoredObject` size + SHA-256 + opaque `obj_*` key.
- Edge: invalid/empty/`../`/`/` keys rejected before remote call.
- Edge: inclusive range bounds, `end=None`, unsatisfiable range → closed range errors.
- Edge: delete twice → no error.
- Error: missing object → `ObjectStorageError("Object unavailable.")`.
- Error: injected sentinel endpoint/bucket/key/credential in mock failures never appear in raised messages.
- Integration: `object_store_from_settings` filesystem default vs s3 construction; missing S3 env fail-closed.
- Integration: readiness probe accepts Settings/composed store — s3-kind mocked put+delete path (not root-dir-only assertion).
- Edge: Dockerfile/extra gate documented — default image lacks boto3; MinIO overlay build installs `object-store`.

**Verification:** S3 + factory unit/contract tests green; sources/readiness composition uses factory; packaging path frozen in inventory.

---

### U3. Compose MinIO overlay and readiness

**Goal:** Runnable local-production MinIO profile without changing default Compose/CI.

**Requirements:** R3, R4, R6 (env/runbook documentation), AE1, AE2; KTD3, KTD5, KTD6, KTD9, KTD11

**Dependencies:** U2

**Files:**
- Create: `app/compose.stack.minio.yml`
- Modify: `app/.env.stack.example` (MinIO overlay section; init vs app vs recon credential placeholders)
- Modify: `docs/operations/compose-stack-runbook.md` (split filesystem vs MinIO readiness)
- Extend: `app/tests/test_compose_stack_config.py`
- Extend: `app/tests/test_health_contract.py`, `app/tests/test_worker_readiness.py` (compose/integration negatives only — factory rewiring owned by U2)

**Approach:** Overlay adds MinIO + init job; sets api/worker `CE_OBJECT_STORE_KIND=s3` and internal endpoint; drops shared object-bytes volume but keeps slim local `CE_SOURCE_STORAGE_ROOT` for domain paths. Init uses admin/`MINIO_ROOT_*` only on the init service; api/worker mount distinct least-privilege `CE_S3_*` (Put/Get/Delete/Head, no ListBucket). Bootstrap creates one private bucket with anonymous denied. Ready fails closed when selected store unavailable (uses U2 factory). Do not wire MinIO into default `scripts/verify.sh`.

**Patterns to follow:** `compose.stack.live.yml` overlay; P10-02 put+delete readiness; compose config fail-closed env tests

**Test scenarios:**
- Happy / Covers AE2: default `compose.stack.yml` unchanged — filesystem root/volume, no minio, no S3 env.
- Happy / Covers AE1: base + minio overlay resolves — minio on `ce_stack`, kind=s3, init before api/worker, internal endpoint, slim local root retained.
- Error: overlay missing required MinIO env → compose config fails closed.
- Error: kind=s3, unreachable endpoint → readiness `object_store_unavailable`; HTTP 503 safe envelope; privacy scan clean.
- Edge: init admin env not present on api/worker/frontend; app `CE_S3_*` not on frontend.
- Edge: compose asserts app env lacks list-capable recon credentials.
- Integration (opt-in): ready green with MinIO up; cross api/worker get on same key proves shared store.

**Verification:** Compose config + readiness tests green; runbook documents both profiles.

---

### U4. Contract tests, recon hooks, and evidence

**Goal:** Freeze P12-04 hook contract; prove AE3/AE4; close P10-04 and advance DRIFT-15.

**Requirements:** R5 (recon/content-route extensions), R6 (hook contract docs), R7, AE3, AE4; KTD2, KTD10, KTD11

**Dependencies:** U2, U3

**Files:**
- Extend: `app/tests/test_s3_object_store.py`
- Create: `app/scripts/stack_object_store_recon.py` (name may be `stack_object_store_export.py` if clearer — keep one entrypoint with verify/export/orphan-warn modes)
- Create: `app/tests/test_stack_object_store_recon.py`
- Extend: `app/tests/test_documents_service.py` (and HTTP contract if needed) for AE3
- Create: `docs/_scratch/p10-04-minio-object-store-evidence.md`
- Modify: `docs/master-build-plan.md`, `docs/brownfield-refactor-register.md` DRIFT-15
- Modify: `.gitignore` and/or runbook (export output paths ephemeral; never commit manifests)

**Approach:** Prove put/get/range/delete/missing/traversal/sanitization. Publish Recon Hook Contract: SQL-derived `{key, sha256, size?}` input; verify hard-fails missing/hash/size/version mismatch; export emits versioned manifest (`storeKind`, `capturedAt`, objects with key/etag/versionId?/sizeBytes/contentSha256); orphan-warn for unreferenced store keys via **operator List credentials** (not api/worker env); `storeKind` gate for P12-04. Operator-only; no credential printing. Export manifests are secret-class — evidence records digest, object count, and version-marker policy only (never committed key lists). Filesystem remains development-only residual. P10-04 export feeds P12-04 R6 object-tree digest; schemas differ — do not treat P12-04 R6 as the export schema authority.

**Patterns to follow:** `docs/_scratch/p10-02-stack-smoke-evidence.md`; P12-04 R4/R9/KTD5; `stack_smoke_core.py` CLI shape; documents service `ObjectStorageError` → `document_content_unavailable`

**Test scenarios:**
- Happy: recon verify/export matching keys/hashes → pass + stable digest.
- Error: missing referenced key → hard-fail.
- Error: hash or size mismatch → hard-fail.
- Edge: orphan store key → warn-only (document policy).
- Edge: `source_images.object_key` missing → hard-fail like originals.
- Error / Covers AE3: content route with missing object → 503 `document_content_unavailable`, no key in message.
- Error / Covers AE3: content/prep route when store bytes hash or size disagree with DB → 503 `document_content_unavailable`, no key leak (if service already hashes on read; otherwise document as recon-hard-fail only and narrow AE3 prose in evidence).
- Edge: ready may pass while referenced object absent (capability ≠ integrity) — document; recon fails.
- Privacy: recon mock failures with sentinel credentials never print `CE_S3_*` or raw botocore bodies.
- Privacy: evidence template / checklist rejects embedding raw export manifest bodies.
- Edge: recon script env can List; api/worker settings fixture cannot.
- Edge / Covers AE4: evidence explicitly denies bucket UI, multi-cloud, HA, default CI MinIO.

**Verification:** Tracker DONE; DRIFT-15 advanced for local-production MinIO + readiness; P12-04 can attach to frozen hooks; opt-in live MinIO smoke acceptable as evidence altitude.

---

## Verification Contract

- Adapter contract tests (filesystem parity + S3); factory composition; Compose overlay config; readiness privacy.
- Opt-in live MinIO smoke acceptable as evidence altitude; default CI stays filesystem.
- Privacy matrix: credentials, endpoint/bucket/key/path, raw storage errors, recon manifest classification — each owned by U2–U4 tests; extend cross-sink privacy scan with S3 sentinels for ready/`document_content_unavailable`/worker-not-ready where feasible.
- Recon hook contract frozen for P12-04; readiness ≠ referential integrity documented.
- Credential tiers proven by compose-config tests (init ≠ app ≠ recon List).

## Definition of Done

R1–R7 and AE1–AE4 satisfied; filesystem not production evidence; MinIO/S3 path proven; P10-04 DONE; DRIFT-15 advanced without claiming KMS/HA/multi-cloud.

## Sources & Research

- docs/architecture/deployment-topology.md (object-store decision 2026-07-28)
- docs/architecture/production-adaptation-blueprint.md
- docs/tech-stack.md
- docs/master-build-plan.md P10-04
- docs/plans/2026-07-28-005-feat-p12-04-backup-restore-drills-plan.md (hook consumer)
- app/context_engine/adapters/object_storage.py
- docs/_scratch/p4-01-source-storage-inventory.md
- docs/_scratch/p10-02-stack-smoke-evidence.md
- Deepening research 2026-07-28: architecture-strategist, repo-research-analyst, security-sentinel, data-integrity-guardian

---

## Deferred / Open Questions

### From 2026-07-28 review

- **Private endpoint allowlist for `CE_S3_ENDPOINT`** — U2 S3 adapter / Risks (P1, security-lens-reviewer, confidence 75)

  Fail-closed validation that rejects public-host endpoints may over-constrain staging or future cloud S3 shapes. Decide whether Phase 1 MinIO overlay relies on Compose network isolation + documented private DNS only, or adds a settings allowlist (internal DNS / loopback / CIDR) before implementation.

- **Freeze live + MinIO multi-overlay stack contract now** — KTD5 / Tail ownership P12-04 (P2, feasibility-reviewer, confidence 75)

  P12-04 will need `-f compose.stack.yml -f compose.stack.live.yml -f compose.stack.minio.yml` with combined build args, networks, and volume matrix. Decide whether U1/U3 inventory freezes that stacking contract now or defers the combined matrix until P12-04 with only pairwise overlays proven in P10-04.
