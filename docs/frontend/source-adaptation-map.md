# Frontend Source Adaptation Map

Local Studio is design/engineering evidence, not a runtime dependency or product authority. Fork only the minimum element into Context Engine-owned code, retain provenance, then verify it against Context Engine contracts.

Source roots:

```text
.references/code/local-studio/frontend/src/
.references/ce-local-studio-docs/
.references/ce-local-studio-trim-feature-review.md
app/client/src/
```

## Port/adapt decisions

| Reference anchor | Decision | Context Engine target and required change |
| --- | --- | --- |
| Local Studio `app/styles/globals/tokens.css` | fork | `styles/tokens.css`; prune agent/runtime tokens, document mappings, verify AA contrast |
| Local Studio `ui/button.tsx`, `input.tsx`, `textarea.tsx`, `select.tsx`, `checkbox.tsx` | fork/adapt | `ui/`; preserve compact geometry, add CE variants and accessibility tests |
| Local Studio `ui/card.tsx`, `table.tsx`, `tabs.tsx`, `status.tsx`, `page-state.tsx` | fork/adapt | shared product primitives; exhaustive safe status mapping |
| Local Studio `ui/modal.tsx`, `drawer.tsx`, `right-detail-panel.tsx` | adapt | dialogs, mobile navigation, PDF/Evidence panes; fix focus trap/return and responsive behavior |
| Local Studio `features/shell/left-sidebar*` | adapt | role-aware CE navigation; omit Local Studio Status/Models/Usage/agent routes |
| CE v1 `features/navigation-sidebar/*` | model | route registry, 188-320 px resize pattern; reconcile with final parity shell spec |
| Local Studio `features/agent/ui/chat-pane*`, `agent-composer-*`, `assistant-markdown.tsx` | adapt presentation only | CE transcript/composer; remove model, tool, filesystem, queue, steer, and host concepts |
| CE v1 `features/chat-shell/ChatShell.tsx`, `EvidencePanel.tsx` | model/replace runtime | retain turn-scoped panel geometry; add safe deep-link contract and canonical stream store |
| Local Studio `features/agent/runtime/runtime-cursor.ts` | port concept | separate received/applied cursors; CE resumes after atomically applied sequence |
| Local Studio `features/agent/runtime/session-runtime-controller.ts` | model | one interruptible subscription controller; replace Pi/status logic with CE SSE schemas |
| Local Studio `features/agent/runtime/runtime-schema.ts` | port concept | strict versioned boundary decoding; use CE event union/generated DTOs |
| Local Studio `lib/api/create-api-client.ts` | port composition | modular capability clients; fixed same-origin base and request-scoped server credentials |
| Local Studio `lib/api/core.ts` | rewrite | keep timeout/parser lessons; remove backend override, API key, permissive legacy frames, broad mutation retry |
| CE v1 `features/documents/DocumentsPage.tsx` | adapt structure | single `/documents`, table + 50% inline viewer/mobile drawer; use safe content/anchor APIs |
| F-009 `ce-client-port-and-parity.md` | model | preserve CE route names and source/graph interaction geometry |
| Local Studio `features/settings/*` | adapt grammar | role-specific Phase 1 settings DTOs only; credential fields remain write-only |
| Local Studio quality scripts | port/extend | import direction, cycles, dead code, duplication, API/SSE snapshots, storage/privacy scans |

## Explicit rejection

Do not port or expose:

- `features/agent` filesystem, terminal, Git, browser, plan, canvas, comments, plugins, skills, queue, steer, compact, Pi events, project/cwd, or session JSONL authority;
- Electron/preload/native bridges, desktop secret vaults, local project stores, or host paths;
- browser-selected controller/runtime URLs, API keys, provider/model/retrieval controls, or automatic backend fallback;
- Local Studio controller, SQLite persistence, inference lifecycle, OpenAI proxy, model recipes, hardware, or usage surfaces without a new CE contract;
- Local Studio `features/logs/*`, Logs, Usage, Server status, audit/diagnostic browsers, or observability navigation in Phase 1; retain only as reference evidence for `../future/observability-layer.md`;
- CE v1 private IDs, source-block fetches, raw preview path, useEffect-heavy state authority, or old `stage/token/evidence/done` event assumptions;
- copying an entire feature directory “for parity.” Every copied file needs an active target owner.

## Adaptation procedure

1. Record a deterministic source digest, file, license, and target file in `THIRD_PARTY_NOTICES`/provenance ledger. Record a commit only when usable Git provenance actually exists.
2. Copy the smallest primitive/algorithm, rename it for Context Engine vocabulary, and remove unrelated branches/assets.
3. Replace DTOs and transport with generated CE contracts before rendering it.
4. Replace hard-coded styling with approved CE token mappings; do not preserve obsolete white-canvas or agent-only styles.
5. Add unit, accessibility, visual, privacy, and browser tests tied to behavior case IDs.
6. Run structural gates proving `app -> features -> ui/lib`, no reverse imports, no reference-tree runtime import, and no forbidden vocabulary/API surface.

## Acceptance checklist

- Runtime bundle contains no import/path/package dependency on `.references` or Local Studio packages.
- Source licenses and material forks are attributable.
- Browser traffic is same-origin CE API only.
- Live/replay use one CE reducer and safe DTOs.
- Required Local Studio geometry/tokens pass visual baselines; CE route/role behavior passes interaction cases.
- A parity difference is either fixed or recorded as an intentional Context Engine product/accessibility/security divergence.
