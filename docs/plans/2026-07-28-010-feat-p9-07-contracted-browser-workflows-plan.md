---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P9-07 Contracted Browser Workflows - Plan
type: feat
date: 2026-07-28
---

# P9-07 Contracted Browser Workflows - Plan

## Goal Capsule

- **Objective:** Close P9-07 by wiring contracted member/admin browser workflows: conversation rename/delete (M-08), ordered composer-ref discovery/attach (M-09), Settings If-Match concurrency (A-01), and domain/source operation-history recovery UX (A-03/A-07/A-09/A-10).
- **Authority:** docs/prd.md; interaction M-08/M-09/A-01/A-03/A-07/A-09/A-10; docs/frontend/* chat/settings/documents contracts; P9-02/P9-04/P11-02/P4-05 dependencies; docs/master-build-plan.md P9-07.
- **Execution profile:** Feature-layer UI against generated clients; Vitest/component altitude; Playwright residual P12-07.
- **Readiness checkpoint:** Implementation-ready after 2026-07-28 bundle packaging.
- **Stop conditions:** Stop if inventing user admin mutation UI, wiki/observability screens, or unapproved DTO fields; do not claim production Playwright DONE.
- **Tail ownership:** P12-07 production-boundary E2E/visual matrix.

---

## Product Contract

### Summary

Unlock contracted browser controls that backend/contracts already support but UI leaves disabled or incomplete.

Product Contract preservation: authored from master-build-plan P9-07 bootstrap.

### Problem Frame

Rename/delete adapters exist without product controls; composer-ref picker remains disabled despite P11-02; Settings mutations omit If-Match despite P2 ETag proofs; operation-history APIs exist while Settings/Documents show only coarse state — blocking recoverable admin operations and member governed-context workflows.

### Actors

| Actor | Role |
| --- | --- |
| Member | Renames/deletes conversations; attaches composer refs |
| Administrator | Mutates credentials/settings with If-Match; inspects operation history; retries/cancels |
| Coding agent | Implements UI + component tests + evidence |

### Key Flows

**F1 — Conversation rename/delete.** Owner renames/deletes → server confirms → list/open views update; cross-owner indistinguishable not-found.

**F2 — Composer refs.** Discover ordered source/evidence/template refs → attach chips → submit consumes tokens; invalid chips identified safely.

**F3 — Settings If-Match.** Admin loads ETag/version → mutation sends If-Match → 428/409 stale_revision handled with refresh.

**F4 — Operation history.** Admin opens domain/source history → sees recoverable states, request IDs, retry/cancel where allowed → refresh reconciles server truth.

### Requirements

- R1. Inventory `docs/_scratch/p9-07-contracted-browser-workflows-inventory.md`.
- R2. Conversation rename/delete UI with server-truth and conflict handling (M-08).
- R3. Enable ordered composer-ref discovery/attach using P11-02 APIs (M-09); no raw tokens in storage.
- R4. Thread If-Match/ETag through Settings credential/runtime mutations (A-01) with two-admin conflict UX.
- R5. Render domain/source operation history with safe failure/request IDs and retry/cancel affordances bound to allowedActions (advisory only).
- R6. Region deep-link behavior depends on P4-05; integrate when available without blocking other units.
- R7. Evidence `docs/_scratch/p9-07-contracted-browser-workflows-evidence.md`; mark P9-07 DONE; P9 phase DONE if no other open P9 tasks.

### Acceptance Examples

- AE1. Owner rename/delete updates list; non-owner sees safe not-found.
- AE2. Ordered refs submit; expired/duplicate chips fail before provider work with safe labels.
- AE3. Stale Settings mutation shows 409 and refreshes snapshot.
- AE4. Failed cleanup op visible in history with retry path.
- AE5. No passwords/tokens/private IDs in local/session storage.

### Scope Boundaries

#### In scope

- Chat rename/delete; composer refs UI; Settings If-Match; operation history panels; component tests; evidence

#### Deferred to Follow-Up Work

- Playwright production matrix (P12-07)
- User admin mutation UI (no contract)

#### Outside this product's identity

- Wiki/observability routes; browser-selected providers

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | Use generated clients only | DRIFT-01 chat precedent |
| KTD2 | allowedActions advisory; reauthorize every mutation | Backend authority |
| KTD3 | Vitest altitude for DONE; Playwright residual P12-07 | Matches P9-04 |

### Assumptions

- P11-02 discover/consume APIs remain green.
- P4-05 may land in parallel; region highlight integrates when ready.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Storing composer tokens | Memory-only; clear on identity change |
| Scope creep into users CRUD | Explicit out of scope |

---

## Implementation Units

### U1. Browser workflow inventory

**Goal:** Freeze disabled controls and API readiness.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `docs/_scratch/p9-07-contracted-browser-workflows-inventory.md`

**Approach:** Call-site table for rename/delete, refs picker, Settings mutations, op history.

**Patterns to follow:** p9-02/p9-04 inventories

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Every required workflow has disposition.

---

### U2. Chat rename/delete and composer refs

**Goal:** M-08/M-09 UI.

**Requirements:** R2,R3,AE1,AE2,AE5

**Dependencies:** U1

**Files:**
- Modify: `app/client/src/features` chat discovery/composer modules
- Create/modify: chat feature tests

**Approach:** Wire rename/delete to generated APIs; unlock discover/attach ordered refs; preserve drafts on recoverable failures; never persist raw tokens.

**Patterns to follow:** P9-02 workbench; P11-02 contracts

**Test scenarios:**
- Happy: rename/delete server-confirmed.
- Happy: ordered refs attach/submit.
- Error: invalid ref chip safe messaging.
- Privacy: no token in storage.

**Verification:** Node/Vitest tests green.

---

### U3. Settings If-Match and operation history

**Goal:** A-01 concurrency + recoverable ops UX.

**Requirements:** R4,R5,AE3,AE4

**Dependencies:** U1

**Files:**
- Modify: Settings providers/domains/documents admin features
- Create/modify: settings/documents tests

**Approach:** Capture ETag/version from GET; send If-Match; handle 428/409; render operation history lists from cataloged GET operations endpoints.

**Patterns to follow:** P2-02 ETag; P9-04 domains accordion

**Test scenarios:**
- Happy: matching If-Match succeeds.
- Error: stale_revision refresh path.
- Happy: history shows failed cleanup + retry affordance when allowed.

**Verification:** Focused frontend tests green.

---

### U4. Evidence and tracker

**Goal:** Close P9-07.

**Requirements:** R6,R7

**Dependencies:** U2, U3

**Files:**
- Create: `docs/_scratch/p9-07-contracted-browser-workflows-evidence.md`
- Modify: `docs/master-build-plan.md`

**Approach:** Record residuals for P12-07 Playwright; note P4-05 integration status.

**Patterns to follow:** p9-04 evidence

**Test scenarios:**
- Test expectation: none -- docs.

**Verification:** Tracker DONE with residuals.

---

## Verification Contract

- Frontend typecheck + focused Vitest/node tests.
- No Playwright required for P9-07 DONE.
- Privacy storage checks for tokens/secrets.

## Definition of Done

R1–R7 and AE1–AE5 satisfied at component altitude; P9-07 DONE; Playwright residual explicit.

## Sources & Research

- docs/frontend/chat-and-evidence-workbench.md
- docs/frontend/route-and-workspace-spec.md
- docs/master-build-plan.md P9-07
- docs/_scratch/legacy-gap-plan-bundle.md
