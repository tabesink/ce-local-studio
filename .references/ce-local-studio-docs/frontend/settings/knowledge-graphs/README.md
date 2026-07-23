# Settings → Knowledge Graphs

**Status:** Complete (v1)  
**Surface:** Settings panel → **Knowledge Graphs**  
**Code:**  
- `frontend/src/features/settings-panel/SettingsPanel.tsx`  
- `frontend/src/features/settings-panel/domainSettingsHelpers.ts`  
**Shared kit:** [`../../shared/accordion-storage-kit.md`](../../shared/accordion-storage-kit.md) (**not exported yet**)

## Purpose

Let Administrators deploy and control backend-owned Knowledge Graphs from Settings using Controllers-style accordion rows, a Deploy create/start gesture, and expand-only storage bars from admin `storageSummary` — without ports, runtime URLs, paths, or Docker guts.

## Docs in this pack

| File | Contents |
|---|---|
| [`README.md`](./README.md) | This overview + authority + live drift |
| [`anatomy.md`](./anatomy.md) | ASCII target layout |
| [`components.md`](./components.md) | Composition map |
| [`behavior.md`](./behavior.md) | Expand, lifecycle, safe fields |
| [`do-dont.md`](./do-dont.md) | Guardrails |

## Product summary

- Visible group label: **Knowledge Graphs** (API entity remains Knowledge Domain).
- Accordion rows: chevron, display name, mono id, lifecycle status, Start/Stop XOR, quiet Delete.
- Expand shows locked embedding + backend-owned storage summary (collapsed by default; one open row).
- Deploy creates then starts; failures keep safe SettingsNotice copy only.
- Controllers accordion/storage primitives remain **not exported yet** — cite `environment-controls`.

## Authority split

| Concern | Authority |
|---|---|
| Accordion / storage UI grammar | This pack + [`../../shared/accordion-storage-kit.md`](../../shared/accordion-storage-kit.md) |
| Visual tokens / kit inventory | [`DESIGN.md`](../../../../DESIGN.md) / [`../../theme.md`](../../theme.md) |
| Structure + safe fields | [`docs/plans/2026-07-10-006-feature-domain-deploy-settings-ui-plan.md`](../../../plans/2026-07-10-006-feature-domain-deploy-settings-ui-plan.md) |
| Controllers density polish (live remediation) | [`docs/plans/2026-07-11-002-feature-knowledge-graphs-settings-parity-polish-plan.md`](../../../plans/2026-07-11-002-feature-knowledge-graphs-settings-parity-polish-plan.md) |
| Kit gap honesty | [`docs/plans/2026-07-11-003-feature-design-kit-contract-inventory-plan.md`](../../../plans/2026-07-11-003-feature-design-kit-contract-inventory-plan.md) |
| Factory requirements | [`docs/plans/2026-07-13-001-feat-frontend-uiux-component-factory-plan.md`](../../../plans/2026-07-13-001-feat-frontend-uiux-component-factory-plan.md) |

## Inspiration (bounded)

Reference demo: `.reference-ls-frontend/templates/nextjs-feature-demos/features/environment-controls/`  
Take: Controllers list density, expandable row chrome, storage bar hierarchy, quiet actions.  
Leave: radio “active controller”, host ports, auto URLs, container ids, operator dumps.

Shell / coloring context only: `features/settings-panel/`, `features/user-preferences/`.

## Live-code drift (do not copy as canon)

**Target grammar in this pack is canonical for new work.** Live `SettingsPanel` Knowledge Graphs markup may still hand-roll Controllers density and omit pieces of the product target. Treat differences as warnings; remediate via plan 002 / kit export follow-ons — do not freeze hand-rolls as the pattern to copy.

Known drift themes to re-check against live code (evidence only):

- Hand-rolled expandable rows instead of cited Controllers density composition (**not exported yet** as a shared primitive).
- Collapsed-row status / action density may lag Controllers (e.g. missing or lighter `StatusPill` weight vs target).
- Storage must remain expand-only total/limit + one bar + warning (plan 002); do not re-add component breakdown chrome on this surface.
- Deploy may live in an adjacent `SettingsGroup` (“New Knowledge Graph”) per polish decisions — match the product plan in force, not ad-hoc card stacks.

See plans **006**, **002**, and **003** linked above for remediation ownership.
