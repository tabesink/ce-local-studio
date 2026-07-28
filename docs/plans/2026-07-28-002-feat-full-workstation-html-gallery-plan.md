---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-child
title: Full Workstation HTML Gallery Steering - Plan
type: feat
date: 2026-07-28
enriched: 2026-07-28
origin: docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md
tracker: docs/master-build-plan.md#P9-06
---

# Full Workstation HTML Gallery Steering - Plan

## Goal Capsule

- **Objective:** Make script-free HTML parity fixtures the mandatory human steering surface for every Phase 1 frontend UI surface — primitives, shared compositions, and feature composites (including chat shell) — while React remains behavioral authority and live BFF/API remains product authority.
- **Authority:** Root `AGENTS.md`; `DESIGN.md`; `docs/frontend/ui-parity-spec.md` (catalog owner); `docs/frontend/component-contracts.md`; `docs/frontend/AGENTS.md`; factory plan `docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md` (superseded for gallery scope only); this Product Contract.
- **Execution profile:** Authority amendments + catalog expansion + parity trios + structural enforcement. No new product routes, DTOs, SSE events, or Live Settings/Playwright F3 claims (those remain P12-07).
- **Stop conditions:** Stop if HTML is treated as product/behavior authority; if stubbed product responses appear in live routes; if a second physical kit or Storybook-as-authority is introduced; if Phase 2/3 surfaces enter the catalog; if graph canvas is gallery-enabled before an approved graph DTO.
- **Tail ownership:** P12-07 owns production-boundary Playwright route matrix and Settings F3. Residual mega-kit demolition beyond gallery ownership remains FE-01/P9-05 residuals. P11-04 Evidence attach UX stays DEFERRED and must not appear as a gallery target.

---

## Product Contract

### Summary

Adopt **Option A — full workstation gallery**: every Phase 1 UI surface agents may implement must have a versioned catalog target with an HTML fixture before chrome work is allowed. Expand beyond the five-starter factory. Chat, documents, shell, login, and remaining primitives become first-class gallery targets. HTML steers look; React/Vitest steers interaction; production routes stay server-backed.

### Problem Frame

The D0/P9-01 factory proved HTML→React steering for five targets, then left chat/documents/shell as route-only work. Humans cannot steer those surfaces with HTML today, so agents invent or copy live markup. Option A closes that gap without making HTML authorize product behavior.

### Key Decisions

- **Full catalog is mandatory.** Uncovered Phase 1 chrome is a stop condition, not an advisory “parity gap.”
- **Three target layers.** Primitive / shared composition / feature composite — same trio shape (`manifest` + `fixtures/*.html` + `react/*.test.tsx`).
- **HTML remains non-authoritative for behavior.** Forbidden claims in manifests stay (no focus/ARIA/product-state authority from HTML alone).
- **Feature composites are static state galleries.** Synthetic labels only; reachable visual states (loading/empty/ready/error/inspector-open/narrow) without network or mocked live product responses.
- **Chat shell is in scope.** ConversationRail, Transcript, Composer, EvidenceInspector each get targets; optional combined `chat-workbench` layout target for three-region geometry.
- **Graph stays unavailable-only.** Gallery covers the deliberate unavailable surface, not a canvas.
- **P11-04 attach UX stays out.** No suggest/attach chip gallery while DEFERRED.
- **New tracker row P9-06.** Does not reopen P9-01..P9-05 DONE status; extends the factory.

### Actors

| Actor | Role |
| --- | --- |
| Human builder / reviewer | Edits HTML fixtures to steer look; reviews agent React mirrors |
| Coding agent | Implements only catalog-covered roles; mirrors HTML into React; records new targets before inventing chrome |
| Structural CI | Fails missing HTML for catalog rows and unmapped new UI ownership |
| P12-07 | Consumes catalog targets for route visual matrix; does not replace HTML steering |

### Requirements

**Authority**

- R1. Amend `docs/frontend/ui-parity-spec.md` so the D0 catalog is the full Phase 1 workstation register (not starter-only), with Option A readiness rules.
- R2. Amend `docs/frontend/AGENTS.md` and `DESIGN.md`: compose only from catalog targets that have HTML fixtures; missing target → stop and add catalog+HTML first.
- R3. Record factory-plan supersession for gallery scope: deferred “chat/document/graph parity work” no longer excludes HTML gallery (graph canvas still blocked until contract).
- R4. Add `docs/master-build-plan.md` task **P9-06** owning this initiative; link brownfield register residual for mega-kit/gallery coverage.

**Catalog and assets**

- R5. Every target has `schemaVersion`, `targetId`, `owner`, `catalogState`, `layer` (`primitive` \| `shared` \| `feature`), `disposition`, shared/htmlStatic/react assertion blocks, and synthetic-only sourceEvidence notes.
- R6. Exact paths remain: `app/client/tests/parity/manifests/<id>.json`, `fixtures/<id>.html`, `react/<id>.test.tsx`.
- R7. HTML fixtures are script-free, network-free, non-routable, production-bundle-excluded, synthetic data only (R11 from factory plan preserved).
- R8. Starter five remain `FACTORY_READY`; new targets start `NOT_STARTED` and earn `FACTORY_READY` via shared + HTML-static + React (Vitest/RTL) + applicable a11y assertions (Playwright route matrix still P12-07).
- R9. Provide a non-routable local index (dev/test-only) listing all fixtures for human browsing — not a Next.js product route.

**Enforcement**

- R10. Extend `app/client/tests/frontend-uiux-factory.test.mjs` (and/or a dedicated catalog test) so every catalog row requires the trio on disk once state ≠ `BLOCKED_CONTRACT`.
- R11. Structural gate: new or relocated UI modules under `src/ui` and listed feature composition owners must map to a `targetId`; unmapped chrome fails CI.
- R12. Agents must not invent page-local chrome for a role that has a catalog target; uncovered contracted roles require a new catalog row in the same slice.

**Visual linkage**

- R13. `docs/frontend/visual-regression-plan.md` must state that P12-07 route baselines reference catalog `targetId`s (or HTML snapshot regions) so HTML steering and Playwright do not diverge.

### Acceptance Examples

- AE1. Human steers chat composer density in `composer.html`; agent updates React Composer; Vitest parity passes; live `/chat` still uses server DTOs/SSE.
- AE2. Agent attempts new chat chrome without a catalog target → structural/factory gate fails or agent stops for catalog amendment.
- AE3. Full catalog index opens locally; every Phase 1 target listed; no private IDs, paths, or server payloads in HTML.
- AE4. Graph gallery shows only unavailable state; no LightRAG/canvas markup.

### Scope Boundaries

**In**

- Authority doc amendments (parity, AGENTS, DESIGN, visual-regression, master-build-plan, brownfield note, factory supersession note).
- Full catalog register (Appendix A) with parity trios for all listed targets.
- Local fixture index + CI enforcement.
- Migration/disposition of residual mega-kit controls that live surfaces already use (Select, ToggleSwitch, UiModal, PageState, etc.) into catalog ownership homes.

**Out**

- Claiming P12-07 DONE or production-ingress E2E.
- Storybook-as-authority.
- Phase 2 observability / Phase 3 wiki gallery targets.
- Graph canvas / node detail before approved graph contract.
- P11-04 Evidence attach/suggest UI.
- Demolishing every legacy alias in one slice (alias-only remains allowed per R9 factory rules).

### Dependencies / Assumptions

- Token contract and `zai-dark` / `zai-light` remain sole theme system.
- Existing five starter trios stay green and are not rewritten except for catalog metadata (`layer` field).
- Chat/documents/settings React features already exist; gallery adds steering + parity proof, not greenfield product behavior.
- Local Studio references remain read-only visual evidence.

---

## Planning Contract

### Key Technical Decisions

- **KTD1. Tracker id = P9-06.** New child under P9; does not reopen P9-01..05. `(session-settled: user chose Option A)`
- **KTD2. Catalog lives only in `ui-parity-spec.md`.** Other docs link; no duplicate schema. Add `layer` to manifest schema (v1 → v1.1 or `schemaVersion: 2` if needed for strict parsers).
- **KTD3. Feature composites map 1:1 to contracted roles**, not one giant HTML page per route — except one optional `chat-workbench` / `documents-workbench` geometry target for three-region / list+viewer layout.
- **KTD4. Ownership homes unchanged.** Primitives → `src/ui` (migrate when FACTORY_READY). Shell → `src/features/shell` + `navigation-sidebar`. Chat → `src/features/chat-shell`. Documents → `src/features/documents`. Settings → `src/features/settings-panel`. Auth login → `src/features/auth`. Prefer extract-from-monolith feature files over inventing parallel components.
- **KTD5. Enforcement altitude.** Node tests assert catalog↔files; structure tests assert ownership mapping; Vitest owns interaction. No HTML-driven visual diff required for FACTORY_READY (Playwright remains P12-07).
- **KTD6. Wave sequencing.** Authority → primitives/shared in use → shell → chat → documents/settings/login → residual contracted primitives → index+gates. Chat is not blocked on finishing unused FE-01 controls (Card, SegmentedControl) if those stay `NOT_STARTED` but listed.
- **KTD7. “In use” vs “contracted unused”.** Targets already imported by live features are Wave 1–4. Contracted-but-unused primitives may remain `NOT_STARTED` in catalog without blocking chat gallery — but agents still cannot invent replacements for them.

### Technical Design

```text
Human edits tests/parity/fixtures/<target>.html
        │
        ▼
Manifest shared + htmlStatic assertions
        │
        ▼
Agent updates owner React (src/ui or src/features/*)
        │
        ▼
Vitest/RTL react/<target>.test.tsx
        │
        ▼
FACTORY_READY (catalog state)
        │
        ▼
P12-07 Playwright route matrix references targetIds
```

Fixture index: `app/client/tests/parity/index.html` (or generated) — open via `file://` or a non-exported static server script; never registered under `src/app`.

### Assumptions

- A1. Master-build-plan may gain P9-06 without renumbering DONE P9 tasks.
- A2. Manifest schema bump is additive (`layer` required for new targets; starters backfilled in U1).
- A3. Extracting Transcript/Composer from `ChatShell.tsx` is allowed when needed for ownership clarity; behavior must not regress P9-02 proofs.

### Open Questions

| ID | Question | Status |
| --- | --- | --- |
| Q1 | Manifest `schemaVersion` 1+`layer` vs hard bump to 2? | Deferred — implementer chooses additive field if existing parsers tolerate it; else bump to 2 in U1 |
| Q2 | Combined workbench HTML targets required or optional? | Deferred — default optional; add if human steering of three-region geometry needs a single file |

### Sequencing

1. U1 Authority + catalog schema + starter backfill  
2. U2 In-use primitives / shared chrome (Select, Modal, Toggle, PageState, …)  
3. U3 Shell compositions  
4. U4 Chat feature composites  
5. U5 Documents + settings remainder + login + graph-unavailable  
6. U6 Residual contracted primitives + index + CI enforcement + tracker/brownfield closure  

---

## Implementation Units

### U1. Authority and catalog schema

**Goal:** Make Option A normative and list the full register with correct states for existing starters.

**Files:**
- Modify: `docs/frontend/ui-parity-spec.md`
- Modify: `docs/frontend/AGENTS.md`
- Modify: `DESIGN.md`
- Modify: `docs/frontend/visual-regression-plan.md`
- Modify: `docs/master-build-plan.md` (add P9-06)
- Modify: `docs/brownfield-refactor-register.md` (gallery residual / shell-UI row note)
- Modify: `docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md` (supersession note for gallery scope only)
- Modify: `app/client/tests/parity/manifests/{button,input,status-pill,settings-row,domains-accordion}.json` (`layer` backfill)
- Modify: `app/client/tests/frontend-uiux-factory.test.mjs` (assert Option A wording + full-register anchor)

**Approach:** Rewrite D0 catalog section: starter table becomes subset of Appendix A register; state that HTML fixture is required before chrome implementation; keep HTML non-behavior-authority language. Add P9-06 row `NOT_STARTED` → will flip as units close.

**Tests:**
- `app/client/tests/frontend-uiux-factory.test.mjs` — asserts full-workstation gallery language, P9-06 mention in master-build-plan, compose-from-HTML-catalog rule in AGENTS.

**Verification:**
- Factory authority tests green; docs cross-link without contradicting starter FACTORY_READY statuses.

---

### U2. In-use kit targets (live imports)

**Goal:** Gallery-cover controls already used by Settings/Preferences/shell that are not yet starter FACTORY_READY.

**Minimum targetIds:** `select`, `toggle-switch`, `ui-modal` (ConfirmActionDialog / UiModal), `page-state` (DataSurface/PageState), `error-box` / `alert` as applicable to live `ErrorBox`/`PageState`.

**Files:**
- Create: `app/client/tests/parity/manifests/<id>.json`
- Create: `app/client/tests/parity/fixtures/<id>.html`
- Create: `app/client/tests/parity/react/<id>.test.tsx`
- Modify or migrate: ownership under `src/ui` or keep Settings-consumed aliases per inventory disposition in `docs/_scratch/p9-01-ui-inventory.md`
- Create: `docs/_scratch/p9-06-u2-kit-inventory.md` (call-site → target map)

**Approach:** Inventory current imports from `@/components/ui` / `_shared/ui`; one disposition per symbol; HTML steers variants/states already required by `component-contracts.md`.

**Tests:**
- New Vitest files per target; structure ownership tests updated if physical home moves.

**Verification:**
- Each U2 target `FACTORY_READY` at Vitest altitude; no live route behavior change required beyond import retarget.

---

### U3. Shell compositions

**Goal:** HTML-steer AppShell, NavigationRail, and related chrome.

**targetIds:** `app-shell`, `navigation-rail`, `pane-header` (if distinct in live UI), mobile-nav drawer region covered in shell HTML states.

**Files:**
- Create: parity trio for each
- Modify: `app/client/src/features/shell/AppShell.tsx`
- Modify: `app/client/src/features/navigation-sidebar/NavigationSidebar.tsx`
- Modify: `app/client/tests/structure/ui-ownership.test.ts` as needed

**Approach:** Static regions for expanded/collapsed rail, narrow drawer, main slot placeholder; no auth truth in HTML.

**Tests:**
- Vitest keyboard/collapse presentation where owned by React; HTML static regions only for geometry/tokens.

**Verification:**
- Shell targets FACTORY_READY; chat-shell remains separate feature (not merged).

---

### U4. Chat feature composites

**Goal:** HTML-steer all chat workbench regions.

**targetIds:** `conversation-rail`, `transcript`, `composer`, `evidence-inspector`; optional `chat-workbench`.

**Files:**
- Create: parity trios
- Modify: `app/client/src/features/chat-shell/ChatShell.tsx`, `EvidencePanel.tsx`, and extracts if needed (`Transcript.tsx`, `Composer.tsx`, …)
- Modify: existing `app/client/tests/chat-inspector.test.tsx` / chat tests only if ownership splits require import updates
- Create: `docs/_scratch/p9-06-u4-chat-gallery-evidence.md`

**Approach:** Synthetic turns/labels/evidence cards; states: empty conversation, streaming placeholder presentation, ready with selection, inspector open, narrow drawer, cancelled/redacted presentation labels — no real SSE, no private IDs, no raw prompts beyond synthetic lorem.

**Tests:**
- Vitest: selection, keyboard cards, drawer focus return already proven in P9-02 must remain green; new parity tests cover catalog assertions.

**Verification:**
- Four (or five) chat targets FACTORY_READY; P9-02 stream/reducer proofs unchanged; no P11-04 chips.

---

### U5. Documents, settings remainder, login, graph-unavailable

**Goal:** Complete route-feature gallery coverage for remaining Phase 1 routes.

**targetIds:** `document-library`, `document-viewer`, `source-operation-panel` (admin bits only if present), `settings-nav`, `settings-group`, `login`, `graph-unavailable`.

**Files:**
- Create: parity trios
- Modify: `DocumentsPage.tsx`, `PdfPreview.tsx`, `SettingsPanel.tsx`, `LoginPage.tsx`, `GraphPage.tsx` as needed for ownership clarity
- Create: `docs/_scratch/p9-06-u5-routes-gallery-evidence.md`

**Approach:** Documents: list+viewer states and PDF chrome geometry without real bytes. Settings: section nav + groups (domains accordion already FACTORY_READY — link, don’t duplicate). Login: compact card. Graph: unavailable copy only.

**Tests:**
- Vitest parity per target; existing documents/graph-unavailable tests stay green.

**Verification:**
- All U5 targets FACTORY_READY or explicitly `BLOCKED_CONTRACT` with named missing authority (none expected for these).

---

### U6. Residual primitives, index, enforcement, closure

**Goal:** List remaining contracted primitives; ship index + hard gates; close P9-06.

**targetIds (may stay NOT_STARTED if unused):** `textarea`, `checkbox`, `segmented-control`, `tabs`, `card`, `table`, `list-row`, `drawer`, `skeleton`, `markdown-content`, `resource-table`, `operation-status`, `confirm-action-dialog` (if not satisfied by `ui-modal`), `right-inspector` (if not satisfied by evidence-inspector/shell).

**Files:**
- Create: catalog rows + optional stub manifests for NOT_STARTED residuals (HTML optional until work begins — but R10: once state leaves NOT_STARTED/BLOCKED, trio required)
- Create: `app/client/tests/parity/index.html` (+ optional generator script)
- Modify: `app/client/tests/structure/*` catalog-map enforcement
- Modify: `app/client/tests/frontend-uiux-factory.test.mjs`
- Create: `docs/_scratch/p9-06-full-gallery-evidence.md`
- Modify: `docs/master-build-plan.md` P9-06 → DONE when gates pass

**Approach:** Enforcement test loads catalog register (from a machine-readable `app/client/tests/parity/catalog.json` exported from/aligned with ui-parity-spec) and asserts file presence + no unmapped owners. Prefer a single `catalog.json` generated or hand-maintained as CI source of truth mirrored in the doc table.

**Tests:**
- Catalog completeness test; index links resolve to fixtures on disk; privacy scan over fixtures (no forbidden substrings).

**Verification:**
- P9-06 DONE evidence packet; Option A agent rule enforced; residuals explicitly NOT_STARTED without blocking in-use gallery.

---

## Verification Contract

| Gate | Command / proof |
| --- | --- |
| Factory authority | From `app/client`: node test including `tests/frontend-uiux-factory.test.mjs` |
| Parity React | From `app/client`: `vitest run` (parity + existing chat/documents) |
| Structure | `tests/structure/**/*.test.ts` including catalog-map |
| Privacy | Fixture scan for credentials, `/var/`, `s3://`, private UUID patterns, runtime URLs |
| Docs | P9-06 row + ui-parity-spec register match `catalog.json` |
| Non-goals | Do not require P12-07 Playwright pass to close P9-06 |

---

## Definition of Done

**Global**

1. Option A is normative in ui-parity-spec, AGENTS, DESIGN.
2. Every Phase 1 in-use surface has FACTORY_READY HTML/React/manifest trio.
3. Residual contracted-but-unused targets are listed NOT_STARTED (not omitted).
4. CI fails on missing trio for active catalog rows and unmapped chrome.
5. Local fixture index exists and is non-routable in production.
6. HTML never authorizes product behavior; live routes still server-backed.
7. P9-06 evidence recorded; factory plan supersession noted; P12-07 linkage documented.

**Per unit:** unit Goal met; listed tests green; no Phase 2/3 or P11-04 gallery targets; stop conditions honored.

---

## Appendix

### Appendix A — Phase 1 catalog register (initial)

| targetId | layer | owner | initial state | wave |
| --- | --- | --- | --- | --- |
| button | primitive | src/ui | FACTORY_READY | — |
| input | primitive | src/ui | FACTORY_READY | — |
| status-pill | primitive | src/ui | FACTORY_READY | — |
| settings-row | feature | src/features/settings-panel | FACTORY_READY | — |
| domains-accordion | feature | src/features/settings-panel | FACTORY_READY | — |
| select | primitive | src/ui (migrate) | NOT_STARTED | U2 |
| toggle-switch | primitive | src/ui (migrate) | NOT_STARTED | U2 |
| ui-modal | shared | src/ui or settings-owned confirm | NOT_STARTED | U2 |
| page-state | shared | src/ui | NOT_STARTED | U2 |
| error-box | primitive | src/ui | NOT_STARTED | U2 |
| app-shell | shared | src/features/shell | NOT_STARTED | U3 |
| navigation-rail | shared | src/features/navigation-sidebar | NOT_STARTED | U3 |
| pane-header | shared | src/features/shell or ui | NOT_STARTED | U3 |
| conversation-rail | feature | src/features/chat-shell | NOT_STARTED | U4 |
| transcript | feature | src/features/chat-shell | NOT_STARTED | U4 |
| composer | feature | src/features/chat-shell | NOT_STARTED | U4 |
| evidence-inspector | feature | src/features/chat-shell | NOT_STARTED | U4 |
| chat-workbench | feature | src/features/chat-shell | NOT_STARTED (optional) | U4 |
| document-library | feature | src/features/documents | NOT_STARTED | U5 |
| document-viewer | feature | src/features/documents | NOT_STARTED | U5 |
| settings-nav | feature | src/features/settings-panel | NOT_STARTED | U5 |
| settings-group | feature | src/features/settings-panel | NOT_STARTED | U5 |
| login | feature | src/features/auth | NOT_STARTED | U5 |
| graph-unavailable | feature | src/features/graph | NOT_STARTED | U5 |
| textarea | primitive | src/ui | NOT_STARTED | U6 |
| checkbox | primitive | src/ui | NOT_STARTED | U6 |
| segmented-control | primitive | src/ui | NOT_STARTED | U6 |
| tabs | primitive | src/ui | NOT_STARTED | U6 |
| card | primitive | src/ui | NOT_STARTED | U6 |
| table | primitive | src/ui | NOT_STARTED | U6 |
| list-row | primitive | src/ui | NOT_STARTED | U6 |
| drawer | shared | src/ui | NOT_STARTED | U6 |
| skeleton | primitive | src/ui | NOT_STARTED | U6 |
| markdown-content | primitive | src/ui | NOT_STARTED | U6 |
| resource-table | shared | src/ui / documents | NOT_STARTED | U6 |
| operation-status | shared | src/ui / settings | NOT_STARTED | U6 |
| confirm-action-dialog | shared | merge with ui-modal if identical | NOT_STARTED | U6 |
| right-inspector | shared | merge with evidence-inspector if identical | NOT_STARTED | U6 |

### Appendix B — Authority supersession

Factory plan **Deferred for later → “Future CE-owned chat, document, or graph parity work…”** is superseded for **HTML gallery inclusion** of chat/documents/shell/login/graph-unavailable. Graph **canvas** enablement remains blocked on approved graph DTO. Storybook-as-authority remains deferred/rejected.
