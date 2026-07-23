# Theme primer (Context Engine)

Canonical contract: root [`DESIGN.md`](../../DESIGN.md). This page is orientation only.

## Atmosphere

Dense Local Studio–style workstation: dark-first by default, quiet surfaces, readable technical workflows.
Tokens come from the appearance / user-preferences runtime (`--ui-*`, `--fs-*`, `--rad-*`) with Geist / Geist Mono — not a white zinc marketing dashboard.

## Quick palette (token roles)

| Role | Feel | Authority |
|---|---|---|
| Page / shell | Dark workstation base (light mode pair exists) | `--ui-*` via appearance runtime |
| Text | High-contrast on surface | `text` / foreground tokens |
| Panel | Quiet elevated surface + border | surface / border tokens |
| Muted | Secondary labels, mono ids | muted + `--fs-xs` |
| Primary action | High-contrast monochrome CTA | primary tokens |
| Danger | Destructive / delete only | danger / destructive tokens |

Do not invent dark-only or feature-local hex. Discover live class/token usage from `@/components/ui` and `DESIGN.md`.

## Type

- Geist for UI; Geist Mono for IDs, paths (when allowed), timestamps, machine-safe tokens.
- Prefer compact `--fs-*` scale; avoid arbitrary browser defaults.
- Weight hierarchy stays within 400 / 500 / 600.

## Shape & depth

- Dense 24px/28px controls; radius from `--rad-*` (full pills are exceptional).
- Borders and dividers separate regions more than shadows.
- Prefer rows / groups over card grids for Settings lists.

## Settings density

Settings panels should feel like compact Controllers / settings-panel grammar:

```
Section title + optional muted description
────────────────────────────────────────────────────────────────
Row label (+ muted id)                    [ pill | toggle | … ]
  └ expanded body (safe fields / storage bars when applicable)
```

For Controllers-style accordion + storage bars, reuse [`shared/accordion-storage-kit.md`](./shared/accordion-storage-kit.md) (status: **not exported yet** — cite `environment-controls`).

## Out of theme for this app

- Generic white shadcn/zinc dashboard chrome
- Purple-on-white / indigo glow dashboards
- Warm cream + terracotta “editorial” looks
- Pill clusters, stat strips, floating badges on heroes
- Feature-local `data-theme` or parallel token systems
