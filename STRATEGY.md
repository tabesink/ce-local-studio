---
name: CE Frontend Factory
last_updated: 2026-07-22
---

# CE Frontend Factory Strategy

## Target problem

Builders and coding agents can follow Context Engine backend docs reliably, but frontend has no equivalent operable path. Look-and-feel gets invented instead of controlled through HTML mockups bound to a shared primitive/composite kit, so surfaces drift from the product theme.

## Our approach

Compose only from the HTML-backed primitive kit; never invent page-local chrome or a second token system — so agents can change look via mockups without fracturing the theme.

## Who it's for

**Primary:** Coding agents implementing CE UI slices - They're hiring the factory to ship theme-aligned primitives/composites without inventing chrome.

## Key metrics

- **Kit coverage** - Share of required primitives with a CE-tokenized HTML mockup and matching React primitive (factory catalog).
- **Compose-only compliance** - % of frontend PRs with zero new page-local chrome and zero raw color/spacing outside tokens (style-token + import-boundary gates).
- **Agent rework rate** - Share of UI slices needing a second pass for invented chrome, wrong density, or wrong theme (merge review checklist).
- **Composite reuse** - Product surfaces using shared composites vs one-off layouts (catalog + provenance).

## Tracks

### Visual constitution

CE-owned `DESIGN.md` plus token authority as the single theme/geometry source of truth.

_Why it serves the approach:_ Agents need one visual constitution so “compose from the kit” has an unambiguous look.

### HTML ↔ React kit

Tokenized HTML mockups for required primitives, each bound 1:1 to a React primitive in `src/ui`.

_Why it serves the approach:_ Design stays editable in HTML while shipping stays kit-only — no parallel chrome.

### Agent operating layer + composites

`docs/frontend/AGENTS.md`, forced read order, feature packs; shared composites (e.g. Settings domain accordion) built only from the kit, with compose-only gates.

_Why it serves the approach:_ Makes the compose-only rule the default path for agents, and proves it on real composites.
