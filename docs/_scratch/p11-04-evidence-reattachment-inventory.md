# P11-04 Evidence Reattachment Inventory

Date: 2026-07-28  
Status: **closed for DEFER** — no contract edits.  
Gate: `docs/_scratch/p11-04-evidence-reattachment-validation.md` Status is **DEFER**.  
Tracker: master-build-plan P11-04 → **`DEFERRED`**.  
Plan: `docs/plans/2026-07-28-001-feat-p11-04-evidence-attach-deferral-plan.md`.

Authority: `docs/master-build-plan.md` P11-04; `docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md` (U2–U5 blocked until reopen).

## Brownfield snapshot (unchanged under DEFER)

| Surface | Path | Disposition |
| --- | --- | --- |
| Chat shell composer | `app/client/src/features/chat-shell/ChatShell.tsx` | **retain** — no suggestion strip; References picker remains unavailable |
| Chat shell hook | `app/client/src/features/chat-shell/use-chat-shell.ts` | **retain** — may keep `composerRefTokens: []` |
| Chat shell API | `app/client/src/features/chat-shell/api.ts` | **retain** — no suggest / mint-on-accept client |
| Evidence inspector | `app/client/src/features/chat-shell/EvidencePanel.tsx` | **retain** — no auto-attach from inspector selection |
| Characterization gate | `app/client/tests/chat.test.mjs` | **retain** — pre-P11-04 gate remains valid |
| Composer-refs service | `app/context_engine/services/composer_refs.py` | **retain** — P11-01..03 Done; no suggestion projection |
| Discover HTTP | `POST /composer-refs:discover` | **brownfield evidence only** — not used as unconfirmed suggestion API |
| Turn-start consume / fingerprint | P11-02 / P11-03 | **retain** — dormant for Evidence attach until reopen |

## Gaps (remain until reopen APPROVED)

| Gap | Notes |
| --- | --- |
| No suggestion DTO / HTTP projection | Deferred with P11-04 |
| No compose-epoch / dismiss semantics | Deferred |
| No interaction-state / a11y rows for suggestion states | Deferred |
| Eager discover mint | Must not become unconfirmed suggestion API if/when reopened |
| Closed capability manifest | No change under DEFER |
| References picker disabled | Residual — Evidence attach unlock deferred pending reopen criteria |
| Domain-change invalid attached chips | Not shipping attach UX now |

## Amendment checklist (umbrella U2 — blocked until reopen APPROVED)

Do **not** check these off or edit the targets while validation Status is DEFER.

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
- [ ] `docs/prd.md` — only if a future APPROVED selects a non-expansive clarify or named-bullet path
- [ ] Ranking/cap pinned (citation/display order; cap 5; accept-order fingerprint) unless APPROVED overrides

## Explicit non-edits under DEFER

- No HTTP/DTO/frontend contract body changes for suggestions.
- No chat-shell unlock of suggestions or References picker.
- Source/template attach residual timing unchanged by this slice.

## Next step

1. ~~Product owner DEFER decision~~ — done in validation.
2. Publish deferral evidence + set tracker **`DEFERRED`** (plan U2/U3).
3. Stop. Reopen only on observed pain or grounding-quality gap per validation.
