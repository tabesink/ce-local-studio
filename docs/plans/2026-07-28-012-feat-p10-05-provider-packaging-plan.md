---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P10-05 Provider and Parser Packaging - Plan
type: feat
date: 2026-07-28
---

# P10-05 Provider and Parser Packaging - Plan

## Goal Capsule

- **Objective:** Close P10-05 by packaging Docling/Reducto and OpenAI/Bedrock/Ollama adapters into explicit deployment profiles with no-network CI fixtures retained and credential-gated staging smoke required before claiming a provider production-supported.
- **Authority:** docs/tech-stack.md; as-built-gaps parsers/providers; P4-03/P7-03; docs/master-build-plan.md P10-05.
- **Execution profile:** Packaging + matrix docs + optional smoke scripts; do not force live providers into root verify.
- **Readiness checkpoint:** Implementation-ready after 2026-07-28 bundle packaging.
- **Stop conditions:** Stop if claiming unsupported providers green, scaffolding browser provider selection, or making root CI require network providers.
- **Tail ownership:** P12-06 locks/SBOM; P12-07 failure paths; P12-08 acceptance.

---

## Product Contract

### Summary

Define which parser/model extras ship in which images/profiles; keep CI fixture altitude; require credential-gated staging smoke before production-supported claims.

Product Contract preservation: authored from P10-05 bootstrap.

### Problem Frame

Adapters exist at fixture altitude; optional extras and fail-closed registry entries leave operators unsure what is production-supported. Root verify must not gain live network dependence.

### Actors

| Actor | Role |
| --- | --- |
| Operator | Selects deployment profile and supplies credentials |
| Coding agent | Packaging, matrix, smoke scripts, evidence |

### Key Flows

**F1 — Profile matrix.** Document/image profiles declare included parser/synthesis extras and fail-closed kinds.

**F2 — CI.** Default verify uses injectable transports only.

**F3 — Staging smoke.** Credential-gated script exercises each claimed provider; failures keep fail-closed claim.

### Requirements

- R1. Inventory `docs/_scratch/p10-05-provider-packaging-inventory.md`.
- R2. Explicit packaging for Docling/Reducto and OpenAI/Bedrock/Ollama in pyproject/images/docs.
- R3. Deployment profile matrix: which kinds are packaged, fail-closed, or production-supported only after smoke.
- R4. CI remains no-network fixture altitude.
- R5. Credential-gated staging smoke scripts/runbook steps; never commit secrets.
- R6. Evidence + tracker DONE with honest unsupported residuals.

### Acceptance Examples

- AE1. Matrix lists each provider/parser with status.
- AE2. Default verify green without network providers.
- AE3. Smoke script refuses to run without explicit credentials/env gate.
- AE4. Unsmoked Bedrock/Ollama remain fail-closed if not proven.

### Scope Boundaries

#### In scope

- Packaging, matrix, smoke gates, docs/evidence

#### Deferred to Follow-Up Work

- New provider kinds beyond tech-stack list

#### Outside this product's identity

- Browser-selected providers; cost dashboards

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | Production-supported requires smoke evidence | Honest claims |
| KTD2 | CI stays fixture-only | Root gate stability |
| KTD3 | Fail-closed default for unproven kinds | Safety |

### Assumptions

- OpenAI synthesis and Docling/Reducto are the first smoke candidates.
- Ollama is local-only egress.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Secret leakage in smoke logs | Allowlisted logging; redaction |
| Scope creep to new vendors | Tech-stack closed list |

---

## Implementation Units

### U1. Packaging inventory

**Goal:** Freeze extras/images/registry seams.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `docs/_scratch/p10-05-provider-packaging-inventory.md`

**Approach:** Table parser/synthesis kinds vs package/image/CI/smoke status.

**Patterns to follow:** as-built-gaps bullets

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Matrix draft complete.

---

### U2. Packaging extras and image layers

**Goal:** Make Docling/Reducto/OpenAI/Bedrock/Ollama extras and image layers explicit.

**Requirements:** R2

**Dependencies:** U1

**Files:**
- Modify: `app/pyproject.toml` / Dockerfiles as needed
- Test: existing parser/synthesis fixture suites; missing-dep fail-closed checks

**Approach:** Minimal packaging changes; keep default CI image on fixtures; no browser config.

**Patterns to follow:** as-built-gaps optional extras notes; P10-01 compose config

**Test scenarios:**
- Happy: image build with declared extras still succeeds in verify Docker step.
- Edge: fail-closed kinds remain registered without network.

**Verification:** Docker build + import tests; default verify green.

---

### U3. Deployment-profile matrix

**Goal:** Operator-facing matrix of profiles, kinds, env, egress, and evidence altitude.

**Requirements:** R3, AE1

**Dependencies:** U2

**Files:**
- Create: `docs/operations/provider-deployment-profiles.md` (name flexible)
- Modify: `docs/operations/compose-stack-runbook.md` / `docs/tech-stack.md` profile notes

**Approach:** Compact table: packaged vs fail-closed vs production-supported-after-smoke; local vs leave-deployment egress; CI vs staging columns.

**Patterns to follow:** `docs/tech-stack.md`

**Test scenarios:**
- Happy: matrix lists each tech-stack provider/parser with status.
- Error: no browser-selectable provider UI documented as product surface.

**Verification:** Matrix linked from runbook; matches inventory.

---

### U4. Credential-gated staging smoke scripts

**Goal:** Prove claimed providers before production-supported label.

**Requirements:** R4, R5, AE2, AE3, AE4

**Dependencies:** U2, U3

**Files:**
- Create: `app/scripts/provider_staging_smoke.py` (name flexible)
- Modify: runbook
- Create: tests that smoke refuses without gate env

**Approach:** Script requires explicit env allowlist; exercises bounded success/timeout/auth-fail mapping; records evidence artifact path. Never wire into default `scripts/verify.sh`.

**Patterns to follow:** `app/scripts/stack_smoke_*.py`

**Test scenarios:**
- Error: missing gate env → refuse before network.
- Happy: with fixtures/injectable, mappings stay typed (CI).
- Integration: live smoke only under credentials (evidence, not default verify).

**Verification:** Refuse test on default path; live evidence optional.

---

### U5. Evidence and tracker

**Goal:** Close P10-05 with honest per-kind status.

**Requirements:** R6, AE1

**Dependencies:** U1–U4

**Files:**
- Create: `docs/_scratch/p10-05-provider-packaging-evidence.md`
- Modify: `docs/master-build-plan.md`

**Approach:** Publish matrix statuses; residuals named (P12-06/07/08); no dishonest production-supported claims.

**Patterns to follow:** `docs/_scratch/p10-03-worker-lifecycle-evidence.md`

**Test scenarios:**
- Test expectation: none -- docs.
- Edge: unsmoked kinds remain fail-closed explicitly.

**Verification:** Tracker DONE.

---

## Verification Contract

- Default verify remains no-network.
- Packaging/build checks green.
- Smoke refuse-without-gate test green.

## Definition of Done

R1–R6 and AE1–AE4 satisfied; no dishonest production-supported claims; P10-05 DONE.

## Sources & Research

- docs/tech-stack.md
- docs/architecture/as-built-gaps-and-decisions.md
- docs/master-build-plan.md P10-05
