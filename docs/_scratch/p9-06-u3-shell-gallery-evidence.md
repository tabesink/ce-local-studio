# P9-06 U3 — Shell composition parity evidence

Date: 2026-07-28  
Scope: U3 parity trios for `app-shell`, `navigation-rail`, and `pane-header`. No production migration in this slice.

## Summary

| targetId | Physical owner | Import path (parity tests) | Layer | catalogState |
| --- | --- | --- | --- | --- |
| `app-shell` | `app/client/src/features/shell/AppShell.tsx` | `@/features/shell/AppShell` | shared | FACTORY_READY |
| `navigation-rail` | `app/client/src/features/navigation-sidebar/NavigationSidebar.tsx` | `@/features/navigation-sidebar/NavigationSidebar` | shared | FACTORY_READY |
| `pane-header` | `app/client/src/_shared/ui/index.tsx` (`PageHeader`) | `@/_shared/ui` | shared | FACTORY_READY |

## Composition notes

- **AppShell** accepts `{ children: ReactNode }` only and composes `NavigationSidebar` + `<main>` primary canvas. Optional right inspector remains route-owned (chat/documents); HTML fixture shows dashed third region for geometry steering only.
- **NavigationRail** is prop-less; behavior comes from `useNavigationSidebar`, Next router/pathname, auth role filtering, and conversation search API. HTML uses synthetic labels Chat / Documents / Settings; live registry exposes Chat / Library / Graph / Settings.
- **Pane header** has no dedicated `PaneHeader` export. `PageHeader` in `@/_shared/ui` satisfies the compact title + actions row used inside the app-shell main region (Documents, Graph, Settings surfaces).

## Parity trio paths

| targetId | manifest | fixture | react test |
| --- | --- | --- | --- |
| `app-shell` | `app/client/tests/parity/manifests/app-shell.json` | `app/client/tests/parity/fixtures/app-shell.html` | `app/client/tests/parity/react/app-shell.test.tsx` |
| `navigation-rail` | `app/client/tests/parity/manifests/navigation-rail.json` | `app/client/tests/parity/fixtures/navigation-rail.html` | `app/client/tests/parity/react/navigation-rail.test.tsx` |
| `pane-header` | `app/client/tests/parity/manifests/pane-header.json` | `app/client/tests/parity/fixtures/pane-header.html` | `app/client/tests/parity/react/pane-header.test.tsx` |

## React stubbing approach

| target | stubs |
| --- | --- |
| `app-shell` | `next/navigation` (`useRouter`, `usePathname`), `next/link` → anchor, `useAuthStore` member user + noop logout, `listConversations` → `[]`, `localStorage.clear()` per test |
| `navigation-rail` | Same shell stubs; real `NavigationSidebar` with collapse/expand and mobile drawer exercised via Testing Library + user-event |
| `pane-header` | No network or router stubs; real `PageHeader` with synthetic eyebrow/title and stub action buttons |

## Blockers / deferrals

- Live **AppShell** wires two regions (rail + main) only; inspector parity is deferred to U4 (`evidence-inspector`) and route composites.
- **NavigationRail** conversation search overlay (`listConversations`) is not opened in U3 parity tests; keyboard ⌘K behavior remains covered by feature tests elsewhere.
- `ui-parity-spec.md` catalog rows remain `NOT_STARTED` until U6 index/enforcement closure (per task instruction: do not edit spec in this slice).

## Verification

Run from `app/client`:

```bash
npm test -- tests/parity/react/app-shell.test.tsx tests/parity/react/navigation-rail.test.tsx tests/parity/react/pane-header.test.tsx
```
