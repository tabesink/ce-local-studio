# Context Engine Visual Constitution

Status: subordinate visual guidance for Phase 1. Product, security, accessibility, route/state, DTO, and component contracts take precedence.

Context Engine is a compact internal knowledge workstation. It adapts Local Studio patterns into Context Engine-owned tokens and components; Local Studio remains read-only evidence and is never a runtime dependency.

## Required visual language

- Default to the layered-charcoal `zai-dark` theme and support geometry-equivalent `zai-light`.
- Use Geist Sans for interface text and Geist Mono for identifiers, timestamps, code, and technical metadata.
- Use semantic and component tokens from `docs/frontend/design-token-contract.md`; feature code must not establish raw color, spacing, radius, shadow, or transition systems.
- Prefer dense 24–28 px controls, quiet one-pixel boundaries, restrained elevation, compact metadata, and the documented blue focus/link treatment.
- Preserve the authenticated workstation geometry: collapsible discovery rail, one route-owned primary surface, and an optional inspector that becomes an accessible drawer at narrow widths.
- Semantic state must never rely on color alone. Every action must work by keyboard and touch with visible focus and reduced-motion behavior.

Avoid generic dashboard cards, decorative gradients, oversized headings, pill-everything controls, broad semantic-color fills, and marketing-page composition.

## Authority and implementation path

For frontend work, read in this order:

1. root `AGENTS.md` and `docs/prd.md`;
2. applicable security, HTTP/DTO/SSE, route, state, accessibility, and responsive contracts;
3. `docs/frontend/design-token-contract.md`, `docs/frontend/component-contracts.md`, and `docs/frontend/ui-parity-spec.md`;
4. this visual constitution and `docs/frontend/AGENTS.md`.

`src/ui` is the eventual physical home for API-free, router-free, product-neutral primitives. Settings compositions remain under the Settings feature. Existing `components/ui` and `_shared/ui` trees are brownfield inventory and cannot justify a second physical kit or new legacy imports.

**Option A (P9-06):** steer look through script-free HTML parity fixtures for every Phase 1 catalog target (primitives, shared compositions, and feature composites including chat). Compose only from targets that have HTML fixtures; missing target → stop and add catalog + HTML first. HTML never authorizes product behavior — React and the live BFF/API remain authoritative.

Documentation acceptance does not prove application parity. Factory-ready status requires the React, accessibility, and (where owned) production-boundary evidence defined by the brownfield tracker and P9-06 / P12-07.
