# Feature pack README template

Copy into `docs/frontend/<feature-slug>/README.md`.

```markdown
# <Feature name>

**Status:** Stub | Active | Complete (v1)
**Surface:** <where users see it>
**Code:** `frontend/src/features/<…>`

## Purpose

One short paragraph: what this UI is for.

## Anatomy

ASCII or bullet structure of the main layout (required for Complete packs).

## Components

| Name | Role | Base |
|---|---|---|
| … | … | `@/components/ui` `…` (or named template cite if not in kit yet) |

## Behavior

- Live vs save
- Empty / loading / error
- Role gates if any
- Safe-field rules if any

## Do / Don't

- Do: …
- Don't: …

## Theme

Follow [`../theme.md`](../theme.md) and [`DESIGN.md`](../../../DESIGN.md).

## Related

- Plans: …
- Shared kits: …
```
