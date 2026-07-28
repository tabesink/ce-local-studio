# P9-06 — Full workstation HTML gallery evidence

Date: 2026-07-28  
Plan: `docs/plans/2026-07-28-002-feat-full-workstation-html-gallery-plan.md`

## Delivered

- U1: Option A authority, full register schema, starter `layer` backfill.
- U2: in-use Select, ToggleSwitch, UiModal, PageState, and ErrorBox trios.
- U3: AppShell, NavigationRail, and PaneHeader trios.
- U4: chat ConversationRail, Transcript, Composer, EvidenceInspector, and
  combined workbench trios.
- U5: DocumentLibrary, DocumentViewer, SettingsNav, SettingsGroup, Login, and
  graph-unavailable trios.
- U6: remaining contracted primitive/shared roles, SourceOperationPanel, the
  script-free local `tests/parity/index.html`, and the hard catalog gate.

The final register contains 39 targets and exactly 39 manifest / HTML / React
trios. Ten residual primitive/shared test files passed individually (37
assertions); five residual composition files passed individually (10
assertions). U3, U4, and U5 focused suites also passed individually. The hard
catalog gate passed 4/4, factory + UI ownership gates passed 10/10, and
`npm run typecheck` passed.

HTML fixtures are synthetic, script-free, network-free, non-routable, and are
not product authority. React tests own behavior and accessibility. P12-07 still
owns production-route screenshots and live Settings F3 through Next/BFF/FastAPI.

## Verification strategy

Vitest files are run one at a time with one worker and a 1 GiB heap. This avoids
the host OOM observed when all jsdom suites shared a large aggregate run:

```bash
NODE_OPTIONS=--max-old-space-size=1024 \
  npx vitest run tests/parity/react/<target>.test.tsx --maxWorkers=1
```

Node authority and structure gates:

```bash
node --experimental-strip-types --test \
  tests/frontend-uiux-factory.test.mjs \
  tests/structure/parity-catalog.test.ts \
  tests/structure/ui-ownership.test.ts
```

The aggregate `npx vitest run` was intentionally not used as completion
evidence: on this host it exhausted the Node heap. Focused per-file runs avoid
cross-file jsdom accumulation and expose assertion failures without raising the
heap limit beyond 1 GiB.

## Boundary

- No product route, DTO, SSE event, or browser authority was added.
- No graph canvas or LightRAG request was added.
- No P11-04 Evidence attach/suggest target was added.
- Playwright production-boundary route matrix remains P12-07.
