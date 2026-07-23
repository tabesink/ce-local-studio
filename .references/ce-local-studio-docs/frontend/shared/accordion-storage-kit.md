# Accordion / storage kit (reusable)

**Status:** **Not exported yet** — composition grammar only; no barrel primitive named Accordion / StorageBar  
**Inspiration (required cite):** `.reference-ls-frontend/templates/nextjs-feature-demos/features/environment-controls/` (Controllers list + storage bars)  
**Visual system:** [`../theme.md`](../theme.md) + [`DESIGN.md`](../../../DESIGN.md)  
**First worked example:** [`../settings/knowledge-graphs/`](../settings/knowledge-graphs/)

## Intent

One Controllers-style expandable-list grammar for Settings (and later routes) that need:

- dense accordion / expandable rows (one open at a time unless a plan says otherwise)
- backend-owned storage summary bars shown **on expand only**
- quiet lifecycle / status chrome without inventing a second row system

Until Controllers accordion + storage bars ship in `@/components/ui`, every implementation must **cite the environment-controls template** and compose existing barrel primitives — do not invent a parallel Accordion API or palette.

## Compose from the live kit (do not invent exports)

| Building block | Job | Source |
|---|---|---|
| `SettingsGroup` | Titled list region | `@/components/ui` |
| `SettingsRow` / fact rows | Quiet label/value rows inside expanded bodies or deploy footers when they fit | `@/components/ui` |
| `StatusPill` | Lifecycle / warning tone | `@/components/ui` |
| `ProgressBar` | Storage usage meter from backend percents | `@/components/ui` |
| `ToggleSwitch` / `IconButton` / `Button` | Lifecycle actions, chevron hit target | `@/components/ui` |
| Controllers accordion row chrome | Expandable list geometry, muted mono subtitle, storage block hierarchy | **Not in kit yet** — cite `environment-controls` |

### Defer until needed

Nested storage-breakdown chevrons, multi-open accordion, browser-computed quotas, radio “active controller” semantics — document only when a product plan requires them. Do not build speculative wrappers.

## Anatomy

```
┌ SettingsGroup title ───────────────────────────────────────────┐
│ optional muted description                                     │
├────────────────────────────────────────────────────────────────┤
│ ▸ Name                         [StatusPill]  [lifecycle ctrl]  │
│   mono-id                                                      │
├────────────────────────────────────────────────────────────────┤
│ ▾ Name                         [StatusPill]  [lifecycle ctrl]  │
│   mono-id                                                      │
│   ┌ expanded (safe) ─────────────────────────────────────────┐ │
│   │ locked config facts (no paths / ports / URLs)            │ │
│   │ Storage                                                  │ │
│   │   total / limit (backend)     [warning pill if needed]   │ │
│   │   ProgressBar (total only on compact Settings surfaces)  │ │
│   │ quiet danger Delete (or plan-specified placement)        │ │
│   └──────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ Deploy / create footer (same group or adjacent group per plan) │
└────────────────────────────────────────────────────────────────┘
```

## Composition rules

1. **Cite before invent.** While status is **not exported yet**, the implementation note / PR must name `environment-controls` as the Controllers reference.
2. **Barrel first.** Prefer `SettingsGroup`, `StatusPill`, `ProgressBar`, and related exports over page-local chrome.
3. **Expand-only storage.** Collapsed headers do not show storage bars. Expanded bodies render admin `storageSummary` only — never browser-inspected paths or invented percents.
4. **One visual family.** Match Controllers density (row height, muted id, pill weight, quiet actions). Do not invent a second card-grid list language.
5. **Relate to Settings shell.** This kit sits inside Settings content (`SettingsLayout` / section content). It does not replace SectionNav or the settings-panel shell template.

## Safe-field contract (UI copy)

Storage and expanded facts may show only backend-safe summary fields (e.g. total/limit/warning/closed component kinds from admin `storageSummary`).

Never surface in this grammar:

- filesystem / storage paths
- host ports, runtime URLs, container ids
- Docker / compose targets
- operator dumps, secrets, stack traces

Product ownership for Knowledge Graphs remains with domain-deploy / storageSummary plans; this kit only documents the reusable chrome.

## Do / Don't

- Do: reuse this grammar for any later route that needs Controllers-style accordion + storage bars.
- Do: keep expand state local/UI-only unless a plan says otherwise.
- Do: mark PRs / docs with **not exported yet** until `@/components/ui` gains the primitives.
- Don't: claim `Accordion`, `StorageBar`, or Controllers row as live barrel exports today.
- Don't: copy hand-rolled live markup that drifts from this target — prefer this kit + the KG pack, then remediate live UI via the polish plan.
- Don't: compute storage in the browser from paths or runtime targets.

## First consumer

[`../settings/knowledge-graphs/`](../settings/knowledge-graphs/) — Settings → Knowledge Graphs Complete (v1) pack.
