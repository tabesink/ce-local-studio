# P9-04 Settings Domains Inventory

Date: 2026-07-27  
Status: complete for P9-04 U1 inventory; contract amendment follows in the same unit. Not a release completion record.

Authority: `docs/master-build-plan.md` P9-04; `docs/plans/2026-07-27-011-feat-settings-domain-accordion-plan.md`; P3-01 closed admin DTOs; P9-01 factory accordion hard stop; DRIFT-04 residuals.

Session-settled: no `storageSummary` DTO reopen; one vertical slice; include DRIFT-04 nav residuals.

## Surfaces inventoried

| Surface | Path | Disposition |
| --- | --- | --- |
| Settings route | `app/client/src/app/settings/page.tsx` | **modify** — keep AppShell wrap; section URL sync owned by SettingsPanel (or page pass-through) |
| Settings panel | `app/client/src/features/settings-panel/SettingsPanel.tsx` | **modify** — Domains accordion rewrite, Knowledge Domains labels, strip storage chrome, wire `?section=` |
| Domain helpers | `app/client/src/features/settings-panel/domainSettingsHelpers.ts` | **modify** — retain one-open / deploy / lifecycle pure helpers; remove or stop requiring storageSummary helpers for UI |
| SettingsRow | `app/client/src/features/settings-panel/SettingsRow.tsx` | **retain** — factory-ready composition |
| Domains API | `app/client/src/features/domains/api.ts` | **replace** lifted shapes — generated `AdminDomainDto` / `OperationDto`, `{operation}` start/stop, If-Match delete, member `queryEligible` |
| Chat domain selector | `app/client/src/features/chat-shell/ChatShell.tsx` | **modify** with U2 — `available` → `queryEligible` |
| Documents domain filter | `app/client/src/features/documents/DocumentsPage.tsx` | **modify** with U2 — same |
| Domains Settings tests | `app/client/tests/domains-settings.test.mjs` | **modify** — characterize-first rewrite off storageSummary / Knowledge Graphs |
| Parity forbid gate | `app/client/tests/structure/ui-ownership.test.ts` | **modify in U4** — allow Settings-owned accordion parity trio |
| Button accordion absence | `app/client/tests/parity/react/button.test.tsx` | **modify in U4** |
| Factory AGENTS assert | `app/client/tests/frontend-uiux-factory.test.mjs` | **modify in U1** — leave `BLOCKED_CONTRACT` wording; assert approved/`IN_PROGRESS` path |
| Graph unavailable | `app/client/src/features/graph/GraphPage.tsx` | **retain** — P9-03 no-request proof |
| Nav registry | `app/client/src/features/navigation-sidebar/constants.ts` | **retain** — Phase 1 only; no Logs/Usage/Wiki |
| Not-found | `app/client/src/app/not-found.tsx` | **add in U5** — missing today |
| Forbidden | `app/client/src/app/forbidden/page.tsx` | **retain** — pattern for shell-safe page |
| Deferred Logs route | `.references/phase-archive-2026-07-23/app/client/src/app/logs/page.tsx` | **defer** — archive only; must stay out of live `src/app` |

## API / DTO drift (must fix in U2)

| Item | Live client | Closed contract |
| --- | --- | --- |
| Admin domain shape | `available`, optional `storageSummary`, flat `embeddingProfileId` | nested `embeddingProfile`, `queryEligible`, `runtimeReady`, `controlGeneration`, `version`, `allowedActions` — **no** storageSummary |
| start/stop | `{ domain }` | `202 { operation }` |
| delete | no `If-Match` | `If-Match` from `version` |
| Member domains | `available` | `queryEligible` on `DomainSummaryDto` |

## UI / URL drift (must fix in U3)

| Item | Live | Contracted |
| --- | --- | --- |
| Section label | Knowledge Graphs | Knowledge Domains |
| Section URL | local `useState` only | `/settings?section=domains` with push/replace rules |
| Expand body | storage ProgressBar + embeddingProfileId lookup | locked facts from closed AdminDomainDto only |
| Member flash | role-gated fetch but no URL sync | derive effective section from role before paint; zero admin Domains mount for members |

## Deferred-route manifest (DRIFT-04 / U5)

| Candidate | Live tree | Required residual action |
| --- | --- | --- |
| `/logs`, `/usage`, Server status, wiki | absent from `app/client/src/app` | keep absent; archive-only references OK |
| Phase 1 nav | Chat / Library / Graph + Settings item | retain; no Phase 2/3 entries |
| Unknown path | no `not-found.tsx` | add shell-safe not-found |
| Graph | deliberate unavailable, no product-data fetch | reconfirm green |

## Amendment checklist (U1 exit)

- [x] Inventory dispositions recorded (this file)
- [x] `component-contracts.md` — Settings Domain accordion composition + locked-fact / delete rules
- [x] `interaction-state-catalog.md` — Domains accordion state rows incl. start-failed-keep
- [x] `accessibility-contract.md` — disclosure keyboard/ARIA matrix
- [x] `route-and-workspace-spec.md` — Domains section URL ownership note
- [x] `navigation-and-url-state.md` — Settings section push/replace
- [x] `content-and-microcopy.md` — Domains Settings labels / deploy start-failed-keep copy
- [x] `ui-parity-spec.md` — catalog `IN_PROGRESS` + FACTORY_READY Vitest carve-out
- [x] `docs/frontend/AGENTS.md` — amendment approved / `IN_PROGRESS` (not indefinite BLOCKED)

Checklist complete — U1 approval gate satisfied for U2. Parity trio + structural forbid flip remain U4.
