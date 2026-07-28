---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P4-05 Figure and Table Region Provenance - Plan
type: feat
date: 2026-07-28
---

# P4-05 Figure and Table Region Provenance - Plan

## Goal Capsule

- **Objective:** Close P4-05 by carrying durable normalized figure/table regions from parser publish through authorized location resolution and governed viewer focus/fallback for M-04/M-05.
- **Authority:** docs/contracts/document-and-evidence-contract.md; M-04/M-05; docs/quality/seeded-demo-and-test-data.md; docs/frontend/document-viewer-spec.md; P6-02/P9-03 evidence.
- **Execution profile:** Inventory-first brownfield; YAGNI/KISS/DRY; credit existing proofs; dual-lane CI where noted.
- **Readiness checkpoint:** Implementation-ready for coding-agent execution after 2026-07-28 legacy-gap bundle packaging.
- **Stop conditions:** Stop if DONE invents browser-supplied region authority, private block IDs in URLs, or changes P6-02 retrieval EvidenceItemDto to require region without contract amendment.
- **Tail ownership:** P9-07/P12-07 browser deep-link matrix; non-PDF viewers remain future.

---

## Product Contract

### Summary

Persist optional normalized regions on canonical figure/table blocks/images when parsers prove them; authorize location endpoints to return region anchors; PDF viewer focuses region with section/page fallback. Retrieval Evidence list remains page/section-only per P6-02 unless a coordinated contract change is approved.

Product Contract preservation: Product Contract authored here from master-build-plan bootstrap; no upstream brainstorm IDs to preserve.

### Problem Frame

M-04 requires figure-region focus, and seed fixtures define regions, but as-built Evidence/location paths often emit region:null and the viewer only navigates pages. Legacy bbox provenance was dropped during rebuild.

### Actors

| Actor | Role |
| --- | --- |
| Member | Opens figure/table Evidence deep links |
| Administrator | Uploads/prepares sources |
| Coding agent | Persist regions, project location, viewer focus |

### Key Flows

**F1 — Publish region.** Parser yields normalized bbox → stored on block/image metadata under lease fence.

**F2 — Location resolve.** Authorized GET location for evidence/document returns page + optional region + fallback.

**F3 — Viewer focus.** Documents route opens PDF, focuses region with margin highlight, or falls back to section/page.

### Requirements

- R1. Inventory docs/_scratch/p4-05-region-provenance-inventory.md credit/gap for parser, schema, location, viewer.
- R2. Persist optional normalized region {x,y,width,height} in 0..1 when parser proves it; never fabricate.
- R3. Authorized location/deep-link DTOs may include region when proven; server ignores browser-supplied region for authority.
- R4. Viewer: valid region → page + fit/highlight; else section/page fallback; unauthorized → Evidence no longer available.
- R5. Keep P6-02 retrieval EvidenceItemDto page/section-only unless an approved coordinated contract change lands in this slice.
- R6. Seed/fixture alignment with docs/quality/seeded-demo-and-test-data.md figure region constants.
- R7. Evidence docs/_scratch/p4-05-region-provenance-evidence.md; tracker DONE.

### Acceptance Examples

- AE1. Pump-manual figure fixture publishes region matching seed constants.
- AE2. Location resolve returns region for figure Evidence; text without region stays null.
- AE3. Viewer focuses region; missing region falls back without crash.
- AE4. Cross-owner location remains non-disclosing 404.

### Scope Boundaries

#### In scope

- Region persistence
- Location projection
- PDF viewer focus/fallback
- Fixture alignment
- Tests/evidence

#### Deferred to Follow-Up Work

- Non-PDF/PPT viewers
- Upload orphan compensation

#### Outside this product's identity

- Heuristic bbox guessing
- Private object keys in browser
- Graph UI

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | Regions are optional proven metadata | Never fabricate page 1/region |
| KTD2 | Location path owns region for deep links; retrieval list stays P6-02 | Preserve closed DTO |
| KTD3 | Normalized 0..1 page-relative rectangles only | Contract match |

### Assumptions

- P9-03 PDF preview infrastructure remains credit.
- Docling/Reducto may omit regions → null is success.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Contract drift if EvidenceItemDto silently gains region | Explicit KTD2 / stop condition |

---

## Implementation Units

### U1. Region provenance inventory

**Goal:** Freeze seams.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: docs/_scratch/p4-05-region-provenance-inventory.md

**Approach:** Credit P4-03/P6-02/P9-03; mark schema/location/viewer gaps.

**Patterns to follow:** p6-02 inventory

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Dispositions complete.

---

### U2. Persist parser regions on publish

**Goal:** Store proven regions under prep fence.

**Requirements:** R2,R6,AE1

**Dependencies:** U1

**Files:**
- Modify: parser normalizer / source block models / migrations if needed
- Modify: app/tests parser/prep suites

**Approach:** Extend canonical block/image metadata for optional region; publish atomically; refuse invalid ranges.

**Patterns to follow:** P4-03 publish fence

**Test scenarios:**
- Happy: figure region persisted.
- Edge: missing region → null.
- Error: out-of-range coords rejected.

**Verification:** Prep/unit tests green.

---

### U3. Authorized location projection

**Goal:** Serve region on location deep links.

**Requirements:** R3,R5,AE2,AE4

**Dependencies:** U2

**Files:**
- Modify: documents/evidence location services and DTOs
- Modify: contract tests

**Approach:** Project region only when stored+authorized; regenerate contracts if DTO fields already approved.

**Patterns to follow:** document-and-evidence-contract location

**Test scenarios:**
- Happy: figure location includes region.
- Error: wrong owner 404.
- Edge: retrieval Evidence list unchanged unless contract amended.

**Verification:** HTTP contract tests green.

---

### U4. Viewer focus and fallback

**Goal:** M-04/M-05 UI behavior.

**Requirements:** R4,AE3

**Dependencies:** U3

**Files:**
- Modify: app/client documents viewer feature
- Modify: frontend unit/Vitest tests

**Approach:** Prefer server location region; fallback section/page; return focus to card.

**Patterns to follow:** document-viewer-spec; P9-03

**Test scenarios:**
- Happy: region highlight.
- Edge: page-only fallback.
- Error: unavailable evidence safe message.

**Verification:** Frontend tests green.

---

### U5. Evidence and tracker

**Goal:** Close P4-05.

**Requirements:** R7

**Dependencies:** U4

**Files:**
- Create: docs/_scratch/p4-05-region-provenance-evidence.md
- Modify: docs/master-build-plan.md

**Approach:** Record commands and residuals.

**Patterns to follow:** p9-03 evidence

**Test scenarios:**
- Test expectation: none -- docs.

**Verification:** Tracker DONE.


---

## Verification Contract

- Unit/HTTP/frontend tests for region publish, location, viewer fallback.
- Contract snapshots if DTOs change.
- Case IDs M-04/M-05.

## Definition of Done

R1–R7 and AE1–AE4 satisfied; no fabricated regions; P4-05 DONE.

## Sources & Research

- docs/contracts/document-and-evidence-contract.md
- docs/interaction-behavior-prd.md M-04/M-05
- docs/quality/seeded-demo-and-test-data.md
