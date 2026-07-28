# Frontend Agent Contract

This file is subordinate to root `AGENTS.md`. It guides work under `app/client`; it cannot authorize product behavior, public fields, routes, states, or browser capabilities.

## Before a frontend change

1. Read root `AGENTS.md`, `DESIGN.md`, and `docs/prd.md`.
2. Read the applicable route/state, security, HTTP/DTO/SSE, accessibility, responsive, token, component, and parity contracts.
3. Locate the brownfield disposition in `docs/brownfield-refactor-register.md` and `docs/master-build-plan.md` (including P9-06 gallery ownership).
4. Inspect the existing call sites before retaining, migrating, replacing, or adding a component.
5. Confirm the role has a catalog `targetId` with an HTML fixture in `docs/frontend/ui-parity-spec.md` (Phase 1 workstation factory catalog). If not, stop and add catalog + HTML first.

## Hard rules

- Keep route and BFF entry points in `src/app`, capability orchestration in `src/features`, browser-safe generated contracts/utilities in `src/lib`, and product-neutral primitives in `src/ui`.
- Compose only from catalog targets that have script-free HTML fixtures under `app/client/tests/parity/fixtures/`. Missing target → stop and amend the catalog in the same slice; do not invent page-local chrome or a second token system.
- Temporary legacy import specifiers may only alias the same `src/ui` implementation. They cannot contain competing implementations or receive new call sites.
- Use semantic/component tokens only. Preserve `zai-dark` and `zai-light`, compact density, Geist typography, visible focus, keyboard/touch parity, zoom, reduced motion, and responsive drawers.
- Keep the browser thin. Product truth, authorization, lifecycle, and DTO shape come from FastAPI through the same-origin BFF.
- Never place secrets, private IDs, paths, runtime URLs, raw prompts, answers, source text, provider payloads, or stack traces in UI chrome, storage, fixtures, snapshots, or error detail.
- Preserve drafts and selection across recoverable failures as contracted, and clear private projections on identity change or logout.

## Frontend factory boundary (Option A — full workstation gallery)

P9-06 makes HTML the mandatory human steering surface for every Phase 1 UI surface: primitives, shared compositions, and feature composites (including chat shell). The five-starter subset (Button, Input, StatusPill, SettingsRow, Settings Domain accordion) remains `FACTORY_READY`. Additional register rows start `NOT_STARTED` until their parity trio lands — see the full register in `docs/frontend/ui-parity-spec.md`.

Workflow: human edits `tests/parity/fixtures/<targetId>.html` → agent mirrors into the owning React module → Vitest/RTL parity passes → catalog state may become `FACTORY_READY`. HTML never authorizes product behavior. Do not invent a shared Accordion primitive or storageSummary UI. Do not add P11-04 Evidence attach/suggest gallery targets while that work is DEFERRED. Graph gallery covers only the unavailable surface until an approved graph DTO exists.

Script-free HTML fixtures may prove deterministic static appearance only. React tests own behavior, semantics, focus, and accessibility. Production-boundary live acceptance at `/settings?section=domains` and the route visual matrix remain P12-07 (production Next build, same-origin BFF, FastAPI, server-produced DTOs); intercepted or mocked product responses do not satisfy that acceptance.
