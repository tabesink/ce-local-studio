---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P7-06 Synthesis Context Isolation and Turn Lease Heartbeat - Plan
type: feat
date: 2026-07-28
---

# P7-06 Synthesis Context Isolation and Turn Lease Heartbeat - Plan

## Goal Capsule

- **Objective:** Close P7-06 by isolating untrusted Evidence/context inside private synthesis prompts with delimiter collision defenses, and by heartbeating active turn leases during retrieve/synthesize so a second worker cannot reclaim a live turn.
- **Authority:** Root AGENTS.md privacy invariants; docs/prd.md FR-06/FR-09; P7-03/P7-04; P10-03 mid-turn heartbeat residual; docs/master-build-plan.md P7-06; legacy prompt-assembly isolation as read-only evidence only.
- **Execution profile:** Inventory-first; no-network synthesis fixtures; PostgreSQL lease reclaim denial; do not persist prompts.
- **Readiness checkpoint:** Implementation-ready after 2026-07-28 bundle packaging.
- **Stop conditions:** Stop if DONE pressure persists raw prompts/assembled context, adds browser-visible fields, or pulls P12-05 ingress drain into this slice.
- **Tail ownership:** P12-05 stream-drain; P12-07 capacity; broader RAG quality benchmarks deferred.

---

## Product Contract

### Summary

Harden private synthesis message assembly so Evidence/excerpts cannot break instruction boundaries, and heartbeat turn leases while outbound retrieve/synthesize work runs.

Product Contract preservation: authored from master-build-plan P7-06 bootstrap.

### Problem Frame

P7-03 interpolates Evidence into synthesis messages without delimiter isolation proven by collision tests. P10-03 names mid-turn lease heartbeat as a residual: long retrieve/synthesize can expire and be reclaimed, risking double provider work under concurrency.

### Actors

| Actor | Role |
| --- | --- |
| Member | Submits domain_rag / direct turns |
| Worker | Owns leased turn execution |
| Coding agent | Implements isolation, heartbeat, proofs |

### Key Flows

**F1 — Isolated synthesis.** Orchestrator builds private messages with random/unpredictable delimiters around untrusted Evidence; collision in content is escaped/re-delimited; provider call uses isolated messages; nothing persisted beyond contracted projections.

**F2 — Heartbeat under work.** Turn worker heartbeats lease at <1/3 lease duration during retrieve/synthesize; second worker cannot claim while lease current; expiry after true death remains reclaimable.

### Requirements

- R1. Inventory in `docs/_scratch/p7-06-synthesis-isolation-heartbeat-inventory.md`.
- R2. Private delimiter isolation around untrusted Evidence/context in `adapters/synthesis.py` (or private assembly helper); instruction-boundary + collision tests.
- R3. Never persist raw prompts/assembled context/provider payloads.
- R4. Heartbeat turn lease during retrieve/synthesize; prove second worker cannot reclaim an active turn on PostgreSQL 16.
- R5. Keep grounded-refusal / no Evidence path unchanged (no ungrounded fallback).
- R6. Evidence `docs/_scratch/p7-06-synthesis-isolation-heartbeat-evidence.md`; mark P7-06 DONE; P7 phase DONE if no other open P7 tasks.

### Acceptance Examples

- AE1. Evidence containing delimiter-like or instruction-like text cannot override system instructions in fixture tests.
- AE2. Collision forces re-delimiter or safe escape; synthesis still completes or fails closed without leaking private IDs.
- AE3. Active turn with live heartbeat is not reclaimed by a second worker.
- AE4. Dead worker without heartbeat remains reclaimable after lease expiry.

### Scope Boundaries

#### In scope

- Synthesis isolation + tests
- Turn lease heartbeat + PG reclaim denial
- Inventory/evidence/tracker

#### Deferred to Follow-Up Work

- Metric RAG-triad evaluation
- Upload orphan compensation

#### Outside this product's identity

- Redis locks; prompt logging UI; Phase 2 observability

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | Private random delimiters + collision rewrite | Legacy evidence; privacy-safe |
| KTD2 | Heartbeat from turn worker loop around outbound calls | Matches domain/index lease pattern |
| KTD3 | No public API/DTO changes expected | Fail closed if needed |

### Assumptions

- OpenAI adapter remains primary synthesis path; Bedrock/Ollama stay fail-closed until P10-05.
- Lease duration env knobs already exist from P7-04/P10-03.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Prompt persistence creep | Explicit R3 + privacy scan plants |
| Heartbeat storms | Cadence <1/3 lease; reuse existing helper |

---

## Implementation Units

### U1. Isolation and heartbeat inventory

**Goal:** Freeze seams and credit P7-03/P7-04.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `docs/_scratch/p7-06-synthesis-isolation-heartbeat-inventory.md`

**Approach:** Map synthesis assembly call sites and turn worker lease touch points; disposition credit/gap.

**Patterns to follow:** `docs/_scratch/p7-03-orchestration-inventory.md`

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Inventory complete.

---

### U2. Synthesis delimiter isolation

**Goal:** Instruction-boundary isolation for untrusted Evidence.

**Requirements:** R2,R3,R5,AE1,AE2

**Dependencies:** U1

**Files:**
- Modify: `app/context_engine/adapters/synthesis.py` and/or private assembly helper
- Create/modify: `app/tests/test_synthesis_prompt_isolation.py`

**Approach:** Wrap Evidence blocks with private delimiters; detect collision and regenerate/escape; keep no-network fixtures; assert no prompt persistence paths added.

**Patterns to follow:** P7-03 synthesis adapter; legacy read-only prompt_assembly isolation idea only

**Test scenarios:**
- Happy: normal Evidence synthesizes.
- Edge: Evidence includes delimiter string → collision handled.
- Error: instruction-like Evidence cannot change system role semantics in fixture assertions.
- Privacy: no assembled prompt written to DB/logs fields.

**Verification:** Focused unit tests green.

---

### U3. Mid-turn lease heartbeat

**Goal:** Prevent reclaim of active turns.

**Requirements:** R4,AE3,AE4

**Dependencies:** U1

**Files:**
- Modify: turn worker / chat turn execution loop
- Create/modify: `app/tests/test_postgres_turn_lease_heartbeat.py`

**Approach:** Heartbeat while retrieve/synthesize in flight; barrier test: worker A holds lease with heartbeats; worker B claim fails until stop+expiry.

**Patterns to follow:** P5-03 index heartbeat; P10-03 reclaim scripts

**Test scenarios:**
- Happy: heartbeat extends expiry.
- Integration: second worker cannot reclaim active turn.
- Error: after stop without heartbeat, reclaim succeeds.

**Verification:** PostgreSQL suite green.

---

### U4. Evidence and tracker closure

**Goal:** Honest DONE.

**Requirements:** R6

**Dependencies:** U2, U3

**Files:**
- Create: `docs/_scratch/p7-06-synthesis-isolation-heartbeat-evidence.md`
- Modify: `docs/master-build-plan.md`

**Approach:** Record commands; mark P7-06 DONE; P7 phase DONE when appropriate.

**Patterns to follow:** p7-04 evidence

**Test scenarios:**
- Test expectation: none -- docs.

**Verification:** Tracker links evidence.

---

## Verification Contract

- Isolation unit tests on default pytest path.
- PostgreSQL heartbeat/reclaim tests under opt-in env.
- Privacy non-claims for prompts.

## Definition of Done

R1–R6 and AE1–AE4 satisfied; no prompt persistence; P7-06 DONE.

## Sources & Research

- docs/master-build-plan.md P7-06
- docs/_scratch/p7-03-orchestration-evidence.md
- docs/_scratch/p10-03-worker-lifecycle-evidence.md
- docs/_scratch/legacy-gap-plan-bundle.md
