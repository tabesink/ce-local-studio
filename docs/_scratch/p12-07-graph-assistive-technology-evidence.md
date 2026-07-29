# P12-07 U6 — Graph assistive-technology evidence

Date: 2026-07-29  
Plan unit: U6 / AE13  
Automated axe/keyboard: `app/client/tests/e2e/a11y-golden-routes.spec.ts` (`@pr-fast`)  
**Status: NO-GO — operator AT pass not executed in this slice**

Automated axe + keyboard list/detail equivalence do **not** substitute for this record.

## Environment (fill on execution)

| Field | NVDA + Chrome (Windows) | VoiceOver + Safari (macOS) |
| --- | --- | --- |
| OS version | _pending_ | _pending_ |
| Screen reader + version | _pending_ | _pending_ |
| Browser + version | _pending_ | _pending_ |
| Product git revision | _pending_ | _pending_ |
| Operator | _pending_ | _pending_ |
| Fixture revision | fixtures-v1 | fixtures-v1 |

## Task script (same on both stacks)

1. Sign in as Mina; land on `/chat`.
2. Open Graph (`/database-visualize`); confirm eligible domain selected or select seeded domain.
3. Confirm polite status / accessible summary announces graph load without raw hits/paths.
4. Move focus into node search; type a no-match string; confirm empty/no-match is announced or visible to AT; clear.
5. Search `relief`; move to Relief valve control; activate; confirm detail region and selection state (`aria-current` / summary) without color-only dependence.
6. Narrow viewport / open nodes drawer; trap focus; Escape closes; focus returns to opener.
7. Trigger refresh; busy name retained; no focus steal to canvas (`aria-hidden` presentation).
8. Open unknown/missing domain; safe error + request ID; recover by selecting a valid domain.
9. Note duplicate/missing live-region announcements.

## Results

| Step | NVDA+Chrome | VoiceOver+Safari | Notes |
| --- | --- | --- | --- |
| 1–9 | NOT RUN | NOT RUN | Residual blocks AE13 AT half of P12-07 close |

## Residuals

- Dual screen-reader pass outstanding — do not claim AE13 complete.
- Visual PNG baselines remain `capture_required` in `visual-parity-manifest.json` until capture + review (`verify_visual_parity_manifest.py enforce`).
