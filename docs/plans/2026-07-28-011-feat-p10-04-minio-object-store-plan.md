---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P10-04 Local-Production MinIO Object Store - Plan
type: feat
date: 2026-07-28
---

# P10-04 Local-Production MinIO Object Store - Plan

## Goal Capsule

- **Objective:** Close P10-04 by adding one S3-compatible governed object-store adapter exercised against locally deployed MinIO, with readiness, range/delete/reconciliation, Compose wiring, and backup hooks for P12-04 — while keeping the filesystem adapter development-only.
- **Authority:** AGENTS.md; docs/architecture/deployment-topology.md object-store decision (2026-07-28); docs/architecture/production-adaptation-blueprint.md; docs/tech-stack.md; DRIFT-15; docs/master-build-plan.md P10-04.
- **Execution profile:** Reuse existing object_storage port; YAGNI — no multi-cloud, bucket UI, replication, or HA orchestration.
- **Readiness checkpoint:** Implementation-ready after 2026-07-28 MinIO decision.
- **Stop conditions:** Stop if promoting filesystem adapter to production, inventing a second storage API, or requiring cloud S3 for DONE.
- **Tail ownership:** P12-04 backup consistency; P12-06 digests; P12-08 production acceptance.

---

## Product Contract

### Summary

Local-production and test environments use MinIO behind one S3-compatible adapter implementing the existing governed object-store port. Development may keep filesystem. API/workers share MinIO for concurrent multi-user access.

Product Contract preservation: authored from P10-04 + architecture MinIO decision.

### Problem Frame

Only the filesystem adapter exists; architecture forbids filesystem as production store. Without MinIO, concurrent multi-replica workers cannot safely share source bytes and P12-04 cannot prove production-like object version/key consistency.

### Actors

| Actor | Role |
| --- | --- |
| Operator | Runs Compose with MinIO |
| API/Worker | Put/get/range/delete via port |
| Coding agent | Adapter, Compose, readiness, tests, evidence |

### Key Flows

**F1 — Compose MinIO.** Stack starts private MinIO + bucket bootstrap → API/worker configured with S3 endpoint/credentials → ready probe succeeds.

**F2 — Object lifecycle.** Upload put → DB metadata → get/range → delete; path traversal rejected; keys opaque.

**F3 — Reconciliation hook.** Enumerate referenced keys vs store for backup/restore drills (P12-04 consumes).

### Requirements

- R1. Inventory `docs/_scratch/p10-04-minio-object-store-inventory.md`.
- R2. One S3-compatible adapter implementing existing port (put/get/range/delete, integrity metadata).
- R3. Compose `minio` service (private network; published only to loopback if needed for ops); filesystem remains default for pure-dev profile.
- R4. `/health/ready` and worker readiness include object-store capability when S3 adapter selected.
- R5. Contract/unit tests for success, range, delete, traversal rejection, missing object — against MinIO in Compose or testcontainers-equivalent; CI may keep filesystem unless opt-in MinIO job is added.
- R6. Document env vars and backup hooks (version/key listing) for P12-04.
- R7. Evidence + tracker; advance DRIFT-15; mark P10-04 DONE.

### Acceptance Examples

- AE1. Compose MinIO profile ready; upload→range→delete succeeds.
- AE2. Filesystem still works in development profile.
- AE3. Missing object fails closed for content routes.
- AE4. No bucket management UI or multi-cloud abstraction added.

### Scope Boundaries

#### In scope

- S3 adapter; MinIO Compose; readiness; tests; backup hooks; docs/evidence

#### Deferred to Follow-Up Work

- Cloud AWS-only hardening beyond S3 API
- Upload orphan compensation task

#### Outside this product's identity

- Multi-cloud SDK sprawl; Redis; public object URLs

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | One adapter, MinIO as local-production target | User decision; YAGNI |
| KTD2 | Reuse ObjectStore port | DRY |
| KTD3 | Dev filesystem retained | Fast loop; not production evidence |

### Assumptions

- boto3 or equivalent already acceptable via pyproject optional extra if needed.
- Single-bucket design is enough for Phase 1.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| CI flakiness with MinIO | Opt-in Compose/MinIO tests; filesystem default CI |
| Credential leakage | Env-only; never in DTOs/logs |

---

## Implementation Units

### U1. Object-store inventory

**Goal:** Freeze port/Compose/settings seams.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `docs/_scratch/p10-04-minio-object-store-inventory.md`

**Approach:** Disposition retain filesystem; add S3 adapter; Compose service; readiness.

**Patterns to follow:** p4-01 storage inventory

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Inventory complete.

---

### U2. S3-compatible adapter and settings

**Goal:** Implement adapter behind existing port.

**Requirements:** R2,R6

**Dependencies:** U1

**Files:**
- Modify: `app/context_engine/adapters/object_storage.py` (or sibling)
- Modify: settings/composition
- Create: `app/tests/test_s3_object_store.py`

**Approach:** Minimal S3 client wrapper; opaque keys; range GET; idempotent delete; no public URLs.

**Patterns to follow:** FilesystemObjectStore contract tests

**Test scenarios:**
- Happy: put/get/range/delete.
- Error: traversal/missing object.
- Edge: integrity metadata retained.

**Verification:** Unit/contract tests green (mocked or MinIO).

---

### U3. Compose MinIO and readiness

**Goal:** Runnable local-production store profile.

**Requirements:** R3,R4,AE1,AE2

**Dependencies:** U2

**Files:**
- Modify: `app/compose.stack.yml` (+ overlay if needed)
- Modify: health/readiness composition
- Modify: `docs/operations/compose-stack-runbook.md`
- Create/modify: compose config tests

**Approach:** Add minio service + bootstrap; wire CE_* store settings; ready fails closed when selected store unavailable.

**Patterns to follow:** P10-01/P10-02 compose evidence

**Test scenarios:**
- Happy: ready with MinIO up.
- Error: MinIO down → ready 503 when S3 selected.
- Edge: filesystem profile unchanged.

**Verification:** Compose config + readiness tests.

---

### U4. Contract tests, backup hooks, and evidence

**Goal:** Contract/recon coverage + P12-04 backup hooks; close P10-04 and advance DRIFT-15.

**Requirements:** R5, R6, R7, AE3, AE4

**Dependencies:** U2, U3

**Files:**
- Create/extend: `app/tests/test_s3_object_store.py` (and recon helper tests)
- Create: `app/scripts/stack_object_store_recon.py` (name flexible) for key/version/hash listing
- Create: `docs/_scratch/p10-04-minio-object-store-evidence.md`
- Modify: `docs/master-build-plan.md`, `docs/brownfield-refactor-register.md` DRIFT-15

**Approach:** Prove put/get/range/delete/missing/traversal; expose recon/list hooks for P12-04; record commands; filesystem remains development-only residual; digests/KMS → P12-08.

**Patterns to follow:** `docs/_scratch/p10-02-stack-smoke-evidence.md`; P4-01 storage tests

**Test scenarios:**
- Happy: matching keys/hashes pass recon helper.
- Error: missing object / mismatch hard-fail inputs for P12-04.
- Edge: evidence does not claim multi-cloud/UI/HA.

**Verification:** Tracker DONE; DRIFT-15 advanced; P12-04 can attach to hooks.

---

## Verification Contract

- Adapter contract tests; Compose config; readiness.
- Opt-in live MinIO smoke acceptable as evidence altitude.
- Privacy: no credentials in logs/DTOs.

## Definition of Done

R1–R7 and AE1–AE4 satisfied; filesystem not production; P10-04 DONE.

## Sources & Research

- docs/architecture/deployment-topology.md
- docs/tech-stack.md
- docs/master-build-plan.md P10-04
- docs/_scratch/legacy-gap-plan-bundle.md
