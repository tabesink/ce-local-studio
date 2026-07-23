# Frontend UI Parity Specification

Status: normative for production frontend work.

## Intent

Context Engine must feel like the original Local Studio workstation while obeying Context Engine product, authorization, and data contracts. Parity means equivalent visual hierarchy, density, pane behavior, feedback, and keyboard quality. It does not mean copying agent, filesystem, model-controller, terminal, Electron, or local-trust behavior.

When requirements conflict, precedence is:

1. prd.md and interaction-behavior-prd.md
2. Context Engine API, SSE, security, and evidence contracts
3. this specification and sibling frontend specifications
4. Local Studio source as a visual reference only

## Reference-evidence baseline

Use these Local Studio sources as the comparison baseline:

- frontend/src/app/styles/globals/tokens.css
- frontend/src/features/shell/left-sidebar*.tsx
- frontend/src/ui/
- frontend/src/features/agent/ui/agent-workspace-shell.tsx
- frontend/src/features/agent/ui/chat-pane.tsx
- frontend/src/features/agent/ui/pane-grid.tsx
- frontend/src/features/agent/ui/inspector-panel.tsx

Reference material under `.references/` is read-only visual evidence. This workspace has no usable Git provenance, so a parity baseline must record a deterministic content digest, exact reference path, Context Engine route/state, viewport, theme, screenshot path, masks, and every approved product/accessibility/security divergence. A moving directory or unrecorded reference update is not a baseline.

Use the old Context Engine client only for product route names and feature intent. Do not preserve its incomplete preview, plain-text answer rendering, hover-only menus, raw domain-ID status text, or unsafe browser assumptions.

## Required visual identity

| Element | Production rule |
| --- | --- |
| Theme | zai-dark is the first-render default; zai-light is supported without layout drift |
| Typography | Geist Sans for UI; Geist Mono for IDs, counts, timestamps, request IDs, and technical values |
| Canvas | Layered warm charcoal, not blue-gray dashboard chrome |
| Density | Compact: 30-36 px rows, 40-46 px pane/tool bars, 4 px spacing grid |
| Shape | 8-10 px controls and rows; pill actions; 24 px composer |
| Borders | One-pixel translucent hairlines; no high-contrast panel boxing |
| Accent | Blue for links, focus, live selection, and evidence anchors; semantic colors only for status |
| Elevation | Low-alpha shadows reserved for composer, popovers, drawers, and transient overlays |
| Icons | One outline family, 1.75 stroke, normally 14-16 px; icon-only controls have accessible names |

## Desktop shell contract

At viewport widths of 1024 px and above, authenticated routes use:

    +------------------+-----------------------------------+------------------+
    | discovery rail   | primary work surface              | optional inspector|
    | 240-520 px       | min-width: 0; owns main scroll    | 320-65vw         |
    +------------------+-----------------------------------+------------------+

- The rail defaults to 275 px, collapses to zero with a 40 x 36 px reveal control, and persists width per browser.
- The rail resize target is visually 1 px and has an 8 px hit area. Clamp to 240-520 px.
- Main content must never horizontally push the viewport. Every flex child at a pane boundary uses min-width: 0 and min-height: 0.
- Pane headers are 40 px. App-level toolbars are 46 px.
- Inspectors resize from their left edge and persist width by inspector kind, not by record ID.
- Closing an inspector does not clear the selected turn, evidence, document, or operation.

## Route parity matrix

| Route | Local Studio pattern retained | Context Engine specialization |
| --- | --- | --- |
| /login | centered compact card | team credentials, generic auth errors, no app rail |
| /chat | workbench thread, lifted composer, right tool pane | domains, durable conversations, governed refs, turn evidence |
| /documents | dense resource list plus detail pane | source lifecycle, safe PDF viewer, semantic evidence anchors |
| /database-visualize | compact full-height unavailable surface until enabled | reserved route; no canvas or LightRAG request until an approved graph DTO exists |
| /settings | section navigation plus compact rows | preferences for members; runtime, domains, users for admins |

No route may introduce a generic card grid when the equivalent information fits a Local Studio list, table, pane, or settings row.

## Interaction parity

- Hover may reveal convenience actions, but the same action must be reachable by focus and touch.
- Selected rows use a subtle filled surface plus a non-color indicator where ambiguity remains.
- Destructive actions require an explicit dialog naming the target and consequence. Browser confirm is not production parity.
- Loading preserves final geometry with skeletons; it must not replace the whole app shell.
- Background refresh retains existing rows and marks them stale or refreshing. It must not flash an empty state.
- Popovers close on Escape and outside pointer interaction and restore focus to the opener.
- Resizing disables text selection, uses the appropriate resize cursor, and commits the final clamped width.
- Back and Forward restore the selected resource and inspector state from safe URL state.

## Content hierarchy

| Content | Size and treatment |
| --- | --- |
| Route title | 24 px, medium, -0.02 em tracking |
| Pane title | 14-16 px, medium or semibold |
| Body and controls | 14 px |
| Dense table/list content | 12-13 px |
| Labels and metadata | 10-12 px; uppercase only for short category labels |
| Chat prose | 14 px, 1.625 line height |
| Code, request IDs, and technical values | 12 px monospace |

Assistant output uses semantic Markdown with Local Studio chat rhythm. User text remains whitespace-preserving. Never render provider Markdown as unsanitized HTML.

## Responsive parity

- Below 768 px the rail becomes a modal navigation drawer and a 56 px top bar.
- Below 1024 px an inspector becomes a right slide-over; closing it returns focus to its opener.
- Chat composer remains visible above safe-area insets and does not cover the last transcript item.
- Document list and viewer become mutually visible screens with an explicit Back to library control.
- Evidence, operation status, and destructive consequences are never removed to make a narrow layout fit.

See responsive-and-desktop-matrix.md for the exact viewport matrix.

## Forbidden drift

- Hard-coded colors, spacing, radii, shadows, or z-index values outside the token layer
- Route-specific replacements for shared controls
- Infrastructure URLs, object keys, filesystem paths, private block IDs, or provider names in member UI
- Optimistic success for lifecycle, deletion, or terminal chat state
- Color-only status, hover-only action menus, unlabeled icons, or focus removal
- Per-page mobile behavior invented independently of the shared shell
- Agent-only controls such as model picker, terminal, filesystem, browser automation, queue, or tool approval

## D0 frontend-factory catalog

This section is the sole D0 owner of the parity-manifest schema, catalog states, and readiness rules. D0 documents the factory; it does not create application fixtures or award React/runtime completion.

Catalog states are `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED_CONTRACT`, and `FACTORY_READY`. A target may become `FACTORY_READY` only after all applicable shared, HTML-static, React, accessibility, and browser assertions pass.

| Target | Owner | D0 state | Required brownfield disposition |
| --- | --- | --- | --- |
| Button | `src/ui` | NOT_STARTED | inventory existing implementations; retain/reverify, migrate, or replace in P9-01 |
| Input | `src/ui` | NOT_STARTED | inventory existing implementations; retain/reverify, migrate, or replace in P9-01 |
| StatusPill | `src/ui` | NOT_STARTED | inventory existing implementations; retain/reverify, migrate, or replace in P9-01 |
| SettingsRow | `src/features/settings-panel` | NOT_STARTED | keep as a Settings composition and reverify in P9-01 |
| Settings Domain accordion | `src/features/settings-panel` | BLOCKED_CONTRACT | approve P9-04 interaction contract before manifest, fixture, implementation, or readiness work |

The starter set is not a complete UI allowlist. Uncovered roles continue using the contracted canonical CE control; agents record a parity gap rather than inventing local chrome.

Each later target manifest is versioned and contains:

- identity: `schemaVersion`, `targetId`, `owner`, `catalogState`, `disposition`, and source-evidence digests;
- shared assertions: deterministic labels/content, variants/states, themes, viewports, semantic tokens, and geometry;
- HTML-static assertions: script-free snapshot regions, masks, and expected visual outcomes only;
- React assertions: interaction, keyboard/touch, focus/return, semantics, screen-reader behavior, reduced motion, validation/busy/disabled/status states, zoom, and responsive behavior.

The exact future output paths are:

- `app/client/tests/parity/manifests/<target-id>.json` for versioned scenarios;
- `app/client/tests/parity/html/<target-id>.html` for synthetic, script-free, network-free, non-routable static guidance;
- `app/client/tests/components/<target-id>.test.tsx` for React behavior and accessibility;
- `app/client/tests/e2e/settings-domains.spec.ts` for the production-boundary Settings proof.

HTML assets are excluded from production bundles and may contain only synthetic data. They never authorize product behavior. Live `/settings?section=domains` acceptance uses the production Next build, same-origin BFF, FastAPI, and server-produced DTOs with no request interception or mocked product response.

## Visual acceptance

Capture deterministic fixtures at 390x844, 768x1024, 1280x800, 1440x900, and 1920x1080 in dark theme; also capture 1440x900 in light theme. Capture reflow at 320x640 and 1280x800 at 400% zoom. Each enabled route must cover ready, loading, empty, safe error, and inspector-open states where applicable. `/database-visualize` covers only its deliberate unavailable state until graph enablement.

Automated comparison rules:

- No unintended element may move by more than 4 px from the approved reference.
- Every unmasked screenshot uses a 0.5% pixel-diff threshold; semantic clipping, missing controls/focus, or a layout invariant failure still fails below that value.
- Dynamic transcript, graph, timestamps, and PDF raster regions are masked; their containers are not.
- Keyboard focus screenshots are required for rail navigation, primary actions, dialogs, tabs, evidence cards, and viewer controls.
- A changed baseline requires a named product decision in the pull request; regenerating snapshots is not acceptance.

## Implementation check

A slice is parity-complete only when its component test proves variants, its browser test proves keyboard and narrow behavior, and its deterministic screenshot is approved. Functional E2E success alone is insufficient.
