# P11-04 Evidence Reattachment Validation

Date: 2026-07-28

Status: **DEFER** — not APPROVED.  
Umbrella plan U2+ contract amendment and suggestion UI must not start.  
Master-build-plan tracker status for this task is **`DEFERRED`** (see sign-off and `docs/plans/2026-07-28-001-feat-p11-04-evidence-attach-deferral-plan.md`).

Authority: `docs/master-build-plan.md` P11-04; `docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md` (R6–R13, KTD1–KTD2); `docs/plans/2026-07-28-001-feat-p11-04-evidence-attach-deferral-plan.md`; `docs/prd.md#closed-phase-1-chat-capability-manifest`.

## Decision

Phase 1 will **not** add Evidence suggest-and-confirm carry-forward or prioritize Evidence attach-chip unlock.
Members rely on per-turn domain RAG until reopen criteria are met.
Sealed baseline (P7/P9/P11-01..03) stays Done.

### Deferred package (not shipping)

The former recommended APPROVED package (confirm-gated UI over FR-07/M-09; tokenless/mint-on-accept; latest-turn cap 5; compose-epoch dismissals; References residual; sealed baseline intact) remains the candidate if/when reopened — it is **not** authorized for contract or UI work now.

### Rejected for now

- Shipping suggestion UI or inventing public DTO fields without APPROVED reopen.
- Treating domain-switch carry-forward as the primary job for Evidence attach.
- Auto-attach / ambient memory / second chat-RAG store.
- Weakening sealed-chat acceptance to make room for suggestions.

### DEFER path (executed)

- Set tracker P11-04 to **`DEFERRED`** (not DONE; not pending BLOCKED).
- Do not amend HTTP/DTO/interaction/component/accessibility contracts for suggestions.
- Do not unlock suggestion UI or prioritize Evidence attach chips (References / inspector pin).
- Sealed baseline (P7/P9/P11-01..03) stays Done.
- Server composer-ref plumbing may remain dormant behind unavailable browser attach.

---

## Required evidence axes

All three axes are addressed for this **DEFER** outcome.

### Axis 1 — Repeated Evidence reattachment need

**Question:** Is there a real, repeated need for members to reattach prior-turn Evidence into a later compose that justifies the contract and UX risk?

**PO response:** No — not observed. Hypothesis only; not worth shipping attach/suggest UX yet.

**Evidence / notes:** Session brainstorm (2026-07-28): “we haven’t hit this yet; it’s a hypothesis.” Per-turn domain RAG already re-retrieves; pin/suggest is convenience, not a Phase 1 prerequisite.

### Axis 2 — Comprehension of explicit accept / dismiss

**Question:** Does the product owner accept that a suggestion is **not** an ordered composer ref until the member explicitly accepts; that dismiss is epoch-local and non-durable; and that ignore/dismiss must leave draft/send fully usable?

**PO response:** Yes — those rules stand if/when the feature is reopened. No suggestion UI ships under DEFER, so there is no surface that can violate them.

**Evidence / notes:** Confirmed in brainstorm; deferred package retains suggest ≠ attach and epoch-local dismiss.

### Axis 3 — No pressure to weaken the sealed-chat baseline

**Question:** Will suggestions remain a dependent convenience that cannot block or reopen sealed SSE, grounded-terminal, or workbench acceptance? If validation fails, does the product owner accept leaving suggestions unimplemented while the baseline stays Done?

**PO response:** Yes.

**Evidence / notes:** Explicit DEFER of all Evidence attach UX; sealed baseline remains independently Done; reopen requires observed pain and/or grounding-quality gap (retrieval-first), not schedule pressure.

---

## Manifest disposition (required when APPROVED)

N/A — Status is **DEFER**, not APPROVED. No closed-capability-manifest change.

- [ ] **UI over FR-07/M-09** (recommended) — unchecked; not selected under DEFER.
- [ ] **Named capability-manifest bullet** — unchecked; not selected under DEFER.

**PO selection:** N/A (DEFER)

---

## Reopen criteria

Resume only with a fresh **APPROVED** validation (or successor brief) when either:

1. **Observed pain** — members re-ask / copy excerpts / cannot pin a prior citation; or
2. **Grounding-quality gap** — same-domain retrieval repeatedly misses a passage already shown as Evidence, and retrieval/ranking fixes are evaluated before pin UX.

Domain change alone is not a reopen trigger for Evidence carry-forward.

---

## Sign-off

| Field | Value |
| --- | --- |
| Status | `DEFER` |
| Decided by | Product owner (session confirmation of brainstorm + plan scoping) |
| Date | `2026-07-28` |
| Outcome | `DEFER` |
| Tracker status | `DEFERRED` |
| Plan | `docs/plans/2026-07-28-001-feat-p11-04-evidence-attach-deferral-plan.md` |

When Status is **DEFER**, record deferral evidence only — no contract or UI suggestion work. Umbrella U2–U5 remain unstarted until reopen.
