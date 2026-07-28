# P9-06 U1 — Authority and catalog schema evidence

Date: 2026-07-28  
Plan: `docs/plans/2026-07-28-002-feat-full-workstation-html-gallery-plan.md`  
Branch: `feat/p9-06-full-workstation-html-gallery`

## Delivered

- Option A normative in `docs/frontend/ui-parity-spec.md` (full Phase 1 register + compose-from-HTML rule).
- `docs/frontend/AGENTS.md`, `DESIGN.md`, `docs/frontend/visual-regression-plan.md` updated for catalog-first HTML steering.
- Tracker row `P9-06` added to `docs/master-build-plan.md` (`NOT_STARTED` until U2–U6 close).
- Brownfield foundation row for full workstation HTML gallery.
- Factory plan supersession note for gallery scope (chat/documents/shell included; graph canvas still blocked).
- Starter manifests backfilled with additive `layer` (`primitive` / `feature`).
- `app/client/tests/frontend-uiux-factory.test.mjs` asserts Option A wording, P9-06, layer backfill.

## Verification

```bash
cd app/client && node --experimental-strip-types --test tests/frontend-uiux-factory.test.mjs
```

Result: 5/5 pass (2026-07-28).

## Residuals

- U2–U6: kit/shell/chat/documents/residuals + index + hard CI mapping.
- P9-06 tracker remains `NOT_STARTED` until closure evidence.
