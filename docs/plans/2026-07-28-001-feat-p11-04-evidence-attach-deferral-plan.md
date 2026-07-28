---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
phase_compatibility: phase-1-child
title: P11-04 Evidence Attach UX Deferral - Plan
type: feat
date: 2026-07-28
enriched: 2026-07-28
origin: docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md
tracker: docs/master-build-plan.md#P11-04
---

# P11-04 Evidence Attach UX Deferral - Plan

## Goal Capsule

- **Objective:** Record a durable product decision to defer Phase 1 Evidence attach UX — including P11-04 suggest-and-confirm chips and prioritization of References/inspector Evidence attach unlock — until observed member pain or a proven grounding-quality gap; keep sealed chat and server composer-ref plumbing Done without shipping unused attach surface.
- **Authority:** Root `AGENTS.md` (one-domain retrieval, grounded Evidence, sealed chat); `docs/prd.md#closed-phase-1-chat-capability-manifest` and FR-07; M-09 governed-ref attach rules; `docs/master-build-plan.md` P11-04 product gate; prior umbrella plan `docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md` (APPROVED path superseded for UX shipping); this Product Contract (R1–R9).
- **Execution profile:** Docs/tracker closure only. No HTTP/DTO/frontend contract amendments; no chat-shell or composer-refs service changes.
- **Stop conditions:** Stop if DONE pressure ships suggestion UI, invents public suggestion fields, unlocks References for Evidence, weakens sealed-chat acceptance, or marks P11-04 Done without R5/R6 reopen evidence.
- **Tail ownership:** Source/template attach unlock remains a separate residual (unchanged by this slice). Umbrella U2–U5 stay unstarted until a future APPROVED validation. P12 E2E remains later.

---

## Product Contract

Product Contract preservation: Product Contract unchanged (R1–R9, AE1–AE4, Key Decisions, Scope Boundaries preserved from brainstorm enrichment).

### Summary

Do not ship Evidence suggest-and-confirm or prioritize Evidence attach-chip unlock in Phase 1 UX.
Members rely on per-turn domain RAG.
Treat P11-04 as **DEFERRED**; leave sealed baseline and P11-01..03 server capability Done; browser may keep empty `composerRefTokens` and unavailable References until reopen criteria fire.

### Problem Frame

Evidence reattachment was framed as follow-up speed, but no member has hit re-hunt pain yet — it remains a hypothesis.
In a RAG workstation, each `domain_rag` turn already re-retrieves in one authorized domain, so pin/suggest UX is convenience, not a prerequisite for grounded answers.
Domain switching is a poor primary job for carry-forward: Evidence is domain-bound, and cross-domain attach is a safety/invalid-chip problem, not a happy path.
Shipping suggestion or attach chips on hypothesis risk adds noise and contract surface without proven value.

### Key Decisions

- **Defer all Evidence attach UX for now.** No suggest strip and no priority on unlocking References or inspector “use on next turn” for Evidence until reopen criteria are met.
- **Retrieval over pin.** Prefer fixing retrieval/grounding quality before adding pin UX as a workaround.
- **Server capability may remain dormant.** P11-01..03 discover/consume/fingerprint stay Done; unavailable browser attach is acceptable.
- **Supersede the umbrella APPROVED shipping path for UX.** The lean-agent-shell umbrella’s suggest-and-confirm implementation units stay gated; this decision records DEFER instead of APPROVED for contract/UI work.
- **Domain-switch carry-forward is out.** Do not justify Evidence attach UX as a domain-switching feature.

### Actors

| Actor | Role |
| --- | --- |
| Member | Asks domain-grounded questions; relies on per-turn retrieval while attach UX stays unavailable |
| Product owner | Owns DEFER sign-off and reopen when pain or grounding gap is observed |
| FastAPI / retrieval | Continues one-domain authorized retrieval and grounded terminals without requiring composer Evidence refs |

### Requirements

**Deferral stance**

- R1. Phase 1 does not ship Evidence suggest-and-confirm UI (unconfirmed chips that become ordered refs only after accept).
- R2. Phase 1 does not prioritize unlocking Evidence attach chips via References picker or inspector pin until reopen criteria in R5–R6 are met.
- R3. Sealed SSE, grounded terminals (`no_grounded_context` / `evidence_only`), and the Evidence/Refs/Source workbench remain independently Done and must not be reopened or weakened to make room for attach UX.
- R4. Server composer-ref schema, consume, fingerprint, and replay (P11-01..03) may remain in place; the browser may continue submitting empty Evidence attach tokens and showing References unavailable without claiming P11-04 Done.

**Reopen criteria**

- R5. Reopen Evidence attach UX only after observed member pain: re-asking to re-ground, copying excerpts into questions, or explicit inability to pin a prior citation.
- R6. Alternatively reopen when a grounding-quality gap is shown: retrieval repeatedly misses a passage the member already saw on a prior turn in the same domain — and retrieval/ranking fixes are evaluated before pin UX.
- R7. Domain change alone is not a reopen trigger for Evidence carry-forward suggestions.

**Tracker honesty**

- R8. P11-04 validation/status must record **DEFER** (not APPROVED); no HTTP/DTO/frontend contract amendments for suggestions while deferred.
- R9. Residuals must name Evidence attach / References unlock as deferred pending R5–R6, without implying the sealed baseline is incomplete.

### Acceptance Examples

- AE1. **DEFER closes without UI**
  - **Given:** Product owner confirms hypothesis-only need and retrieval-first stance
  - **When:** P11-04 gate is resolved
  - **Then:** Status is DEFER; no suggestion DTO/UI ships; sealed baseline stays Done
- AE2. **Reopen on observed pain**
  - **Given:** Members repeatedly copy prior excerpts or ask for pin because follow-ups lose the citation
  - **When:** Product owner reopens Evidence attach
  - **Then:** Work resumes from a fresh APPROVED validation (or successor brief), not silent UI unlock
- AE3. **Reopen on grounding gap prefers retrieval first**
  - **Given:** Same-domain follow-ups miss a passage already shown as Evidence last turn
  - **When:** The gap is confirmed
  - **Then:** Retrieval/ranking remediation is considered before shipping pin/suggest UX
- AE4. **Domain switch does not unlock carry-forward**
  - **Given:** Member changes next-turn domain
  - **When:** No R5/R6 evidence exists
  - **Then:** No suggest-or-attach project starts solely to carry Evidence across domains

### Scope Boundaries

**In scope for this decision**

- Durable DEFER for P11-04 suggest-and-confirm and deprioritized Evidence attach unlock
- Reopen criteria (pain, grounding gap) and tracker/validation honesty
- Explicit non-weakening of sealed chat baseline

**Deferred for later (only if R5 or R6)**

- Evidence suggest-and-confirm (umbrella APPROVED package)
- References / inspector Evidence attach unlock
- Ranking/cap/compose-epoch dismissal rules for suggestions

**Outside this decision**

- Removing or redesigning P11-01..03 server composer-ref capability
- Source/template attach unlock (not decided here; remains a separate residual unless later tied to the same pain)
- Domain-switch carry-forward as a product feature
- Weakening grounded refusal or one-domain retrieval
- Tools, plugins, ambient memory, or a second chat-RAG store

### Deferred to Follow-Up Work

- Annotating the umbrella plan body as superseded (optional honesty; not required for tracker closure)
- Source/template References unlock prioritization (separate residual)

### Dependencies / Assumptions

- Assumption: Per-turn domain RAG is sufficient for Phase 1 follow-ups until R5/R6 evidence appears.
- Dependency: P7/P9 sealed workbench and P11-01..03 server refs remain the baseline; this decision only blocks Evidence attach UX shipping.
- Related: `docs/_scratch/p11-04-evidence-reattachment-validation.md` must become Status **DEFER**; umbrella U2–U5 stay unstarted.

### Sources / Research

- `docs/master-build-plan.md` P11-04 BLOCKED product gate; P11-01..03 DONE with browser unlock residual
- `docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md` (prior APPROVED-path umbrella; UX shipping superseded by this DEFER)
- `docs/_scratch/p11-04-evidence-reattachment-validation.md` (pending → DEFER)
- `AGENTS.md` one-domain retrieval and grounded-Evidence invariants
- Brownfield: chat submits `composerRefTokens: []`; References unavailable in chat shell

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Tracker status is `DEFERRED`.** Use the master-build-plan status value `DEFERRED` (not `BLOCKED` with a prose note, not `DONE`). Deliverable text cites this plan and the validation DEFER record. (session-settled: user confirmed scoping defaults)
- KTD2. **Source/template residual untouched.** Do not change residual language that implies source/template attach unlock timing; only Evidence attach / P11-04 / References Evidence path. (session-settled: user confirmed scoping defaults)
- KTD3. **Docs-only slice.** No OpenAPI regeneration, no client characterization unlock, no composer_refs service edits. Proof is artifact consistency, not runtime tests.
- KTD4. **Umbrella APPROVED path stays gated.** Do not edit HTTP/DTO/frontend catalogs for suggestions; point residual readers at this plan + validation DEFER instead of starting umbrella U2.
- KTD5. **Validation axes filled from brainstorm.** Axis 1 = hypothesis only / not observed; Axis 2 = accept/dismiss comprehension accepted as product rule but moot while deferred; Axis 3 = no pressure to weaken sealed baseline (explicit yes).

### Assumptions

- Product-owner sign-off for this DEFER is the session confirmation of the brainstorm synthesis and this plan’s scoping gate (Decided by: product owner / session actor; Date: 2026-07-28).
- P11 phase row may remain DONE with wording that P11-04 is DEFERRED (server governed-context assembly complete; Evidence attach UX deferred).

### Sequencing

1. U1 — write DEFER into the validation decision record (hard gate artifact).
2. U2 — inventory note + evidence file for deferral honesty.
3. U3 — tracker/residual updates to `DEFERRED` with reopen criteria named.

---

## Implementation Units

### U1. Record DEFER validation decision

**Goal:** Convert the pending P11-04 validation scratch into a signed DEFER decision with all three PO axes filled.

**Requirements:** R1–R3, R5–R8, AE1, AE4; KTD5

**Dependencies:** None

**Files:**
- Modify: `docs/_scratch/p11-04-evidence-reattachment-validation.md`

**Approach:**
- Set Status to **DEFER** (not FAILED unless wording requires; prefer DEFER per brainstorm).
- Fill Axis 1: hypothesis only; no observed repeated reattachment need; RAG re-retrieve preferred.
- Fill Axis 2: product accepts that suggestion ≠ attach and dismiss is epoch-local — deferred, so no UI ships that would violate this.
- Fill Axis 3: yes — sealed baseline stays Done; suggestions must not reopen it.
- Manifest disposition: leave unchecked / note N/A for DEFER (no APPROVED path).
- Sign-off: Status DEFER; Outcome DEFER; Date 2026-07-28; Decided by session product-owner confirmation; cite `docs/plans/2026-07-28-001-feat-p11-04-evidence-attach-deferral-plan.md`.
- State that U2+ of the umbrella plan must not start.

**Execution note:** Documentation-only. Do not amend contracts or unlock UI.

**Patterns to follow:** `docs/_scratch/p6-02-evidence-contract-decision.md` status/sign-off shape; existing pending validation skeleton.

**Test scenarios:**
- Happy path: File Status is DEFER; all three axes non-empty; Outcome DEFER; cites this plan.
- Edge: APPROVED or pending left in Status → unit incomplete.
- Error: Any HTTP/DTO/frontend contract diff in the same unit → stop; out of scope.

**Verification:** Validation file is reviewable as DEFER; no contract/UI files changed.

---

### U2. Deferral inventory note and evidence artifact

**Goal:** Record readiness inventory as closed-for-deferral and publish P11-04 evidence that maps AE1/AE4 without claiming Done.

**Requirements:** R1–R4, R8–R9, AE1; umbrella U6 DEFER path

**Dependencies:** U1

**Files:**
- Modify: `docs/_scratch/p11-04-evidence-reattachment-inventory.md`
- Create: `docs/_scratch/p11-04-evidence-reattachment-evidence.md`

**Approach:**
- Inventory: cite validation Status DEFER at top; amendment checklist remains unchecked; note U2–U5 blocked until reopen; next step = tracker update (U3) then stop.
- Evidence: cite validation DEFER + this plan; confirm no suggestion DTO/HTTP fields added; confirm sealed baseline language unchanged; name reopen criteria (R5/R6); name residuals (Evidence attach / References unlock deferred; source/template residual unchanged; P12 E2E later).
- Explicitly state browser may keep `composerRefTokens: []` and References unavailable.

**Execution note:** Documentation-only. Prefer grep/spot-check of catalogs for absence of suggestion fields rather than inventing tests.

**Patterns to follow:** `docs/_scratch/p11-03-assembly-fingerprint-replay-evidence.md` residual honesty; inventory gate language already in the U1 inventory file.

**Test scenarios:**
- Happy path (Covers AE1.): Evidence cites DEFER validation; checklist unchecked; no claim of P11-04 Done.
- Edge: Evidence claims APPROVED path or References unlock Done → reject.
- Integration: Spot-check `docs/contracts/http-api-catalog.md` and `docs/contracts/dto-schema-catalog.md` for absence of Evidence-suggestion endpoints/DTOs introduced by this slice.

**Verification:** Evidence + inventory agree with DEFER; catalogs unchanged by this slice.

---

### U3. Tracker and residual closure to DEFERRED

**Goal:** Move P11-04 to `DEFERRED` in trackers with honest residuals and reopen criteria.

**Requirements:** R8, R9, AE1; KTD1, KTD2

**Dependencies:** U1, U2

**Files:**
- Modify: `docs/master-build-plan.md` (P11 phase summary line; P11-04 row; P11-03 residual pointer if it still says P11-04 remains as if still gated-open)
- Modify: `docs/brownfield-refactor-register.md` (hashed composer tokens row residual mentioning P11-04)
- Modify as needed: `docs/_scratch/p11-03-assembly-fingerprint-replay-evidence.md` residual pointers (honesty only)

**Approach:**
- P11-04 status → `DEFERRED`; deliverable text: product DEFER — Evidence attach UX / suggest-and-confirm not shipping until observed pain or grounding-quality gap; evidence `docs/_scratch/p11-04-evidence-reattachment-evidence.md`; validation `docs/_scratch/p11-04-evidence-reattachment-validation.md`.
- P11 phase summary: keep phase DONE for P11-01..03; replace “P11-04 remains product-gated BLOCKED” with “P11-04 DEFERRED (Evidence attach UX)”.
- Brownfield residual: replace “P11-04 remain” with deferred Evidence attach / References unlock pending reopen criteria; do not imply server P11 incomplete.
- Do not edit source/template residual wording beyond Evidence/P11-04 clarity (KTD2).
- Do not mark References picker Done.

**Execution note:** Documentation-only tracker honesty.

**Patterns to follow:** Prior P11-03 closure residual language; master-build-plan status vocabulary (`DEFERRED`).

**Test scenarios:**
- Happy path (Covers AE1.): P11-04 is `DEFERRED`; evidence pointer present; not `DONE`.
- Edge: Phase P11 still claims P11-04 BLOCKED waiting for PO with empty axes → stale; must match validation DEFER and tracker `DEFERRED`.
- Error: Any suggestion UI/contract files modified → out of scope.

**Verification:** Tracker, validation, and evidence agree; sealed-baseline acceptance language unchanged.

---

## Verification Contract

| Gate | What proves it |
| --- | --- |
| Product gate | `docs/_scratch/p11-04-evidence-reattachment-validation.md` Status **DEFER** with three axes filled |
| No ship | No new suggestion HTTP/DTO/frontend contract fields; umbrella U2–U5 not started |
| Evidence | `docs/_scratch/p11-04-evidence-reattachment-evidence.md` maps AE1/AE4; reopen R5/R6 named |
| Tracker | P11-04 `DEFERRED` in `docs/master-build-plan.md`; brownfield residual honest |
| Baseline | Sealed chat / P11-01..03 Done language preserved; References unlock not claimed Done |

Root `release:validate` is **not** required for this docs-only slice; document that boundary in the evidence file.

---

## Definition of Done

### Global

- [ ] Validation Status is DEFER with three axes + sign-off
- [ ] Evidence artifact published; inventory checklist remains unchecked
- [ ] P11-04 tracker status is `DEFERRED` (not DONE, not pending BLOCKED)
- [ ] No suggestion contract/UI shipped
- [ ] Sealed baseline and P11-01..03 remain Done
- [ ] References picker unlock not claimed Done
- [ ] Source/template residual not silently expanded or closed
- [ ] Reopen criteria (observed pain; grounding-quality gap with retrieval-first) named in evidence

### Per unit

| Unit | Done when |
| --- | --- |
| U1 | Validation file Status DEFER; three axes filled; cites this plan |
| U2 | Evidence + inventory agree on DEFER; catalogs unchanged |
| U3 | Master-build P11-04 `DEFERRED`; brownfield residual honest |
