# Shared UI kits

Cross-feature reusable UI contracts. Prefer these over page-local chrome.
Kit status must stay honest with [`DESIGN.md`](../../../DESIGN.md) §11 (live barrel vs **not in kit yet**).

| Kit | Status | Doc |
|---|---|---|
| Accordion / storage | **Not exported yet** — document + cite only | [`accordion-storage-kit.md`](./accordion-storage-kit.md) |

## Kit status (aligned with DESIGN.md §11)

| Pattern | In `@/components/ui`? | What to do |
|---|---|---|
| `SettingsLayout` / `SettingsGroup` / `SettingsRow` / `SettingsFactRows` / `SettingsNotice` | Yes | Import from barrel |
| `ProgressBar`, `StatusPill`, `ToggleSwitch`, `IconButton`, `UiModal` | Yes | Import from barrel |
| Controllers-style accordion / expandable list rows + storage bars | **No — not in kit yet** | Cite + adapt `.reference-ls-frontend/templates/nextjs-feature-demos/features/environment-controls/`; follow [`accordion-storage-kit.md`](./accordion-storage-kit.md) |

## Rule

Shared kits are composition contracts under Local Studio tokens.
They compose `@/components/ui` primitives (and named template cites for gaps).
They do not invent a parallel token system or claim exports that do not exist.
