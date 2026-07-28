---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P1-07 Durable Idempotency and Keyset Pagination - Plan
type: feat
date: 2026-07-28
---

# P1-07 Durable Idempotency and Keyset Pagination - Plan

## Goal Capsule

- **Objective:** Close P1-07 by adding a shared durable HTTP create-idempotency record and opaque keyset pagination for cataloged list routes, including conversation create.
- **Authority:** Root AGENTS.md; docs/contracts/http-api-catalog.md Idempotency-Key and pagination; docs/master-build-plan.md P1-07; docs/brownfield-refactor-register.md comparative-gap addendum; docs/quality/definition-of-done.md.
- **Execution profile:** Inventory-first brownfield; YAGNI/KISS/DRY; credit existing proofs; dual-lane CI where noted.
- **Readiness checkpoint:** Implementation-ready for coding-agent execution after 2026-07-28 legacy-gap bundle packaging.
- **Stop conditions:** Stop if DONE pressure invents user CRUD mutations, browser UI, Redis/RQ, or uncataloged endpoints; do not weaken ownership 404 non-disclosure.
- **Tail ownership:** P9-07/P12-07 consume list/create UX; broader DRIFT-01 response-component adoption remains vertical-owned.

---

## Product Contract

### Summary

Implement one PostgreSQL-backed Idempotency-Key + fingerprint store for cataloged create/operation routes, and opaque keyset pagination returning `{items|capabilityCollection,nextCursor}` for users/domains/sources/operations/documents/conversations lists.

Product Contract preservation: Product Contract authored here from master-build-plan bootstrap; no upstream brainstorm IDs to preserve.

### Problem Frame

The HTTP catalog already requires Idempotency-Key semantics and opaque cursors, but routes return nextCursor:null or omit durable create-idempotency. Conversation create was explicitly deferred pending a shared durable record. Without this primitive, concurrent creates can double-apply and lists cannot page safely under multi-user load.

### Actors

| Actor | Role |
| --- | --- |
| Administrator | Creates domains/profiles and lists admin collections |
| Member | Creates conversations and lists owned conversations/documents |
| Coding agent | Inventory, migration, service, route adoption, tests, evidence |

### Key Flows

**F1 — Idempotent create.** Client retries same Idempotency-Key + fingerprint → reuse prior result; changed body → 409 idempotency_conflict; concurrent same-key races serialize to one outcome.

**F2 — Keyset page.** Client lists with limit/cursor → stable (createdAt,id) page + opaque nextCursor; malformed/foreign cursor → cursor_expired.

**F3 — Conversation create adoption.** POST /conversations uses the shared durable record (no longer deferred).

### Requirements

- R1. Inventory seams in docs/_scratch/p1-07-idempotency-pagination-inventory.md with credit/gap dispositions.
- R2. Add durable idempotency table(s) storing key hash, fingerprint, principal scope, route class, response ref/status, created_at; never store raw request bodies with secrets.
- R3. Same key+fingerprint reuses result; mismatch → 409 idempotency_conflict; prove concurrent same-key on PostgreSQL 16.
- R4. Adopt Idempotency-Key on cataloged create/operation routes that already list it, including conversation create.
- R5. Implement opaque keyset pagination for GET admin users/domains/sources/operations, GET documents, GET conversations with limit default 50 max 100.
- R6. Conversation cursors carry versioned public refs and owner-filter before keyset derivation; wrong-owner/malformed → cursor_expired.
- R7. Evidence in docs/_scratch/p1-07-idempotency-pagination-evidence.md; mark P1-07 DONE and reopen/close P1 phase honestly.

### Acceptance Examples

- AE1. Inventory freezes every cataloged Idempotency-Key and nextCursor surface.
- AE2. Concurrent identical create with one key yields one row and matching responses.
- AE3. Changed body same key → 409 idempotency_conflict.
- AE4. List pages return opaque nextCursor until exhausted; null only on last page.
- AE5. Conversation create with Idempotency-Key is durable and replay-safe.

### Scope Boundaries

#### In scope

- Shared durable idempotency primitive
- Keyset pagination on cataloged list routes
- Conversation create adoption
- PostgreSQL concurrency proofs
- Inventory/evidence/tracker

#### Deferred to Follow-Up Work

- Broader handwritten response DTO adoption (DRIFT-01)
- Browser list virtualization (P9/P12)

#### Outside this product's identity

- User admin mutation APIs
- Redis/RQ caches
- Wiki/audit-read lists

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | One shared idempotency store keyed by principal+route-class+key-hash | Avoid per-route bespoke tables |
| KTD2 | Store fingerprint of effective inputs, not raw secrets | Privacy invariant |
| KTD3 | Opaque cursors encode prior public ref/version only | No private IDs in browser |
| KTD4 | Credit existing unique constraints; add only missing durability | YAGNI |

### Assumptions

- Catalog pagination naming may be capability-specific but nextCursor semantics are shared.
- No browser work in this slice.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Double-write under race | PG unique + transaction claim |
| Cursor leaking foreign rows | Owner-filter before keyset |

---

## Implementation Units

### U1. Idempotency and pagination inventory

**Goal:** Freeze credit/gap surfaces before code.

**Requirements:** R1, AE1

**Dependencies:** None

**Files:**
- Create: docs/_scratch/p1-07-idempotency-pagination-inventory.md

**Approach:** Table every catalog Idempotency-Key and nextCursor route with current behavior and disposition.

**Patterns to follow:** docs/_scratch/p12-03-adversarial-security-inventory.md

**Test scenarios:**
- Test expectation: none -- inventory unit.

**Verification:** Every listed catalog surface has a disposition.

---

### U2. Durable idempotency schema and service

**Goal:** Shared create-idempotency primitive with race proofs.

**Requirements:** R2,R3,AE2,AE3

**Dependencies:** U1

**Files:**
- Create/modify: app/migrations/* idempotency
- Modify: app/context_engine/services (shared helper)
- Create: app/tests/test_idempotency_store.py
- Create: app/tests/test_postgres_idempotency_races.py

**Approach:** Migration + service helper that claims/reuses by key hash+fingerprint inside a transaction; map conflicts to approved ErrorCodes.

**Patterns to follow:** P7-04 client_request_id attach/replay; protected-mutation helper

**Test scenarios:**
- Happy: replay returns prior result without second side effect.
- Error: fingerprint mismatch → 409.
- Integration: concurrent same-key PostgreSQL race → one winner.

**Verification:** PG race suite green.

---

### U3. Route adoption for create + keyset lists

**Goal:** Wire cataloged creates and list routes.

**Requirements:** R4,R5,R6,AE4,AE5

**Dependencies:** U2

**Files:**
- Modify: conversation/domain/model-profile/source route+service modules
- Modify: list query handlers for users/domains/sources/operations/documents/conversations
- Create/modify: app/tests/test_*_pagination*.py and HTTP contract tests

**Approach:** Adopt helper on create routes listing Idempotency-Key; replace nextCursor:null stubs with keyset; conversation cursor ownership filter.

**Patterns to follow:** http-api-catalog pagination section

**Test scenarios:**
- Happy: second page returns remaining items.
- Edge: limit clamp 1..100.
- Error: foreign conversation cursor → cursor_expired.
- Integration: conversation create idempotent replay.

**Verification:** Focused HTTP/PG tests green; OpenAPI regenerated if needed.

---

### U4. Evidence and tracker closure

**Goal:** Honest DONE.

**Requirements:** R7

**Dependencies:** U3

**Files:**
- Create: docs/_scratch/p1-07-idempotency-pagination-evidence.md
- Modify: docs/master-build-plan.md

**Approach:** Record commands/case IDs/residuals; mark P1-07 DONE; set P1 phase DONE if no other open P1 tasks.

**Patterns to follow:** p12-02 evidence shape

**Test scenarios:**
- Test expectation: none -- docs/tracker.

**Verification:** Tracker links evidence.


---

## Verification Contract

- Inventory + evidence pair.
- Default pytest + opted-in PostgreSQL race tests.
- Contract snapshots regenerated if response/query shapes change.
- Privacy: no raw secrets in idempotency rows.

## Definition of Done

1. R1–R7 and AE1–AE5 satisfied.
2. Authorization/privacy boundaries intact.
3. P1-07 DONE with evidence.
4. No invented user mutations or Redis.

## Sources & Research

- docs/contracts/http-api-catalog.md
- docs/master-build-plan.md P1-07
- docs/_scratch/legacy-gap-plan-bundle.md
