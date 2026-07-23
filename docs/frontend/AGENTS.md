# Frontend Agent Contract

This file is subordinate to root `AGENTS.md`. It guides work under `app/client`; it cannot authorize product behavior, public fields, routes, states, or browser capabilities.

## Before a frontend change

1. Read root `AGENTS.md`, `DESIGN.md`, and `docs/prd.md`.
2. Read the applicable route/state, security, HTTP/DTO/SSE, accessibility, responsive, token, component, and parity contracts.
3. Locate the brownfield disposition in `docs/brownfield-refactor-register.md` and `docs/master-build-plan.md`.
4. Inspect the existing call sites before retaining, migrating, replacing, or adding a component.

## Hard rules

- Keep route and BFF entry points in `src/app`, capability orchestration in `src/features`, browser-safe generated contracts/utilities in `src/lib`, and product-neutral primitives in `src/ui`.
- Compose covered roles from the canonical kit. If the catalog has a gap, use the contracted existing CE control and record the gap; do not invent page-local chrome or a second token system.
- Temporary legacy import specifiers may only alias the same `src/ui` implementation. They cannot contain competing implementations or receive new call sites.
- Use semantic/component tokens only. Preserve `zai-dark` and `zai-light`, compact density, Geist typography, visible focus, keyboard/touch parity, zoom, reduced motion, and responsive drawers.
- Keep the browser thin. Product truth, authorization, lifecycle, and DTO shape come from FastAPI through the same-origin BFF.
- Never place secrets, private IDs, paths, runtime URLs, raw prompts, answers, source text, provider payloads, or stack traces in UI chrome, storage, fixtures, snapshots, or error detail.
- Preserve drafts and selection across recoverable failures as contracted, and clear private projections on identity change or logout.

## Frontend factory boundary

The D0 starter catalog covers Button, Input, StatusPill, SettingsRow, and a Settings-owned Domain accordion entry. The accordion remains `BLOCKED_CONTRACT` until its interaction contract is approved. The five entries are starter coverage, not a complete allowlist.

Script-free HTML fixtures may prove deterministic static appearance only. React tests own behavior, semantics, focus, and accessibility. Live acceptance at `/settings?section=domains` must run through the production Next build, same-origin BFF, and FastAPI with server-produced DTOs; intercepted or mocked product responses do not satisfy acceptance.
