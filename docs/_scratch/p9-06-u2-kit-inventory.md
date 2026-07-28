# P9-06 U2 — Kit parity inventory (five in-use targets)

Date: 2026-07-28  
Scope: U2 parity trios for Select, ToggleSwitch, UiModal, PageState, ErrorBox. No migration in this slice.

## Summary

| targetId | Physical owner | Import path (parity tests) | Layer | In-use call sites |
| --- | --- | --- | --- | --- |
| `select` | `app/client/src/_shared/ui/index.tsx` | `@/_shared/ui` | primitive | SettingsPanel, PreferencesPanel |
| `toggle-switch` | `app/client/src/_shared/ui/index.tsx` | `@/_shared/ui` | primitive | SettingsPanel (domain lifecycle), DomainAccordionRow slot |
| `ui-modal` | `app/client/src/_shared/ui/index.tsx` | `@/_shared/ui` | shared | SettingsPanel (delete Knowledge Domain) |
| `page-state` | `app/client/src/components/ui/PageState.tsx` | `@/components/ui/PageState` | shared | AppLayout, SettingsPanel, DocumentsPage, not-found, forbidden |
| `error-box` | `app/client/src/components/ui/ErrorBox.tsx` | `@/components/ui/ErrorBox` | primitive | LoginPage |

Production imports today mostly use `@/components/ui` barrel re-exports for `_shared` symbols. Parity React tests import `@/_shared/ui` for Select/ToggleSwitch/UiModal per U2 steering.

## Call-site notes

### Select

- `app/client/src/features/settings-panel/SettingsPanel.tsx` — embedding model picker in Knowledge Domain deploy row (`aria-label="Embedding model"`, compact `h-7`).
- `app/client/src/features/user-preferences/PreferencesPanel.tsx` — font family row inside Typography settings group.

### ToggleSwitch

- `app/client/src/features/settings-panel/SettingsPanel.tsx` — domain lifecycle start/stop in each DomainAccordionRow (`aria-label` reflects Start/Stop + display name).
- `app/client/tests/parity/react/domains-accordion.test.tsx` — composition harness imports via `@/components/ui` barrel.

### UiModal / UiModalHeader

- `app/client/src/features/settings-panel/SettingsPanel.tsx` — delete Knowledge Domain confirmation (`max-w-md`, synthetic title "Delete Knowledge Domain" in product; parity uses "Confirm action").

### PageState

- `app/client/src/components/layout/AppLayout.tsx` — session resolve loading gate.
- `app/client/src/features/settings-panel/SettingsPanel.tsx` — Suspense fallback while settings load.
- `app/client/src/features/documents/DocumentsPage.tsx` — library Suspense + signed-out empty state.
- `app/client/src/app/not-found.tsx` — safe not-found surface.
- `app/client/src/app/forbidden/page.tsx` — forbidden surface with `tone="danger"`.

### ErrorBox

- `app/client/src/features/auth/LoginPage.tsx` — auth failure message below sign-in form.

## Parity trio paths

| targetId | manifest | fixture | react test |
| --- | --- | --- | --- |
| `select` | `app/client/tests/parity/manifests/select.json` | `app/client/tests/parity/fixtures/select.html` | `app/client/tests/parity/react/select.test.tsx` |
| `toggle-switch` | `app/client/tests/parity/manifests/toggle-switch.json` | `app/client/tests/parity/fixtures/toggle-switch.html` | `app/client/tests/parity/react/toggle-switch.test.tsx` |
| `ui-modal` | `app/client/tests/parity/manifests/ui-modal.json` | `app/client/tests/parity/fixtures/ui-modal.html` | `app/client/tests/parity/react/ui-modal.test.tsx` |
| `page-state` | `app/client/tests/parity/manifests/page-state.json` | `app/client/tests/parity/fixtures/page-state.html` | `app/client/tests/parity/react/page-state.test.tsx` |
| `error-box` | `app/client/tests/parity/manifests/error-box.json` | `app/client/tests/parity/fixtures/error-box.html` | `app/client/tests/parity/react/error-box.test.tsx` |

## Import path notes

- `@/_shared/ui` resolves via `@/*` → `src/*` and is valid for parity tests and direct imports.
- Feature code continues to import Select/ToggleSwitch/UiModal from `@/components/ui` barrel (`export * from "@/_shared/ui"`). No import-path conflict; parity tests use the physical owner path explicitly.
- PageState and ErrorBox are CE-only modules under `src/components/ui`; barrel and deep imports both resolve.
