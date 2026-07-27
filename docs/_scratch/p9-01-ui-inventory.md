# P9-01 UI Ownership Inventory

Date: 2026-07-27  
Status: complete for P9-01 U1 inventory only; no migration mutations in this record. Execution evidence for later units, not a release completion record.

Authority for this inventory: `docs/master-build-plan.md` P9-01; `docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md` (KTD2–KTD5, KTD8–KTD9); `docs/frontend/component-contracts.md`; `docs/frontend/ui-parity-spec.md` (D0 catalog owner — path strings amended in U1); `DESIGN.md`; `docs/frontend/AGENTS.md`.

Session decision (U1): **KEEP LIVE `_shared` Button/Input/StatusPill API** as the `src/ui` canonical surface, with the approved divergence table below. Do not rename props/tones in this slice.

## Observed competing trees

| Tree | Physical location | Role today | Target after P9-01 |
| --- | --- | --- | --- |
| Thin / dual-body kit | `app/client/src/components/ui/**` (13 files) | Mixed: barrel re-exports `_shared`; CE-only surfaces; orphaned dual bodies; login deep-imports divergent Button/Input | Migrated symbols → alias-only; CE-only retained/reverified; orphaned dual bodies deleted |
| Mega-kit | `app/client/src/_shared/ui/index.tsx` (1 file) | Live SoT for most Settings/Documents/Chat primitives via barrel or direct import | Extract Button/Input/StatusPill → `src/ui`; SettingsRow → settings feature; residual sole-home until FE-01 |
| Layout | `app/client/src/components/layout/**` (2 files) | `AppShell` (rail+main) + `AppLayout` (auth gate) | `AppShell` → `src/features/shell`; `AppLayout` stays auth-truth owner |
| Canonical home | `app/client/src/ui/**` | **Absent** | Create for product-neutral primitives |
| Shell feature | `app/client/src/features/shell/**` | **Absent** | Create for AppShell ownership |
| Parity scaffolding | `app/client/tests/structure/**`, `parity/**` | **Absent** (`e2e/` already exists) | Land per path-authority decision below |

## Path-authority decision

Master-build-plan P9-01 paths win. Same-slice amend of `docs/frontend/ui-parity-spec.md` output bullets (KTD2):

| Artifact | Canonical path |
| --- | --- |
| Structural ownership gate | `app/client/tests/structure/ui-ownership.test.ts` |
| Parity manifests | `app/client/tests/parity/manifests/<target>.json` |
| HTML-static fixtures | `app/client/tests/parity/fixtures/<target>.html` |
| React/RTL parity | `app/client/tests/parity/react/<target>.test.tsx` |
| Browser E2E scaffolding | `app/client/tests/e2e/` (domains production-boundary acceptance remains P12-07; implementation P9-04) |

Starter-target `FACTORY_READY` is earned by shared + HTML-static + React (Vitest/RTL) + applicable R10 assertions (KTD9). Playwright route/visual matrix stays P12-07.

## Dual-body note (Button / Input / StatusPill)

Barrel `@/components/ui` currently does `export * from "@/_shared/ui"`, so barrel consumers get the live `_shared` API. Login bypasses the barrel and deep-imports thin files:

| Symbol | Live body (canonical for P9-01) | Thin competing body | Deep-import call sites |
| --- | --- | --- | --- |
| Button | `_shared/ui` (`size`, `icon`, `loading`, `className` via HTML attrs) | `components/ui/Button.tsx` (no `size`/`icon`; fixed `h-7`) | `app/login/page.tsx` |
| Input | `_shared/ui` (`label?`, `error?`, `icon?`, forwardRef) | `components/ui/Input.tsx` (**required** `label`, no `error`/`icon`/ref) | `app/login/page.tsx` |
| StatusPill | `_shared/ui` (`tone`, `variant` dot\|badge, `className`) | `components/ui/StatusPill.tsx` (same public shape; token-syntax drift) | **none** (orphaned dual body) |

### Approved divergence table vs `component-contracts.md`

Keep live prop/tone names; map contract vocabulary in parity docs/tests only:

| Contract (`component-contracts.md`) | Live `_shared` / `src/ui` API | Notes |
| --- | --- | --- |
| Button variants primary/secondary/danger/ghost/icon | same | Keep |
| Button sizes sm/md/lg | `size?: "sm" \| "md" \| "lg"` (default `md`) | Thin copy lacks `size` — delete thin |
| Button loading + label retention | `loading?: boolean` | Live spinner replaces `icon` when loading; add `aria-busy` in migrate/reverify if missing |
| Input label / help / error / required / disabled | `label?`, `error?`; native `required`/`disabled`; **no dedicated `help` prop** | Approved gap: help remains composition (nearby copy), not a prop rename |
| Input label required? | Contract implies labeled inputs; live `label` **optional** | Keep optional; login continues passing `label` |
| StatusPill tones: neutral, info, success, warning, danger | Live: `default`, `info`, `good`, `warning`, `danger` | Mapping: `default`↔neutral, `good`↔success; **do not rename `tone` values in-slice** |
| StatusPill never color-only | Live pairs dot/text or badge text | Keep |

## Shell vs chat-shell note

| Surface | Path | Owns | Must not own |
| --- | --- | --- | --- |
| AppShell | `components/layout/AppShell.tsx` → migrate to `features/shell` | Discovery rail (`NavigationSidebar` = NavigationRail role), main slot | Auth truth, chat transcript/composer |
| AppLayout | `components/layout/AppLayout.tsx` | Session resolve/redirect for non-public routes | Product shell chrome |
| ChatShell | `features/chat-shell/ChatShell.tsx` | Conversation workbench inside main | Global rail / route shell |

`/chat` composes `<AppShell><ChatShell /></AppShell>`. Do not merge chat-shell into AppShell.

## Accordion hard stop (BLOCKED_CONTRACT / blocked-P9-04)

- Catalog target **Settings Domain accordion** remains `BLOCKED_CONTRACT`.
- Live Settings Domains section uses hand-rolled expand/collapse; not a kit export.
- **P9-01 must not** invent accordion parity manifests, fixtures, React tests, or `FACTORY_READY` claims.
- Disposition: `blocked-P9-04`. Implementation stays P9-04; production-boundary F3 acceptance stays P12-07.

## Import call-site matrix

### From `@/components/ui` (barrel)

| Call site | Symbols |
| --- | --- |
| `app/client/src/features/settings-panel/SettingsPanel.tsx` | `cx`, `EmptySafeNotice`, `IconButton`, `Input`, `ProgressBar`, `Select`, `SettingsButton`, `SettingsFactRows`, `SettingsGroup`, `SettingsInput`, `SettingsLayout`, `SettingsNotice`, `SettingsRow`, `StatusPill`, `ToggleSwitch`, `UiModal`, `UiModalHeader`, `SettingsSectionDef` |

### From `@/components/ui/...` (deep)

| Call site | Specifier | Symbols |
| --- | --- | --- |
| `app/client/src/app/login/page.tsx` | `@/components/ui/AppLogo` | `AppLogo` |
| `app/client/src/app/login/page.tsx` | `@/components/ui/Button` | `Button` (**thin body**) |
| `app/client/src/app/login/page.tsx` | `@/components/ui/ErrorBox` | `ErrorBox` |
| `app/client/src/app/login/page.tsx` | `@/components/ui/Input` | `Input` (**thin body**) |
| `app/client/src/app/forbidden/page.tsx` | `@/components/ui/PageState` | `PageState` |
| `app/client/src/components/layout/AppLayout.tsx` | `@/components/ui/PageState` | `PageState` |
| `app/client/src/features/documents/DocumentsPage.tsx` | `@/components/ui/PageState` | `PageState` |
| `app/client/src/features/navigation-sidebar/NavigationSidebar.tsx` | `@/components/ui/AppLogo` | `AppLogo` |
| `app/client/src/components/ui/SettingsLayout.tsx` | `@/components/ui/PageHeader`, `@/components/ui/ListGroup` | intra-thin only |
| `app/client/src/components/ui/index.ts` | `@/components/ui/{AppLogo,ErrorBox,PageState}` | re-exports |

### From `@/_shared/ui`

| Call site | Allowlist note |
| --- | --- |
| `app/client/src/components/ui/index.ts` | barrel SoT bridge |
| `app/client/src/components/ui/AppLogo.tsx` | CE-only helper (`cx`) |
| `app/client/src/features/chat-shell/ChatShell.tsx` | allowlisted |
| `app/client/src/features/chat-shell/EvidencePanel.tsx` | allowlisted |
| `app/client/src/features/documents/DocumentsPage.tsx` | allowlisted |
| `app/client/src/features/documents/PdfPreview.tsx` | allowlisted |
| `app/client/src/features/graph/GraphPage.tsx` | allowlisted |
| `app/client/src/features/navigation-sidebar/NavigationSidebar.tsx` | allowlisted |
| `app/client/src/features/user-preferences/PreferencesPanel.tsx` | allowlisted |

Frozen allowlist lives in `app/client/tests/design-kit-contract.test.mjs`. P9-01 rewrite must shrink monotonically (KTD7).

### From `@/components/layout/...`

| Call site | Specifier |
| --- | --- |
| `app/client/src/app/providers.tsx` | `@/components/layout/AppLayout` |
| `app/client/src/app/chat/page.tsx` | `@/components/layout/AppShell` |
| `app/client/src/app/documents/page.tsx` | `@/components/layout/AppShell` |
| `app/client/src/app/database-visualize/page.tsx` | `@/components/layout/AppShell` |
| `app/client/src/app/settings/page.tsx` | `@/components/layout/AppShell` |
| `app/client/src/app/forbidden/page.tsx` | `@/components/layout/AppShell` |

## Per-file disposition table

### `app/client/src/components/ui/**`

| Path | Exports of interest | Disposition | Brief reason |
| --- | --- | --- | --- |
| `app/client/src/components/ui/index.ts` | Re-exports `_shared` + CE-only | alias-only (after migrate) | Temporary legacy barrel; no competing bodies for migrated symbols |
| `app/client/src/components/ui/Button.tsx` | `Button` | delete | Divergent thin body; login-only deep import |
| `app/client/src/components/ui/Input.tsx` | `Input` | delete | Divergent thin body; login-only |
| `app/client/src/components/ui/StatusPill.tsx` | `StatusPill`, `StatusDot`, tones | delete | Orphaned dual body |
| `app/client/src/components/ui/SettingsLayout.tsx` | `SettingsLayout`, `SettingsGroup`, `SettingsRow`, … | delete | Orphaned dual body; SettingsRow moves to feature |
| `app/client/src/components/ui/ListGroup.tsx` | `ListGroup`, `ListRow`, `RowValue`, `EmptySafeNotice` | delete | Orphaned; only thin SettingsLayout |
| `app/client/src/components/ui/PageHeader.tsx` | `PageHeader` | delete | Orphaned dual body |
| `app/client/src/components/ui/SearchInput.tsx` | `SearchInput` | delete | Orphaned dual body |
| `app/client/src/components/ui/SegmentedControl.tsx` | `SegmentedControl` | delete | Orphaned dual body |
| `app/client/src/components/ui/Table.tsx` | `Table`, table cells | delete | Orphaned dual body |
| `app/client/src/components/ui/AppLogo.tsx` | `AppLogo` | retain-and-reverify | CE-only; not starter parity |
| `app/client/src/components/ui/ErrorBox.tsx` | `ErrorBox` | retain-and-reverify | CE-only; not starter parity |
| `app/client/src/components/ui/PageState.tsx` | `PageState` | retain-and-reverify | CE-only; not starter parity |

### `app/client/src/components/layout/**`

| Path | Exports of interest | Disposition | Brief reason |
| --- | --- | --- | --- |
| `app/client/src/components/layout/AppShell.tsx` | `AppShell` | migrate | → `src/features/shell`; then alias-only |
| `app/client/src/components/layout/AppLayout.tsx` | `AppLayout` | retain-and-reverify | Auth gate; must not merge into AppShell |

### `app/client/src/_shared/ui/**`

| Path | Exports of interest | Disposition | Brief reason |
| --- | --- | --- | --- |
| `app/client/src/_shared/ui/index.tsx` | Starter: `Button`, `Input`, `StatusPill`, `SettingsRow` (+ types). Residual mega-kit: Table, Modal, Drawer, Model*, Select, … | migrate (extract starters) + alias-only for those symbols + defer-FE-01 for residual sole homes | KTD3/KTD4/KTD5 |

### Virtual / missing targets

| Path | Disposition | Brief reason |
| --- | --- | --- |
| `app/client/src/ui/*` (absent) | migrate (create) | Canonical product-neutral home |
| SettingsRow under `features/settings-panel` | migrate | Catalog owner; Preferences consumes Settings export |
| `app/client/src/features/shell` (absent) | migrate (create) | Shell ownership |
| Settings Domain accordion (no dedicated file) | blocked-P9-04 | No parity artifacts in P9-01 |

## Starter-target disposition summary

| Target | Catalog owner | Inventory disposition | Notes |
| --- | --- | --- | --- |
| Button | `src/ui` | migrate + retain-and-reverify live API | Delete thin; retarget login |
| Input | `src/ui` | migrate + retain-and-reverify live API | Delete thin; retarget login |
| StatusPill | `src/ui` | migrate + retain-and-reverify live tones | Delete orphaned thin; divergence table |
| SettingsRow | `src/features/settings-panel` | migrate | Move ownership under Settings |
| Settings Domain accordion | `src/features/settings-panel` | blocked-P9-04 | No invent / no parity files |

## Characterization baselines for U2 (before deleting thins)

| Control | Expected before/after unify |
| --- | --- |
| Button loading | `loading` disables repeat activation; label retained; expose `aria-busy` if missing on live body |
| Button disabled | native `disabled` |
| Input | `label` when provided; `error` message association; `disabled` |
| StatusPill | never color-only; live tones `default`/`info`/`good`/`warning`/`danger` |

## P9-01 boundary (this inventory)

This unit records file/call-site dispositions and path authority only. It does **not**:

- create `src/ui`, `features/shell`, structure/parity fixtures, or aliases (U2+);
- approve accordion interaction grammar (P9-04);
- claim live `/settings?section=domains` acceptance (P12-07);
- demolish the full FE-01 mega-kit catalog.

Evidence before mutation:

- `src/ui` and `features/shell` directories do not exist.
- `app/client/tests/structure/` and `app/client/tests/parity/` do not exist; `app/client/tests/e2e/` does.
- Design-kit contract still requires barrel `export * from "@/_shared/ui"` and freezes nine `_shared` importers.
- Login is the only production deep-import of divergent Button/Input bodies.
