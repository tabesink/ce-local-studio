---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P12-07 Browser E2E Accessibility and Capacity - Plan
type: feat
date: 2026-07-28
---

# P12-07 Browser E2E Accessibility and Capacity - Plan

## Goal Capsule

- **Objective:** Close P12-07 by running production Next build + BFF + FastAPI Playwright proofs for accessibility, visual matrix, CSRF product path, two-user cache/BFCache isolation, M-11 open-panel, real LightRAG capacity/isolation, provider/runtime failure, and deterministic fixture materialization — without inventing a RAG-triad observability product.
- **Authority:** docs/frontend/browser-e2e-scenarios.md; visual-regression-plan.md; seeded-demo-and-test-data.md; DRIFT-07/09/19/29; docs/master-build-plan.md P12-07 (depends P5-04,P9-07,P10-04,P10-05,P12-02,P12-03).
- **Execution profile:** Production-build E2E; blocked on P5-04/P9-07/P10-04/P10-05; fixtures first.
- **Readiness checkpoint:** Implementation-ready; implementation of live runtime E2E waits on prerequisites.
- **Stop conditions:** Stop if mocking product DTOs for acceptance, inventing Phase 2 quality dashboards, or claiming B0 without Playwright job.
- **Tail ownership:** P12-08 aggregates; B0 completes when this lands.

---

## Product Contract

### Summary

Materialize deterministic fixtures and prove contracted browser/multi-user/capacity behavior through the real stack and real LightRAG runtime.

Product Contract preservation: authored from P12-07 bootstrap.

### Problem Frame

P9 closed component/Vitest altitude; B0 and DRIFT browser halves remain open. Seeded fixture world is specified but not fully materialized. Capacity/isolation through real LightRAG is unproven.

### Actors

| Actor | Role |
| --- | --- |
| Mina/Noah/Ava fixtures | Multi-user actors |
| Coding agent | Fixtures, Playwright, capacity scripts, evidence |

### Key Flows

**F1 — Fixtures.** Build/verify deterministic documents/manifest/expected answers.

**F2 — Playwright matrix.** Login/chat/documents/settings/graph-unavailable; CSRF; two-user cache; M-11 panel; a11y; visual baselines.

**F3 — Capacity/failure.** Concurrent queries; provider/runtime failure paths; load shedding.

### Requirements

- R1. Inventory `docs/_scratch/p12-07-browser-e2e-capacity-inventory.md`.
- R2. Materialize `docs/quality/seeded-demo-and-test-data.md` artifacts (manifest, documents, expected outputs, seed command).
- R3. Playwright through production Next + BFF + FastAPI; no mocked product responses for acceptance.
- R4. CSRF product path; two-user cache/BFCache; M-11 open-panel/cache half.
- R5. Accessibility + visual matrix baselines at approved thresholds.
- R6. Real LightRAG capacity/isolation + provider/runtime failure evidence (needs P5-04/P10-05).
- R7. Expected-answer browser acceptance for seeded figure question only — not a RAG-triad product metric API.
- R8. Evidence + tracker; close DRIFT-07/09/19/29 browser halves / B0 as applicable.

### Acceptance Examples

- AE1. Fixtures verify hashes/idempotent seed.
- AE2. Playwright login→chat→evidence→documents region path green for Mina.
- AE3. Noah cannot read Mina conversation/cache contents.
- AE4. Visual matrix + a11y checks pass.
- AE5. Capacity test shows isolation and safe 429/503 before collapse.

### Scope Boundaries

#### In scope

- Fixtures; Playwright; a11y/visual; CSRF; cache isolation; capacity/failure; evidence

#### Deferred to Follow-Up Work

- Metric RAG triad evaluation product
- FE-01 mega-kit demolition

#### Outside this product's identity

- Phase 2 observability screens

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | Fixtures before E2E | Seeded-demo contract |
| KTD2 | Production build only for acceptance | DoD |
| KTD3 | Expected answers ≠ observability product | Scope control |

### Assumptions

- P9-06 gallery targets provide visual targetIds.
- P9-07 workflows available for rename/refs/history coverage.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Flaky E2E | Deterministic fixtures/clock; quarantine policy |
| Runtime unavailable | Hard wait P5-04 |

---

## Implementation Units

### U1. E2E/capacity inventory

**Goal:** Map scenarios to case IDs and prereqs.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `docs/_scratch/p12-07-browser-e2e-capacity-inventory.md`

**Approach:** Credit P9/P12-03; list Playwright scenarios and capacity cases.

**Patterns to follow:** browser-e2e-scenarios.md

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Scenario matrix complete.

---

### U2. Deterministic fixture materialization

**Goal:** Commit buildable fixture world.

**Requirements:** R2,R7,AE1

**Dependencies:** U1

**Files:**
- Create: `app/tests/fixtures/manifest.json` and documents/expected as specified
- Create/modify: seed + fixtures:build/verify scripts
- Create: fixture verification tests

**Approach:** Synthetic only; gated seed; hash verify; figure expected answer constant.

**Patterns to follow:** seeded-demo-and-test-data.md

**Test scenarios:**
- Happy: fixtures:verify passes.
- Error: blank hash fails.
- Edge: seed idempotent.

**Verification:** Fixture gate green.

---

### U3. Playwright matrix and isolation

**Goal:** Browser acceptance proofs.

**Requirements:** R3,R4,R5,AE2,AE3,AE4

**Dependencies:** U2; P9-07; P10-04

**Files:**
- Create/modify: `app/client/tests/e2e/**`
- Create: visual baselines governance
- Modify: CI workflow Playwright job

**Approach:** Production build; real BFF/API; CSRF login; two-user jars; M-11; a11y; visual matrix.

**Patterns to follow:** visual-regression-plan.md; P9-05 cache rules

**Test scenarios:**
- Covers M-01/M-04/M-08/M-09/M-11/C-03/C-04 as applicable.
- Error: cross-user cache miss/denial.
- Edge: graph-unavailable no request.

**Verification:** Playwright job green.

---

### U4. Capacity and runtime failure

**Goal:** Real runtime concurrency/failure evidence.

**Requirements:** R6,AE5

**Dependencies:** U3; P5-04; P10-05

**Files:**
- Create: capacity/failure scripts or e2e stress harness
- Create: evidence commands

**Approach:** Concurrent members on one domain; isolation assertions; provider/runtime failure → safe codes.

**Patterns to follow:** C-01; deployment capacity section

**Test scenarios:**
- Happy: N members isolated.
- Error: runtime down → safe failure with request ID.
- Edge: 429/503 before unbounded growth.

**Verification:** Evidence recorded.

---

### U5. Evidence and tracker / B0

**Goal:** Close P12-07 and advance B0.

**Requirements:** R8

**Dependencies:** U4

**Files:**
- Create: `docs/_scratch/p12-07-browser-e2e-capacity-evidence.md`
- Modify: master-build-plan + DRIFT-07/09/19/29

**Approach:** Honest residuals only; mark browser halves DONE where proven.

**Patterns to follow:** p12-02 evidence

**Test scenarios:**
- Test expectation: none -- docs.

**Verification:** Tracker DONE; B0 status updated honestly.

---

## Verification Contract

- Fixture verify; Playwright CI; capacity evidence; privacy cache checks.
- Cite P5-04/P9-07/P10-04/P10-05 revisions.

## Definition of Done

R1–R8 and AE1–AE5 satisfied; no mocked acceptance; P12-07 DONE.

## Sources & Research

- docs/frontend/browser-e2e-scenarios.md
- docs/quality/seeded-demo-and-test-data.md
- docs/master-build-plan.md P12-07
