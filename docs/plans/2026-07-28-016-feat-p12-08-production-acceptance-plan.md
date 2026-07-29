---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P12-08 Production Acceptance and Release Decision - Plan
type: feat
date: 2026-07-28
---

# P12-08 Production Acceptance and Release Decision - Plan

## Goal Capsule

- **Objective:** Close P12-08 by aggregating one revision-matched, graph-aware P12-03..P12-07 evidence set into a production acceptance record with runbooks, recovery objectives, the full admin Reducto→graph/index→chat→Evidence→PDF demonstration, named residuals, and an explicit go/no-go release decision for local-production Phase 1.
- **Authority:** docs/quality/definition-of-done.md production release gate; docs/architecture/deployment-topology.md; docs/master-build-plan.md P12-08.
- **Execution profile:** Documentation/evidence aggregation only; the enabled graph is implemented and proven by P12-07, not invented here; blocked on graph-aware P12-03..07 artifacts.
- **Readiness checkpoint:** Implementation-ready as an acceptance slice; execution waits on dependencies.
- **Stop conditions:** Stop if inventing missing capabilities instead of failing no-go; stop if scaffolding Phase 2 observability.
- **Tail ownership:** Post-release operations; future Phase 2/3 briefs only.

---

## Product Contract

### Summary

Produce the release decision packet: checklist, graph-aware operator demonstration, runbook ownership, RPO/RTO statement for local-production, residual register, and signed go/no-go.

Product Contract preservation: authored from P12-08 bootstrap.

### Problem Frame

Even with vertical proofs, release needs one aggregated acceptance record. Without it, operators cannot decide go/no-go or own recovery.

### Actors

| Actor | Role |
| --- | --- |
| Release approver | Go/no-go |
| Operator | Owns runbooks/recovery |
| Coding agent | Aggregates evidence and templates |

### Key Flows

**F1 — Checklist.** Verify each production-gate item cites evidence path + artifact revision and that no pre-graph schema/image/security/backup artifact is represented as current.

**F2 — Residuals.** Only deployment decisions (KMS vendor specifics, Path 2, etc.) remain — no silent gaps.

**F3 — Decision.** Re-run the operator demonstration from admin login/provider configuration through graph/chat/Evidence/PDF, then record go or no-go with owners and date.

### Requirements

- R1. Inventory checklist `docs/_scratch/p12-08-production-acceptance-inventory.md` mapping DoD production gate → evidence owners.
- R2. Acceptance record template/evidence `docs/_scratch/p12-08-production-acceptance-evidence.md`.
- R3. Runbook ownership table covering backup/restore, ingress drain, incident reclaim, provider outage, LightRAG rebuild.
- R4. RPO/RTO objectives stated for local-production matrix (architecture targets retained; measured Compose/staging numbers recorded).
- R5. Named residuals only; missing P12-03..07 evidence forces no-go.
- R6. Update master-build-plan P12-08 and P12 phase status on go; keep NOT_STARTED/BLOCKED on no-go.
- R7. Require the P12-07 Phase 1 graph contract, meaningful provider-backed extraction, authorized safe projection, accessible UI, deletion/rebuild behavior, and complete operator demonstration as release gates.
- R8. Reject mixed-revision evidence: P12-02 suite/contracts, P12-03 security, P12-04 backup/restore, P12-05 ingress, P12-06 images/SBOM/provenance, and P12-07 browser/demo evidence must identify compatible source/schema/contract/image revisions.

### Acceptance Examples

- AE1. Every DoD production-gate checkbox maps to an evidence path.
- AE2. No-go if any of P12-04..07 missing.
- AE3. Go record lists digests from P12-06 and restore drill from P12-04.
- AE4. Residuals explicitly exclude inventing Wiki/observability.
- AE5. Release approver can run `bash scripts/dev.sh`, use its safe service summary/application URL, log in as the bootstrapped admin, configure Reducto/embedding/extraction/synthesis, create/start a domain, upload/prepare/index a PDF, inspect its graph, ask a grounded question, inspect figure/table/text Evidence, and open the governed PDF anchor.
- AE6. Any unavailable graph, constant extraction stub, direct browser/runtime request, raw graph property leak, missing graph deletion/rebuild proof, or stale pre-graph artifact produces an explicit no-go.

### Scope Boundaries

#### In scope

- Acceptance aggregation; runbook ownership; decision record

#### Deferred to Follow-Up Work

- Path 2 populated upgrade
- Phase 2 observability

#### Outside this product's identity

- Multi-tenant Workspace; Redis platform

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | Aggregation only — no new features; consume the enabled graph from P12-07 | P12-08 must not paper over missing implementation |
| KTD2 | Missing dependency evidence ⇒ no-go | Honesty |
| KTD3 | Local-production is the Phase 1 ship target | User decision |

### Assumptions

- P12-03 already DONE and citable.
- MinIO local-production is accepted topology.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Pressure to go with gaps | R5/R6 force no-go |
| Orphan runbooks | Ownership table required |

---

## Implementation Units

### U1. Acceptance inventory checklist

**Goal:** Map every production-gate item to evidence.

**Requirements:** R1,AE1

**Dependencies:** None (update as deps complete)

**Files:**
- Create: `docs/_scratch/p12-08-production-acceptance-inventory.md`

**Approach:** Row per DoD production-gate bullet with owner task and evidence path/status.

**Patterns to follow:** definition-of-done.md production gate

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** No unchecked silent items.

---

### U2. Acceptance record template

**Goal:** Machine/human-readable acceptance record structure citing digests and child evidence.

**Requirements:** R2, AE3

**Dependencies:** U1

**Files:**
- Create: `docs/_scratch/p12-08-production-acceptance-evidence.md` (template sections; fill when deps DONE)
- Optionally: `docs/operations/production-acceptance-template.md`

**Approach:** Sections for graph-aware artifact digests (P12-06), security (P12-03), DR/backup/runtime graph rebuild (P12-04), ingress/SSE/graph HTTP (P12-05), browser/capacity/full demo (P12-07), RPO/RTO, residuals, and decision block. Refuse tag-only or mixed-revision acceptance.

**Patterns to follow:** `docs/quality/definition-of-done.md` production evidence; child P12 evidence docs

**Test scenarios:**
- Happy: template maps every checklist row to a fillable field.
- Error: tag-only image references without digests → incomplete.

**Verification:** Template ready before go decision.

---

### U3. Runbook ownership and recovery objectives

**Goal:** Operators know who/what/how, including graph extraction/runtime failures and the full demonstration; RPO/RTO objectives are stated honestly.

**Requirements:** R3, R4

**Dependencies:** U1

**Files:**
- Create or modify: `docs/operations/runbook-ownership.md` (name flexible)
- Modify/create: `docs/operations/*` runbooks as needed

**Approach:** Ownership table for Compose, full demo startup, backup/restore, ingress drain, incident reclaim, Reducto/embedding/extraction/synthesis outage, graph projection failure, source deletion/reconciliation, and LightRAG graph/retrieval rebuild; record architecture RPO≤15m / RTO≤4h objectives plus measured Compose/staging numbers or explicit residual.

**Patterns to follow:** `docs/operations/compose-stack-runbook.md`; P12-04 runbook

**Test scenarios:**
- Happy: each incident class has a runbook link + owner.
- Edge: residual without owner is forbidden; Compose wall-clock alone does not silently claim production SLO.

**Verification:** Ownership table complete and linked from acceptance record.

---

### U4. Release decision evidence

**Goal:** Explicit go/no-go and tracker alignment.

**Requirements:** R5, R6, R7, R8, AE2, AE3, AE4, AE5, AE6

**Dependencies:** U1–U3; **P12-03..07 DONE**

**Files:**
- Modify: `docs/_scratch/p12-08-production-acceptance-evidence.md` (filled decision)
- Modify: `docs/master-build-plan.md`

**Approach:** Cite compatible digests, graph-aware drills, E2E/full demo, security, and ingress evidence; execute the operator demonstration once against the candidate artifacts; decide go/no-go with named residuals only (no Wiki/observability invent); update tracker to match.

**Patterns to follow:** prior P12 evidence closures

**Test scenarios:**
- Error: missing P12-07 (or any of P12-03..07) → no-go language.
- Happy: all present → go with residuals list.
- Edge: residuals explicitly exclude inventing Wiki/observability product surfaces.
- Error: graph unavailable, empty because the extraction stub is still active, leaking raw runtime fields, inaccessible without the canvas/list equivalent, or missing deletion/rebuild proof → no-go.
- Error: any child evidence references an incompatible pre-graph schema, contract, source revision, or image digest → no-go.

**Verification:** Tracker matches decision.

---

## Verification Contract

- Checklist completeness review.
- All dependency evidence paths resolve.
- No new product code required unless a gap forces no-go remediation (then re-open owning task).

## Definition of Done

R1–R8 and AE1–AE6 satisfied with either go (P12-08 DONE, P12 phase DONE) or documented no-go blockers.

## Sources & Research

- docs/quality/definition-of-done.md
- docs/master-build-plan.md P12-08
- docs/_scratch/legacy-gap-plan-bundle.md
