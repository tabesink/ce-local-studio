# P11-04 Evidence Reattachment — Deferral Evidence

Date: 2026-07-28  
Outcome: **DEFER** (validation) / tracker **`DEFERRED`**  
Plan: `docs/plans/2026-07-28-001-feat-p11-04-evidence-attach-deferral-plan.md`  
Validation: `docs/_scratch/p11-04-evidence-reattachment-validation.md`  
Inventory: `docs/_scratch/p11-04-evidence-reattachment-inventory.md`

## Decision summary

Product owner deferred Phase 1 Evidence suggest-and-confirm and deprioritized Evidence attach-chip unlock (References / inspector pin).
Members rely on per-turn domain RAG.
Sealed chat baseline and P11-01..03 server composer-ref capability remain Done.
Browser may keep empty `composerRefTokens` and References unavailable.

## AE mapping

| AE | Result |
| --- | --- |
| AE1 DEFER closes without UI | Met — Status DEFER; amendment checklist unchecked; no suggestion DTO/UI shipped |
| AE2 Reopen on observed pain | Named in validation reopen criteria; not executed |
| AE3 Reopen on grounding gap prefers retrieval first | Named in validation reopen criteria; not executed |
| AE4 Domain switch does not unlock carry-forward | Met — domain switch rejected as primary job; no carry-forward project started |

## No-ship proof

- Spot-check 2026-07-28: `docs/contracts/http-api-catalog.md` and `docs/contracts/dto-schema-catalog.md` contain no Evidence-suggestion endpoints/DTOs (`suggest` / `reattach` / `mint-on-accept` / `suggestionKey` absent).
- Umbrella plan U2–U5 not started; inventory amendment checklist remains unchecked.
- No chat-shell suggestion unlock in this slice.

## Baseline honesty

- P7 sealed SSE / grounded terminals and P9 Evidence/Refs/Source workbench remain independently Done.
- P11-01..03 discover/consume/fingerprint remain Done; DRIFT-26 closed.
- References picker unlock is **not** claimed Done.
- Source/template attach residual timing is **unchanged** by this slice.

## Reopen criteria

Resume only with a fresh APPROVED validation (or successor brief) when:

1. Observed member pain (re-ask / copy excerpts / cannot pin), or
2. Grounding-quality gap (same-domain miss of a prior-turn passage) with retrieval/ranking considered before pin UX.

## Residuals

| Residual | Owner |
| --- | --- |
| Evidence attach / References unlock / suggest-and-confirm | Deferred pending reopen (P11-04 `DEFERRED`) |
| Source/template attach unlock | Separate residual (unchanged) |
| P12 adversarial privacy / deployed-ingress / browser E2E | P12 |

## Verification boundary

Docs/tracker closure only. Root `release:validate` is **not** required for this slice.

## Tracker updates (U3)

- `docs/master-build-plan.md` P11-04 → `DEFERRED`; P11 phase wording notes P11-04 DEFERRED.
- `docs/brownfield-refactor-register.md` hashed-token row residual updated for deferred Evidence attach / References unlock.
- `docs/_scratch/p11-03-assembly-fingerprint-replay-evidence.md` residual pointer updated for honesty.
