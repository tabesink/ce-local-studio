# P11-04 Evidence Reattachment Inventory

Date: 2026-07-28  
Status: **U1 readiness inventory only** — no contract edits in this unit.  
Gate: `docs/_scratch/p11-04-evidence-reattachment-validation.md` must be **APPROVED** before any amendment checklist item is executed.

Authority: `docs/master-build-plan.md` P11-04; `docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md`.

## Brownfield snapshot (today)

| Surface | Path | Disposition |
| --- | --- | --- |
| Chat shell composer | `app/client/src/features/chat-shell/ChatShell.tsx` | **modify after APPROVED** — suggestion strip + minimal attached/invalid chips; keep References picker unavailable (KTD5) |
| Chat shell hook | `app/client/src/features/chat-shell/use-chat-shell.ts` | **modify after APPROVED** — compose-epoch, dismiss set, ordered accepted tokens on submit (today hard-codes `composerRefTokens: []`) |
| Chat shell API | `app/client/src/features/chat-shell/api.ts` | **modify after APPROVED** — wire contracted suggest / mint-on-accept; do not call eager discover for unconfirmed browse |
| Evidence inspector | `app/client/src/features/chat-shell/EvidencePanel.tsx` | **retain** — no auto-attach from inspector selection |
| Characterization gate | `app/client/tests/chat.test.mjs` | **modify after APPROVED** — only for contracted suggestion/chip surfaces; picker stays unavailable |
| Composer-refs service | `app/context_engine/services/composer_refs.py` | **modify after APPROVED** — tokenless suggest + mint-on-accept; keep turn-start consume/fingerprint |
| Discover HTTP | `POST /composer-refs:discover` | **brownfield evidence only** — eager mint unsafe for unconfirmed suggestions (KTD3) |
| Turn-start consume / fingerprint | P11-02 / P11-03 | **retain** — accepted minted tokens enter existing M-09 path |

## Gaps (must be contracted before UI)

| Gap | Notes |
| --- | --- |
| No suggestion DTO / HTTP projection | Need tokenless list + mint-on-accept (or equivalent) |
| No compose-epoch / dismiss semantics | R12 — tab memory only |
| No interaction-state / a11y rows for suggestion states | R13 prerequisite |
| Eager discover mint | Must not be the unconfirmed suggestion API |
| Closed capability manifest | Suggestions not named; APPROVED must record KTD2 disposition |
| References picker disabled | Residual — not P11-04 DoD under KTD5 |
| Domain-change invalid attached chips | Specified in umbrella F2/R8; zero UI today |

## Amendment checklist (U2 — blocked until APPROVED)

Do **not** check these off or edit the targets until validation Status is APPROVED.

- [ ] `docs/contracts/http-api-catalog.md` — suggestion projection + mint-on-accept (or equivalent)
- [ ] `docs/contracts/dto-schema-catalog.md` — suggestion / accept DTOs; no private ids
- [ ] `docs/frontend/chat-and-evidence-workbench.md` — suggest/accept/dismiss + invalid chips
- [ ] `docs/frontend/frontend-state-ownership.md` — compose-epoch dismiss set; no storage; no cross-tab sync
- [ ] `docs/frontend/interaction-state-catalog.md` — suggested/attached/invalid/loading/empty/stale/failure/accepted/dismissed
- [ ] `docs/frontend/component-contracts.md` — suggestion / chip composition roles
- [ ] `docs/frontend/accessibility-contract.md` — focus/touch/announce/recovery/320px for R13 states
- [ ] `docs/frontend/content-and-microcopy.md` — R13 labels (contracted, not ad-hoc)
- [ ] `docs/frontend/responsive-and-desktop-matrix.md` — if narrow suggestion surface needs an explicit row
- [ ] `docs/interaction-behavior-prd.md` — suggest/dismiss/epoch case without redefining M-09 consume
- [ ] `docs/prd.md` — only if APPROVED selects a non-expansive clarify or named-bullet path (KTD2)
- [ ] Ranking/cap pinned (KTD10 defaults: citation/display order; cap 5; accept-order fingerprint) unless APPROVED overrides

## Explicit non-edits in U1

- No HTTP/DTO/frontend contract body changes in this unit.
- No chat-shell unlock of suggestions or References picker.
- `docs/master-build-plan.md` P11-04 remains **BLOCKED** until U6 closure evidence.

## Next step

1. Product owner completes the three axes + sign-off in `docs/_scratch/p11-04-evidence-reattachment-validation.md`.
2. If **APPROVED** → execute U2 checklist above, then U3–U6 per the plan.
3. If **FAILED/DEFER** → U6 deferral evidence only; leave checklist unchecked.
