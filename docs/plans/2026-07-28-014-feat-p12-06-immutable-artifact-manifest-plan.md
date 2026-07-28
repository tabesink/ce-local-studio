---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P12-06 Immutable Artifact Manifest and SBOM - Plan
type: feat
date: 2026-07-28
---

# P12-06 Immutable Artifact Manifest and SBOM - Plan

## Goal Capsule

- **Objective:** Close P12-06 by producing an immutable release artifact manifest covering web/API/worker/LightRAG runtime image digests, MinIO/provider/runtime locks, schema and contract versions, SBOM, and provenance.
- **Authority:** docs/quality/definition-of-done.md production release gate; docs/architecture/deployment-topology.md release sequence; docs/master-build-plan.md P12-06 (depends P0,P5-04,P10-04,P10-05,P12-02).
- **Execution profile:** Manifest generation + verify hooks; blocked on P5-04/P10-04/P10-05 for pin completeness.
- **Readiness checkpoint:** Implementation-ready; pin completeness waits on prerequisites.
- **Stop conditions:** Stop if inventing product observability UI, or claiming production digests without built artifacts.
- **Tail ownership:** P12-08 go/no-go attaches to this manifest.

---

## Product Contract

### Summary

Generate and verify a commit/release manifest that freezes every artifact a restore/rollback needs.

Product Contract preservation: authored from P12-06 bootstrap.

### Problem Frame

Without pinned digests/SBOM/provenance, rollback and incident response cannot prove what ran. P12-02 freezes contracts but not release images/runtime pins.

### Actors

| Actor | Role |
| --- | --- |
| Operator / releaser | Builds and records manifests |
| Coding agent | Generator, CI hooks, evidence |

### Key Flows

**F1 — Build pins.** Build images → record digests + lockfile hashes + Alembic head + OpenAPI/SSE versions + vendored LightRAG pin + MinIO image pin.

**F2 — SBOM/provenance.** Generate SBOM and provenance attestation for release artifacts.

**F3 — Gate.** Verify script fails on missing/mismatched pins.

### Requirements

- R1. Inventory `docs/_scratch/p12-06-immutable-artifact-inventory.md`.
- R2. Manifest schema listing digests, locks, schema head, contract versions, LightRAG/MinIO pins, provider profile ids.
- R3. SBOM + provenance generation for release images.
- R4. CI/verify hook checks manifest presence/integrity for release profile (not mandatory for every PR if too heavy — document boundary).
- R5. Evidence + tracker DONE; residuals for external signing keys named.

### Acceptance Examples

- AE1. Manifest records all required pin fields.
- AE2. Mutating a digest breaks verify/manifest check.
- AE3. SBOM artifact produced for API/web images.
- AE4. Evidence cites P5-04/P10-04/P10-05 revisions for runtime/store/provider pins.

### Scope Boundaries

#### In scope

- Manifest generator; SBOM/provenance; hooks; evidence

#### Deferred to Follow-Up Work

- External cosign/key ceremony details beyond local-production

#### Outside this product's identity

- Product SBOM browser UI

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | One manifest JSON/YAML committed or CI-uploaded | Simple |
| KTD2 | PR verify may use lighter pin check; release profile full | YAGNI |
| KTD3 | Hard cite runtime/store/provider prereqs | Honest pins |

### Assumptions

- Syft/trivy or equivalent available in CI or documented install.
- Local-production images are the Phase 1 release unit.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Tooling unavailable | Document fallback + fail closed for release profile |
| Stale pins | Generator reads docker inspect + lock digests |

---

## Implementation Units

### U1. Manifest inventory

**Goal:** Freeze required pin fields.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `docs/_scratch/p12-06-immutable-artifact-inventory.md`

**Approach:** List every DoD production-gate pin; map to generator source.

**Patterns to follow:** p12-02 inventory style

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Field list complete.

---

### U2. Manifest generator

**Goal:** Emit immutable manifest.

**Requirements:** R2,AE1,AE4

**Dependencies:** U1; P5-04/P10-04/P10-05 for full pins

**Files:**
- Create: `scripts/generate_release_manifest.py` (name flexible)
- Create: manifest schema/example under `docs/` or `app/contracts/`

**Approach:** Collect digests/locks/versions; refuse incomplete release profile.

**Patterns to follow:** generate_openapi.py discipline

**Test scenarios:**
- Happy: complete inputs → manifest.
- Error: missing LightRAG pin in release mode → fail.

**Verification:** Generator tests green.

---

### U3. SBOM and provenance

**Goal:** Attach SBOM and provenance materials to the manifest.

**Requirements:** R3, AE2

**Dependencies:** U2

**Files:**
- Create: SBOM generation script/CI or release step
- Create: provenance sidecar or manifest section
- Document chosen SBOM tool + version in inventory/evidence

**Approach:** Generate SBOM for primary release images; record provenance tying manifest to source revision + build inputs; no product SBOM UI.

**Patterns to follow:** deployment-topology release sequence step 1

**Test scenarios:**
- Happy: SBOM non-empty; manifest links resolve.
- Error: SBOM generation failure fails release job (not silently skipped).

**Verification:** AE2 in evidence.

---

### U4. Verify gate hooks

**Goal:** Fail CI/release on unexpected pin/digest drift.

**Requirements:** R4, AE3

**Dependencies:** U2

**Files:**
- Create: `scripts/check-release-manifest.sh` (name flexible)
- Modify: `.github/workflows/verify.yml` or release workflow (document PR vs release split)
- Create: adversarial mismatch fixture tests

**Approach:** Compare regeneratable pins; optional full digest check on release job; do not absorb Playwright or live Compose smoke.

**Patterns to follow:** `scripts/check-generated-contracts.sh`; `scripts/verify.sh`

**Test scenarios:**
- Happy: matching manifest/pins pass.
- Error: mutated digest or lockfile pin fails.

**Verification:** Hook tests green.

---

### U5. Evidence and tracker

**Goal:** Close P12-06 for P12-08 consumption.

**Requirements:** R5, AE4

**Dependencies:** U1–U4

**Files:**
- Create: `docs/_scratch/p12-06-immutable-artifact-evidence.md`
- Modify: `docs/master-build-plan.md`

**Approach:** Record commands and residual signing/registry promotion to P12-08; cite P5-04/P10-04/P10-05 pin revisions.

**Patterns to follow:** `docs/_scratch/p12-02-suite-contract-convergence-evidence.md`

**Test scenarios:**
- Test expectation: none -- docs.

**Verification:** Tracker DONE.

---

## Verification Contract

- Generator + mismatch tests.
- Release-profile completeness including P5-04/P10-04/P10-05 pins.

## Definition of Done

R1–R5 and AE1–AE4 satisfied; P12-06 DONE with honest residuals.

## Sources & Research

- docs/quality/definition-of-done.md
- docs/architecture/deployment-topology.md
- docs/master-build-plan.md P12-06
