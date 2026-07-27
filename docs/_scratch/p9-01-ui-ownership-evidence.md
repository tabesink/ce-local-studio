# P9-01 UI Ownership Evidence

Date: 2026-07-27

Slice: P9-01

Status: DONE (four starter targets factory-ready; accordion and live Settings deferred)

Plan: `docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md`

Inventory: `docs/_scratch/p9-01-ui-inventory.md`

## What landed

- Inventory froze competing `components/ui` / `_shared/ui` call sites, KEEP LIVE Button/Input/StatusPill APIs with approved tone/prop divergence vs `component-contracts.md`, and accordion hard-stop (`BLOCKED_CONTRACT` / P9-04).
- Canonical homes: `src/ui` Button/Input/StatusPill; `features/settings-panel` SettingsRow; `features/shell` AppShell. Login and StatusPill consumers resolve to one physical body.
- Legacy `@/components/ui` barrel and `@/_shared/ui` are alias-only for migrated symbols; residual mega-kit bodies remain sole homes until FE-01 (`defer-FE-01`).
- Structural gate: `app/client/tests/structure/ui-ownership.test.ts` + rewritten `design-kit-contract.test.mjs`.
- Parity: versioned manifests, script-free HTML fixtures, and Vitest/RTL React suites for button, input, status-pill, settings-row under `app/client/tests/parity/`.
- Catalog: four unblocked targets `FACTORY_READY`; Settings Domain accordion remains `BLOCKED_CONTRACT`.

## Commands

### Ownership / design-kit / foundation (node:test)

```text
cd app/client
node --experimental-strip-types --test `
  tests/design-kit-contract.test.mjs `
  tests/structure/**/*.test.ts `
  tests/frontend-uiux-factory.test.mjs `
  tests/foundation.test.mjs
```

Result: all suites passed (Windows path normalization applied to foundation route-map assert).

### Parity React (Vitest + Testing Library)

```text
cd app/client
npm run test:parity
npm run typecheck
```

Result: 4 files / 17 tests passed; typecheck passed.

### Composite note

`npm test` is wired as node:test (`tests/*.mjs` + structure) then `vitest run`. Pre-existing `tests/stream-protocol.test.mjs` failures (5 subtests; chat SSE reducer residual owned by P9-02) still fail the node half before Vitest when run as a single `&&` composite. P9-01 acceptance cites the ownership + parity commands above, not full chat stream-protocol green.

## Residuals / non-claims

- Settings Domain accordion interaction contract, manifests, fixtures, React tests, and `/settings?section=domains` implementation → **P9-04**.
- Production-boundary F3/R12/AE1 Settings domains acceptance and Playwright visual-matrix baseline comparison → **P12-07** (DRIFT-07 remains IN_PROGRESS for that half).
- Full FE-01 mega-kit demolition / residual `_shared` sole homes (Table, Modal, Drawer, Select, SettingsLayout, …) → **defer-FE-01**.
- Broader import-direction CI validators → **P9-05**.
- DRIFT-02 EvidencePanel keyboard/focus → **not closed** (P9-02).
- Live StatusPill tones remain `default` / `good` (mapped to contract `neutral` / `success` in parity docs only).

## Artifact revision

Branch: `feat/p9-01-ui-ownership`

Commits (slice): inventory → `src/ui` promote → SettingsRow/AppShell → structural gate → Vitest parity → this evidence/tracker closure.
