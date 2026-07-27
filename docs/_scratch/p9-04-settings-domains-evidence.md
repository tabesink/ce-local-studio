# P9-04 Settings Domain Accordion Evidence

Date: 2026-07-27

Slice: P9-04

Status: DONE (Vitest/RTL + focused node altitude; production-boundary Playwright F3 deferred to P12-07)

Plan: `docs/plans/2026-07-27-011-feat-settings-domain-accordion-plan.md`

Inventory: `docs/_scratch/p9-04-settings-domains-inventory.md`

Authority: FR-03 / FR-10; A-03 / A-05 / A-10; closed `AdminDomainDto` / `OperationDto`;
`docs/frontend/{AGENTS,ui-parity-spec,component-contracts,interaction-state-catalog,accessibility-contract,route-and-workspace-spec,navigation-and-url-state,content-and-microcopy}.md`;
DRIFT-04; P9-01 factory ownership.

## What landed

- U1: Settings Domain accordion interaction amendment across component / interaction-state /
  accessibility / route / nav / microcopy / parity catalog; catalog left `BLOCKED_CONTRACT`
  → `IN_PROGRESS`.
- U2: `features/domains/api.ts` aligned to generated closed DTOs; start/stop → `{operation}`;
  delete + `If-Match`; no `available` / `storageSummary`; member call sites use `queryEligible`.
- U3: `/settings?section=` allowlist sync (`general|provider|domains|users`); Knowledge Domains
  accordion with locked-fact expand body; start_failed_keep microcopy; no storage ProgressBar.
- U4: Settings-owned `DomainAccordionRow` + `domains-accordion` parity trio; structural forbid
  gates flipped; catalog → `FACTORY_READY` at Vitest/RTL altitude.
- U5: shell-safe `app/not-found.tsx`; deferred Phase 2/3 routes remain absent; graph no-request
  reconfirmed; DRIFT-04 → DONE.

## Commands

### Typecheck

```text
cd app/client
npm run typecheck
```

Result (2026-07-27): clean.

### Focused node tests

```text
cd app/client
node --experimental-strip-types --test \
  tests/domains-settings.test.mjs \
  tests/domains-api.test.mjs \
  tests/not-found-nav.test.mjs \
  tests/graph-unavailable.test.mjs \
  tests/frontend-uiux-factory.test.mjs \
  tests/design-kit-contract.test.mjs \
  tests/structure/ui-ownership.test.ts
```

Result: 32/32 passed.

### Parity Vitest

```text
cd app/client
npx vitest run \
  tests/parity/react/domains-accordion.test.tsx \
  tests/parity/react/button.test.tsx \
  tests/parity/react/settings-row.test.tsx
```

Result: 12/12 passed (3 files).

## Privacy / contract checks

- Domains Settings UI, accordion parity fixtures, and not-found copy omit runtime URLs,
  ports, container ids, storage paths, credentials, stack traces, and `storageSummary`.
- Expand body limited to nested embedding profile name/dims, state, `queryEligible`,
  `runtimeReady`, `controlGeneration`, `version`.
- No shared `src/ui/Accordion` primitive.

## Residuals (explicit)

| Residual | Owner |
| --- | --- |
| Production Next/BFF/FastAPI Playwright F3 + full visual matrix for `/settings?section=domains` | P12-07 |
| Broader import-direction / thin-route / barrel CI validators | P9-05 |
| Shared Accordion / StorageBar barrel exports | needs second consumer + contract change |
| Public `storageSummary` / ProgressBar-on-expand | out of scope (not reopened) |
| Phase 2 ops/logs/usage / Phase 3 wiki UI | deferred |

## Tracker dispositions

- `docs/master-build-plan.md` P9-04 → DONE
- `docs/brownfield-refactor-register.md` DRIFT-04 → DONE
- `docs/frontend/ui-parity-spec.md` Settings Domain accordion → `FACTORY_READY`
