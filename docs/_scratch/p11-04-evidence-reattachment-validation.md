# P11-04 Evidence Reattachment Validation

Date: 2026-07-28

Status: **pending product-owner review** — not APPROVED; not FAILED/DEFER.  
U2+ contract amendment and UI must not start until Status is **APPROVED**.

Authority: `docs/master-build-plan.md` P11-04; `docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md` (R6–R13, KTD1–KTD2); `docs/prd.md#closed-phase-1-chat-capability-manifest`.

## Decision under review

Whether Phase 1 should add **Evidence suggest-and-confirm carry-forward**: after a completed grounded turn with eligible Evidence, offer unconfirmed composer suggestions that become ordered attached refs only after an explicit member accept; dismissals are tab-local compose-epoch only.

### Recommended APPROVED package (if the three axes below are satisfied)

1. Treat suggestions as a **confirm-gated UI over existing FR-07 / M-09** governed-ref attach authority — not a new competing closed-capability-manifest bullet, and not a tool/memory/fat-agent expansion (plan KTD2).
2. Unconfirmed suggestions use a **tokenless or mint-on-accept** projection; do not reuse eager `POST /composer-refs:discover` minting for browse/refetch (plan KTD3).
3. Candidate set defaults to **eligible Evidence on the latest completed grounded turn** for the selected next-turn domain; ranking by citation/display order; hard cap **5**; multi-accept order = member accept order (plan KTD4 / KTD10).
4. Dismissals are **compose-epoch tab memory only** — never server, localStorage, sessionStorage, or cross-tab sync (R12 / KTD6).
5. Suggestion loading/empty/failure **never blocks** draft or send without suggestions (R11).
6. **References picker unlock** remains a separate residual unless this decision explicitly bundles it (KTD5).
7. Sealed SSE, grounded-terminal, and Evidence/Refs/Source workbench acceptance **remain independently Done**; suggestions must not reopen or weaken that baseline.

### Rejected alternatives (for the APPROVED path)

- Auto-attach / ambient memory / second chat-RAG store.
- Shipping suggestion UI or inventing public DTO fields before this decision is APPROVED.
- Treating the lean-agent-shell Product Contract alone as HTTP/DTO authority without amending versioned catalogs.
- Weakening sealed-chat acceptance to make room for suggestions.

### FAILED / DEFER path (if any required axis fails)

- Leave P11-04 deferred/BLOCKED.
- Do not amend HTTP/DTO/interaction/component/accessibility contracts for suggestions.
- Do not unlock suggestion UI.
- Sealed baseline (P7/P9/P11-01..03) stays Done.

---

## Required evidence axes

All three axes must be filled before Status can become **APPROVED**.  
Partial fill → Status stays pending or becomes **FAILED/DEFER**.

### Axis 1 — Repeated Evidence reattachment need

**Question:** Is there a real, repeated need for members to reattach prior-turn Evidence into a later compose that justifies the contract and UX risk?

**PO response:** _(fill)_

**Evidence / notes:** _(observation, demo transcript, explicit PO statement, or “hypothesis not worth the risk”)_

### Axis 2 — Comprehension of explicit accept / dismiss

**Question:** Does the product owner accept that a suggestion is **not** an ordered composer ref until the member explicitly accepts; that dismiss is epoch-local and non-durable; and that ignore/dismiss must leave draft/send fully usable?

**PO response:** _(fill — yes/no + any conditions)_

**Evidence / notes:** _(fill)_

### Axis 3 — No pressure to weaken the sealed-chat baseline

**Question:** Will suggestions remain a dependent convenience that cannot block or reopen sealed SSE, grounded-terminal, or workbench acceptance? If validation fails, does the product owner accept leaving suggestions unimplemented while the baseline stays Done?

**PO response:** _(fill — yes/no)_

**Evidence / notes:** _(fill)_

---

## Manifest disposition (required when APPROVED)

Per plan KTD2, choose one:

- [ ] **UI over FR-07/M-09** (recommended) — suggestions are confirm-gated composer UI over existing governed-ref attach; no new closed-capability bullet; optional one-line PRD clarify only if non-expansive.
- [ ] **Named capability-manifest bullet** — requires coordinated `docs/prd.md` amend that still forbids tools/plugins/memory/fat-agent surfaces and preserves the sole-manifest rule.

**PO selection:** _(fill)_

---

## Sign-off

| Field | Value |
| --- | --- |
| Status | `pending product-owner review` |
| Decided by | _(name / role)_ |
| Date | _(YYYY-MM-DD)_ |
| Outcome | APPROVED / FAILED / DEFER |

When Status becomes **APPROVED**, cite this file at the top of `docs/_scratch/p11-04-evidence-reattachment-inventory.md` and proceed to plan U2.  
When Status becomes **FAILED** or **DEFER**, record U6 deferral evidence only — no contract or UI suggestion work.
