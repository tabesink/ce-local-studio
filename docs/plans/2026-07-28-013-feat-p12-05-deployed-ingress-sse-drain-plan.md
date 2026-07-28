---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P12-05 Deployed Ingress SSE and Stream Drain - Plan
type: feat
date: 2026-07-28
---

# P12-05 Deployed Ingress SSE and Stream Drain - Plan

## Goal Capsule

- **Objective:** Close P12-05 by proving deployed-ingress incremental domain-RAG SSE (≥2 deltas before terminal), reconnect/replay, graceful shutdown/stream-drain, TLS/Host/Origin/CSRF through the public edge, and direct FastAPI denial — through the real private LightRAG runtime.
- **Authority:** docs/architecture/deployment-topology.md; frontend-security-boundary.md; DRIFT-05/24/25; M-03/M-10/C-01/C-05; docs/master-build-plan.md P12-05 (depends P5-04,P7-06,P9,P12-02).
- **Execution profile:** Staging/Compose TLS ingress altitude; blocked on P5-04 and P7-06.
- **Readiness checkpoint:** Implementation-ready; implementation starts only when P5-04 and P7-06 are DONE.
- **Stop conditions:** Stop if DONE claims Playwright browser matrix (P12-07), backup drills (P12-04), or SBOM (P12-06); stop if buffering hides incremental deltas.
- **Tail ownership:** P12-07 browser; P12-08 acceptance.

---

## Product Contract

### Summary

Prove the production trust and streaming boundary through ingress→Next BFF→FastAPI with real domain-RAG runtime, including drain semantics.

Product Contract preservation: authored from P12-05 bootstrap.

### Problem Frame

Local BFF and SSE producer proofs exist, but deployed ingress unbuffered SSE, TLS edge authz, direct-API denial, and stream-drain remain open. Without them, concurrent multi-user production streaming is not release-proven.

### Actors

| Actor | Role |
| --- | --- |
| Member | Streams domain_rag through public origin |
| Operator | Runs ingress topology and drain drills |
| Coding agent | Topology, proofs, evidence |

### Key Flows

**F1 — Incremental SSE.** Through ingress, ≥2 answer deltas arrive before terminal.

**F2 — Reconnect/replay.** Disconnect ≠ cancel; resume/replay after cursor.

**F3 — Drain.** SIGTERM: stop new work, drain streams/claims within bound; unresolved work reclaimable.

**F4 — Trust.** TLS; Host/Origin/CSRF; forged headers stripped; direct public FastAPI denied.

### Requirements

- R1. Inventory `docs/_scratch/p12-05-deployed-ingress-inventory.md`.
- R2. Hard wait on P5-04 + P7-06 before implementation proofs that require real runtime/heartbeat.
- R3. Ingress topology (Compose/staging) with TLS and private API.
- R4. Prove ≥2 incremental SSE deltas before terminal through ingress.
- R5. Reconnect/replay + graceful stream-drain/shutdown proofs.
- R6. Direct FastAPI public denial; Host/Origin/CSRF through edge.
- R7. Evidence + tracker; advance DRIFT-05/24/25 deployed halves.

### Acceptance Examples

- AE1. Incremental deltas observed through ingress.
- AE2. Resume after disconnect continues without duplicate completion assumption.
- AE3. Drain completes within configured grace; leases reclaimable.
- AE4. Direct API from untrusted peer denied.

### Scope Boundaries

#### In scope

- Ingress topology; SSE/drain/trust proofs; evidence

#### Deferred to Follow-Up Work

- Browser E2E (P12-07)
- Full HA multi-region

#### Outside this product's identity

- WebSockets; second stream protocol

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | Hard wait P5-04/P7-06 | Real runtime + heartbeat |
| KTD2 | Measure unbuffered deltas | Deployment-topology gate |
| KTD3 | Compose/staging ingress acceptable evidence altitude | Local-production model |

### Assumptions

- P9-05 BFF stripping remains credit.
- P12-02 verify stays green baseline.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Proxy buffering false green | Explicit delta timing assertions |
| Scope into Playwright | Residual to P12-07 |

---

## Implementation Units

### U1. Ingress inventory

**Goal:** Freeze topology and credit/gap.

**Requirements:** R1,R2

**Dependencies:** None (draft OK before P5-04; no DONE claims)

**Files:**
- Create: `docs/_scratch/p12-05-deployed-ingress-inventory.md`

**Approach:** Credit P1-05/P9-05/P7-04; gap deployed edge.

**Patterns to follow:** p12-03 inventory

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Residuals named.

---

### U2. Ingress topology wiring

**Goal:** TLS edge + private API Compose/staging profile.

**Requirements:** R3,R6,AE4

**Dependencies:** U1; P5-04 for runtime-backed path

**Files:**
- Modify: compose/ingress config / ops docs
- Create: ingress trust smoke scripts/tests

**Approach:** Public origin only Next; API private; CSRF/Origin through edge.

**Patterns to follow:** frontend-security-boundary.md

**Test scenarios:**
- Happy: login/mutation through ingress.
- Error: direct API denied.
- Error: hostile Origin rejected.

**Verification:** Smoke scripts green.

---

### U3. SSE unbuffered incremental and reconnect proof

**Goal:** ≥2 answer deltas + reconnect/replay through ingress with real LightRAG domain-RAG.

**Requirements:** R4, AE1, AE2

**Dependencies:** U2; **P5-04 DONE** (hard)

**Files:**
- Create: `app/scripts/stack_ingress_sse_proof.py` (name flexible)
- Create: helper/unit tests as needed

**Approach:** Assert ≥2 incremental deltas before terminal through public origin; reconnect/resume/replay; single buffered blob fails the proof. Use real private LightRAG runtime.

**Patterns to follow:** `docs/architecture/deployment-topology.md` SSE rules; `docs/contracts/sse-event-catalog.md`

**Test scenarios:**
- Happy: ≥2 deltas before terminal through ingress.
- Edge: reconnect resumes; disconnect ≠ cancel.
- Error: buffered one-blob path fails the proof script.

**Verification:** AE1/AE2 commands reproducible; P5-04 revision cited.

---

### U4. Graceful drain and shutdown proof

**Goal:** Topology shutdown sequence with stream-drain and lease recoverability.

**Requirements:** R5, AE3

**Dependencies:** U3; **P7-06 DONE** (hard for mid-turn depth); credit P10-03 stop-claim

**Files:**
- Create: `app/scripts/stack_ingress_drain_proof.py` (name flexible)
- Modify: runbook shutdown section

**Approach:** SIGTERM ingress/API/worker per topology order; stop new work; drain within grace; unresolved work reclaimable; closed socket ≠ completion.

**Patterns to follow:** deployment-topology shutdown table; P10-03 drain; P7-06 heartbeat

**Test scenarios:**
- Happy: drain completes or leaves reclaimable leased work only.
- Edge: disconnect during drain ≠ cancel.
- Integration: cites P10-03 + P7-06 evidence revisions.

**Verification:** AE3 in evidence.

---

### U5. Evidence and tracker

**Goal:** Close P12-05; advance DRIFT-05/24/25 deployed halves.

**Requirements:** R7, AE4

**Dependencies:** U1–U4

**Files:**
- Create: `docs/_scratch/p12-05-deployed-ingress-evidence.md`
- Modify: `docs/master-build-plan.md`; `docs/brownfield-refactor-register.md` DRIFT-05/24/25

**Approach:** Honest residuals for browser matrix (P12-07) and HA.

**Patterns to follow:** `docs/_scratch/p12-03-adversarial-security-evidence.md`

**Test scenarios:**
- Test expectation: none -- docs.

**Verification:** Tracker DONE.

---

## Verification Contract

- Ingress smokes; SSE delta assertions; drain timing.
- Requires P5-04/P7-06 evidence revisions cited.

## Definition of Done

R1–R7 and AE1–AE4 after prerequisites; DRIFT deployed halves advanced; P12-05 DONE.

## Sources & Research

- docs/architecture/deployment-topology.md
- docs/architecture/frontend-security-boundary.md
- docs/master-build-plan.md P12-05
