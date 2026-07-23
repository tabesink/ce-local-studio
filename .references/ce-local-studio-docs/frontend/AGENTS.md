# Frontend UIUX — Agent Contract

## Before any UI change

1. Read [`theme.md`](./theme.md) and root [`DESIGN.md`](../../DESIGN.md).
2. Open the feature folder for the surface you are touching.
3. Prefer [`shared/`](./shared/) kits over one-off row/card chrome.
4. Import shared UI only from `@/components/ui` (live barrel inventory).

When guidelines conflict with `DESIGN.md`, **`DESIGN.md` wins** — then update the conflicting doc in the same change.

## Hard rules

- **`@/components/ui` first.** Compose barrel primitives (`Button`, `SettingsLayout`, `SettingsGroup`, `SettingsRow`, `ProgressBar`, `StatusPill`, `UiModal`, …). Do not invent parallel primitives or a second token system.
- **Tokens only.** Use Local Studio / appearance-runtime tokens (`--ui-*`, `--fs-*`, `--rad-*`). No hardcoded hex in chrome; no feature-local `data-theme` writes.
- **Local Studio parity.** Dense dark-first workstation: Geist / Geist Mono, 24/28px controls, quiet dividers. No generic white dashboard, purple gradients, or pill-everything.
- **Cite gaps honestly.** Patterns marked **not in kit yet** (Controllers-style accordion / expandable list rows + storage bars) must cite the named Local Studio template — do not invent a parallel component API.
  - Required cite for Controllers accordion/storage: `.reference-ls-frontend/templates/nextjs-feature-demos/features/environment-controls/`
  - Shell / SectionNav context: `features/settings-panel/`
  - Appearance coloring context: `features/user-preferences/`
- **Thin wrappers only.** App wrappers exist to kill page-local repetition, not to replace the kit.
- **Safe UI copy.** Never put secrets, paths, ports, runtime URLs, stack traces, or provider payloads in UI chrome.

## When adding a new feature pack

1. Copy [`_templates/feature-README.template.md`](./_templates/feature-README.template.md).
2. Create `docs/frontend/<feature-slug>/`.
3. Link it from [`README.md`](./README.md).
4. Keep stubs honest — mark **Stub** until real contracts exist.

## Knowledge Graphs (first complete pack)

- Worked example: [`settings/knowledge-graphs/`](./settings/knowledge-graphs/)
- Reusable kit: [`shared/accordion-storage-kit.md`](./shared/accordion-storage-kit.md) (**not exported yet**)
- Prefer the pack’s **target** grammar for new work; treat live drift callouts as warnings, not patterns to copy.
- Live visual remediation stays with the dedicated polish plan — not this factory rewrite.

## Anti-patterns

- Imported non-CE factory rules that reject Local Studio parity
- Pointers outside `frontend/src/` for CE UI code (use `frontend/src/features/…`)
- Inventing Controllers accordion/storage exports before the kit ships them
- Copying hand-rolled live Settings markup when the factory target grammar differs
- New color systems, brand fonts, or page-level gradients
