# Context Engine UI Design System — Local Studio Visual Parity

> **Status:** Source of truth for Context Engine UI implementation.  
> **Visual reference:** Local Studio current `main` frontend.  
> **Priority:** Visual and interaction parity first; Context Engine business logic second; personal design preference last.

Context Engine is a RAG workbench. It uses different business objects from Local Studio—domains, documents, ingestion jobs, retrieval evidence, providers, and admin operations—but it must feel like one product family with Local Studio.

This document replaces the earlier white-canvas workbench direction. **Local Studio is a compact, dark-first Codex-like desktop workstation by default.** Context Engine must inherit that system rather than introduce an independent white SaaS/admin aesthetic.

---

## Related Documentation

| Need | Document |
| --- | --- |
| Agent implementation rules | `AGENTS.md` |
| Agent-facing UI implementation guide | `docs/design/context_engine_agent_ui_guidelines.md` |
| Frontend/backend boundary | `docs/architecture.md` |
| Context Engine domain vocabulary | `CONTEXT.md` |
| UI feature requirements | `specs/04-features/F-009-frontend-delivery/` |
| CE client port contract | `specs/04-features/F-009-frontend-delivery/ce-client-port-and-parity.md` |
| Visual parity source package | `.references/local-studio-visual-parity-package.md` |
| Old CE client (structure port) | `.references/code/context-engine/client/` |
| Local Studio reference codebase | `.references/code/local-studio/` |
| Local Studio source reference | `.references/code/local-studio/frontend/src/app/styles/globals/tokens.css` |
| Local Studio shared primitives | `.references/code/local-studio/frontend/src/ui/` |
| App UI barrel (agent import path) | `frontend/src/components/ui` (`@/components/ui`) |
| Shared kit (internal) | `frontend/src/_shared/ui` |
| Settings panel parity template | `.reference-LS-frontend/templates/nextjs-feature-demos/features/settings-panel/` |
| Appearance / coloring reference | `.reference-LS-frontend/templates/nextjs-feature-demos/features/user-preferences/` |

When instructions conflict, use this order:

1. existing Local Studio visual tokens and primitives (live inventory via `@/components/ui`);
2. this document;
3. `docs/design/context_engine_agent_ui_guidelines.md` for agent-facing implementation guidance;
4. feature-specific UI requirements;
5. generic shadcn/Tailwind defaults.

Keep `docs/design/context_engine_agent_ui_guidelines.md` aligned with this document when visual rules, reusable UI patterns, or acceptance checks change.

Do not introduce styling that conflicts with architecture or ADR constraints.

---

# 1. Governing Rule: Visual Parity, Not Visual Inspiration

Use Local Studio as the reference implementation, not as vague inspiration.

For any Context Engine UI decision, resolve in this order:

1. Is there an existing **old CE client** layout/route pattern to port (`.references/code/context-engine/client/`)?
2. Is there an existing Local Studio token?
3. Is there an existing Local Studio primitive?
4. Is there an existing Local Studio screen pattern for restyle?
5. Can a narrow variant extend that primitive without adding a new design language?
6. Only then add a Context Engine-specific component.

Port structure from old CE client. Restyle with Local Studio. See `specs/04-features/F-009-frontend-delivery/ce-client-port-and-parity.md`.

Never start from generic Tailwind, generic shadcn, a white dashboard template, or a marketing-page aesthetic.

## Non-Negotiables

- Default theme is `zai-dark` / dark-first.
- Light theme is the matching `zai-light` system.
- Use Local Studio’s token aliases: `--ui-*` for component implementation, plus the compatible `--bg`, `--fg`, `--surface`, `--rail`, `--border`, `--accent`, `--dim`, `--ok`, `--warn`, and `--err` aliases where existing primitives use them.
- Never hard-code a color, spacing value, radius, or row height in a feature when the token system already expresses it.
- Do not make Context Engine a white-canvas app by default.
- Do not use saturated color cards, gradients, decorative illustrations, large rounded surfaces, or full-pill controls unless a Local Studio reference already uses them.
- Preserve dense workstation behavior: small controls, calm surfaces, controlled contrast, compact metadata, and information-rich rows.
- New Context Engine concepts change labels and data, not the foundational visual grammar.

---

# 2. Reference Implementation

The source implementation to preserve is available in this repo under `.references/code/local-studio/`. Use it as read-only reference code for concrete tokens, primitives, shell geometry, and interaction patterns:

```text
.references/code/local-studio/frontend/src/app/styles/globals/tokens.css
.references/code/local-studio/frontend/src/app/layout.tsx
.references/code/local-studio/frontend/src/lib/themes.ts
.references/code/local-studio/frontend/src/ui/
.references/code/local-studio/frontend/src/features/shell/
.references/code/local-studio/frontend/src/features/agent/
.references/code/local-studio/frontend/src/features/settings/
```

Do not edit the reference checkout while implementing Context Engine. Copy or adapt patterns into live project files only when the task requires it.

## Canonical Fonts

```css
--font-geist-sans
--font-geist-mono
```

- Default sans: **Geist**
- Default monospace: **Geist Mono**
- Fallback sans: `system-ui, sans-serif`
- Fallback mono: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`

Use Geist Sans for application chrome, messages, labels, buttons, tables, and page titles.  
Use Geist Mono for code, API routes, model names, paths, IDs, timestamps, token counts, durations, file names, commands, and payloads.

Do not introduce Inter, Roboto, Arial, system-only typography, or a new mono font as the default Context Engine visual language.

Exception (F-009 appearance picker only): Settings → General may offer Inter / System as selectable font families for Local Studio control parity. The product default remains Geist; do not load Inter as the app default.

---

# 3. Theme Contract

## 3.1 Dark Mode — Default

Use `zai-dark` as the default Context Engine theme.

| Role | Canonical token/value | Usage |
| --- | --- | --- |
| App canvas | `--color-background: #0f0f0f` | Root canvas and central work area |
| Header | `--color-header: #101010` | Compact top bars |
| Panel | `--color-panel: #111111` | Structural side/secondary areas |
| Sidebar / rail | `--color-sidebar: #191919` | Navigation rail and dense left surfaces |
| Raised card | `--color-card: #202020` | Only where a raised surface is needed |
| Popover | `--color-popover: #222222` | Menus, dialogs, popovers |
| Input | `--color-input: #242424` | Inputs, selects, low-elevation controls |
| Subtle surface | `--color-surface: #ffffff0c` | Hoverable/quiet internal surfaces |
| Hover | `--color-hover: #ffffff0f` | Hover background |
| Selected | `--color-selected: #ffffff17` | Selected row, active local context |
| Border | `--color-border: #ffffff14` | Default 1px separator/border |
| Hover border | `--color-border-hover: #ffffff24` | Focus or hover boundary |
| Primary foreground | `--color-foreground: #e7e7e7` | Standard text |
| Brand / primary | `--color-brand: #ffffff` | Main primary action / accent |
| Link / information | `--link: #7ea1c8` | Links, file/URL chips, live status |

Dark mode must read as layered charcoal, not pure black plus bright-blue product chrome.

## 3.2 Light Mode — Equivalent System

Use `zai-light` only as the matching Local Studio light theme. It is not a separate design direction.

| Role | Canonical token/value | Usage |
| --- | --- | ---|
| App canvas | `--color-background: #f4f5f5` | Root canvas |
| Raised alternate canvas | `--color-background-win-alt: #e9ebec` | Secondary window/pane areas |
| Header / panel / card / popover / input | `#fbfbfb` | Main elevated surfaces |
| Sidebar / rail | `--color-sidebar: #eceeee` | Navigation rail |
| Subtle surface | `--color-surface: #0d0d0d08` | Quiet grouping |
| Hover | `--color-hover: #0d0d0d0b` | Hover background |
| Selected | `--color-selected: #0d0d0d12` | Selected local state |
| Border | `--color-border: #0d0d0d1a` | Default 1px separator/border |
| Hover border | `--color-border-hover: #0d0d0d24` | Focus or hover boundary |
| Brand / primary | `--color-brand: #000000` | Primary action / accent |
| Link | `--link: #6b8db5` | Links and information state |

The light theme is warm-neutral/gray, not pure white with blue SaaS panels.

## 3.3 Semantic Color

Semantic color is local, restrained, and never the main page background.

| State | Dark | Light | Use |
| --- | --- | --- | --- |
| Information / active | `#7ea1c8` | Local Studio sky token | live status, links, active underline, non-destructive attention |
| Success | `#46bf72` | `#1e8a3e` | complete, ready, healthy, indexed |
| Warning | `#d48a4c` | `#e07b00` | paused, queued with attention, degraded |
| Danger | `#ff5c5c` | `#e03131` | failed, blocked, destructive action |
| Neutral | foreground-muted token | foreground-muted token | idle, stopped, unavailable, unknown |

Use semantic color through:

- `StatusDot`,
- `StatusPill`,
- a text accent,
- a 1–2px local border,
- a small icon,
- a slim progress fill,
- a compact error/success row.

Do **not** use semantic color as a full-card fill, page section background, navigation rail color, hero treatment, or broad dashboard decoration.

---

# 4. Typography

## 4.1 Core Scale

Use the Local Studio CSS variable ramp. These are the source sizes at `--ui-scale: 1`.

| Token | Base size | Primary role |
| --- | ---: | --- |
| `--fs-2xs` | 9px | micro metadata only |
| `--fs-xs` | 10px | dense metadata, counts, compact state |
| `--fs-sm` | 11px | row metadata, dense labels |
| `--fs-md` | 12px | compact controls and navigation |
| `--fs-base` | 13px | normal workstation body text |
| `--fs-lg` | 14px | readable body, tabs, prominent labels |
| `--fs-xl` | 16px | page/navigation emphasis |
| `--fs-2xl` | 18px | page title |
| `--fs-3xl` | 20px | large page title / key empty state |
| `--fs-4xl` | 24px | rare emphasis only |
| `--fs-display` | 34px | startup or exceptional display treatment only |

Use `text-[length:var(--fs-*)]` or the shared component implementation. Do not assume generic Tailwind `text-sm` maps to the product’s compact scale.

## 4.2 Weight and Leading

```css
--weight-normal: 400;
--weight-medium: 500;
--weight-strong: 600;
--leading: 1.5;
--leading-tight: 1.25;
```

Rules:

- Use 400 for body, metadata, normal labels.
- Use 500 for active navigation, section headers, tabs, selected values.
- Use 600 for compact button labels and decisive page titles.
- Do not default to 700/800/900.
- Use `--leading` for body/multi-line explanation.
- Use `--leading-tight` for titles, compact rows, and single-line control labels.
- Make hierarchy through position, spacing, and contrast before increasing weight or size.

## 4.3 Text Roles

| Role | Font | Size | Weight | Notes |
| --- | --- | ---: | ---: | --- |
| Page title | Geist Sans | 18–20px | 500–600 | Short and functional |
| Section heading | Geist Sans | 13–16px | 500 | Quiet, not display-like |
| Navigation item | Geist Sans | 12px | 400–500 | Dense and scannable |
| Button label | Geist Sans | 12–14px | 600 | Existing size variant decides exact size |
| Body | Geist Sans | 13–14px | 400 | Explanatory content |
| Table primary cell | Geist Sans | 12–13px | 400–500 | Avoid oversized rows |
| Metadata | Geist Mono | 9–12px | 400–500 | Paths, IDs, timing, model/version |
| Code/API content | Geist Mono | 12–14px | 400 | Payloads, snippets, commands |
| Section label / overline | Geist Sans | 11–13px | 500 | Use only where existing pattern supports `0.16em` tracking |

No generic all-caps taxonomy. All caps is reserved for small, pre-existing section-label patterns.

---

# 5. Geometry, Spacing, and Shape

## 5.1 Base Rules

```css
--space-base: 4px;
--radius-base: 7px;
--border-width: 1px;
--ui-control-h: 28px;
--row-h: 28px;
--row-h-sm: 24px;
```

Use a 4px-based rhythm:

```text
4, 8, 12, 16, 20, 24, 28, 32
```

Do not make Context Engine spacious by default. It is a desktop workbench. Density should remain readable but operational.

## 5.2 Radius Ramp

At the default 7px base radius:

| Token | Approx. value | Use |
| --- | ---: | --- |
| `--rad-2xs` | 1.75px | exceptional micro details |
| `--rad-xs` | 3.5px | tiny local elements |
| `--rad-sm` | 5.25px | compact inner elements |
| `--rad-md` | 5.25px | active rows, segmented items |
| `--rad-lg` | 7px | buttons, inputs, panels |
| `--rad-xl` | 10.5px | composer / larger contained areas |
| `--rad-2xl` | 14px | exceptional large container |
| `--rad-3xl` | 21px | avoid unless reference pattern needs it |
| `--rad-full` | 9999px | never default UI chrome |

Controls and active rows should look compact, not soft or bubbly.

## 5.3 Shell Geometry

| Region | Canonical geometry |
| --- | --- |
| Expanded sidebar | `224px` |
| Collapsed sidebar | `48px` |
| Standard dense row | `28px` |
| Small dense row | `24px` |
| Standard compact inline control | `28px` |
| Right detail panel | full width on small screens; `min(560px, calc(100vw - 64px))` on desktop |
| Conversation thread max width | `900px` |
| Composer width at desktop | `clamp(25vw, 46rem, 50vw)` |

Preserve the workstation shell:

```text
left navigation rail | primary work canvas | optional right detail panel
```

Use the right detail panel for evidence, source details, document metadata, operation details, model/provider detail, and logs. Do not create a competing card-heavy dashboard to hold these details.

---

# 6. Surface, Border, and Elevation Rules

## 6.1 Surfaces

Use hierarchy through close dark (or light) neutrals, not cards inside cards.

| Layer | Dark | Light | Typical use |
| --- | --- | --- | --- |
| Root canvas | `--color-background` | `--color-background` | page base |
| Rail | `--color-sidebar` | `--color-sidebar` | persistent navigation |
| Structural panel | `--color-panel` | `--color-panel` | side and secondary containers |
| Raised component | `--color-card` | `--color-card` | modal/card only where needed |
| Input/control | `--color-input` | `--color-input` | editable controls |
| Quiet grouping | `--color-surface` | `--color-surface` | local hover/selected support |

Use `1px` tokenized borders sparingly. Dense lists and tables should prefer separators and row hover states rather than individual floating cards.

## 6.2 Shadows

Default: no shadow.

Permitted reference behavior:

- `shadow-sm` on active segmented-control items.
- composer/floating work tray only:
  - dark: `0 18px 42px rgba(0, 0, 0, 0.42)`
  - light: `0 12px 36px rgba(0, 0, 0, 0.06)`

Do not introduce dashboard-card shadows, floating tile shadows, or multi-level elevation systems.

---

# 7. Component Grammar

Build from shared primitives before creating Context Engine variants.

## 7.1 Buttons

Use the shared `Button` contract.

| Variant | Visual role | Use |
| --- | --- | --- |
| `primary` | high-contrast foreground/background inversion | create, run, submit, confirm |
| `secondary` | bordered low-emphasis action | normal utility action |
| `danger` | red text, quiet danger treatment | delete, stop destructive action |
| `ghost` | low-chrome local action | secondary in-row action |
| `icon` | compact icon-only action | panel/header/row tool |

Rules:

- Base shape: `rounded-lg` / 7px token behavior.
- Use 600 label weight.
- Use compact sizes. Do not default to 40–44px SaaS controls.
- Primary and destructive actions within a group must share height.
- Do not use broad blue primary buttons. Primary is foreground-inverted: white on dark / black on light.
- Avoid full-pill buttons.

## 7.2 Inputs and Selects

Use the existing `Input`/`Select` patterns.

- Standard compact control target: `h-7` / 28px.
- Shape: `rounded-md` or component-owned radius token.
- Surface: `--color-input` or `--ui-bg`, never bright white in dark mode.
- Border: `--ui-border`; focused border uses the restrained hover/focus token.
- Labels are compact, readable, and above/adjacent per shared form primitive.
- Use a code/mono treatment only when the value itself is developer data.

Do not replace Context Engine settings with underline-only white-canvas inputs. That belongs to the retired visual direction, not Local Studio parity.

## 7.3 Tabs and Segmented Controls

Use three existing patterns only:

| Pattern | Use |
| --- | --- |
| Underline tabs | primary content sections within a page/detail surface |
| Rounded-md pill tabs | local choice inside a contained panel; still compact, not full-pill |
| Button-group tabs | explicit mode/state choice where boundaries improve clarity |
| Segmented control | small binary or small set choices such as theme/mode/filter |

Underline tabs use an active 2px accent border; inactive tabs remain muted.  
Segmented active items use surface contrast and only a small reference shadow.

Do not invent a fourth tab style for a Context Engine screen.

## 7.4 Lists, Tables, and Rows

Use list groups/tables as the default information-dense pattern.

- Rows target 24px or 28px height whenever content allows.
- Primary data is left-aligned and readable.
- Status, compact metadata, and actions align to logical columns/right edge.
- Use muted mono for IDs, model names, paths, token counts, timestamps, durations.
- Active rows: restrained selected surface plus `rounded-md` where the reference component applies it.
- Hover: tokenized hover surface, not an animated card lift.
- Do not wrap every row in a card.

## 7.5 Status Dots and Status Pills

Use `StatusDot` and `StatusPill` semantics.

| Tone | Context Engine examples |
| --- | --- |
| `default` | stopped, idle, unknown, unavailable, not applicable |
| `info` | starting, running, indexing, querying |
| `good` | ready, complete, indexed, healthy, setup check `ok` |
| `warning` | paused, queued, degraded, needs review, setup check `warning`, host-dev N/A |
| `danger` | failed, blocked, deleting failure, unsafe, setup check `error` |

Use dot form where text already communicates state. Use badge form only when the state label must remain visible in a dense list.

No full-color status cards. Pair status color with text or icon for accessibility.

## 7.6 Cards and Panels

Cards are exceptions, not the base layout.

- Use standard padding: `p-3`, `p-4`, or `p-6` only through the shared `Card` contract.
- Use a card for a modal interior, concentrated summary, one-off choice, or feature boundary.
- Use dividers/list rows for most settings, jobs, documents, and operations.
- Avoid nested cards.
- A page should feel like a continuous workstation surface, not a grid of dashboard tiles.

## 7.7 Modals, Drawers, and Right Detail Panels

Use:

- Modal for confirmation, creation, destructive actions, short focused configuration.
- Drawer for mobile/narrow-width contextual work.
- Right detail panel for document details, source/evidence detail, ingest job traces, operation log, domain metadata, provider model detail.

Do not make users leave a query or document list just to inspect supporting context.

## 7.8 Progress

Use the shared progress style:

- compact,
- thin,
- neutral track,
- semantic current-state fill,
- exact numeric/word label nearby for longer jobs.

A job may show:

```text
StatusDot + status text | 43% | 11 / 26 chunks | elapsed time
```

Do not use giant animated loaders, large gradient bars, or color-heavy process cards.

---

# 8. Context Engine Pattern Mapping

## 8.1 Domains / Workspaces

**Reference pattern:** sidebar/list row + page header + optional right detail panel.

- Domain list belongs in the left rail or an existing list-group surface.
- Selected domain uses the Local Studio selected row treatment.
- Domain metadata uses muted mono: ID, embedding model, created time.
- Lifecycle status uses `StatusDot`/`StatusPill`.
- Start/Stop/Delete actions use the existing compact button hierarchy.
- Delete remains quiet danger text until an explicit confirmation modal.

Do not make domains into large colorful dashboard cards.

## 8.2 Domain Lifecycle

| Backend state | Tone | UI treatment |
| --- | --- | --- |
| created / stopped | `default` | neutral dot + “stopped” |
| starting | `info` | info dot + “starting”; optional thin progress |
| ready | `good` | green dot + “ready” |
| failed | `danger` | red dot + error summary + “View details” |
| deleting | `warning` or `info` | compact pending indicator + disabled destructive action |
| deleted | not shown in active list | remove after backend confirmation |

Never infer lifecycle from client-side temporary state. FastAPI is the source of truth.

## 8.3 Documents and Ingestion

**Reference pattern:** port old CE client `/documents` layout — table list + **inline PDF preview panel** (50% desktop split, mobile drawer). Restyle with Local Studio tokens.

Document row:

```text
status dot | title / filename | parser | prep/index state | updated | row actions
```

Row click opens `DocumentPreviewPanel` → `DocumentPdfPreview` (blob URL + native `<object>`). Do not move preview to a nested `/documents/[id]` route.

Ingestion state:

- queued → warning/default
- parsing/indexing → info
- indexed → good
- failed → danger
- cancelled → default/warning based on backend contract

The right panel may contain:

```text
PDF preview (<object>) or safe metadata when preview unavailable
Document title · parser · status
prep/index progress · timestamps · compact diagnostics
tabs: Details | Operations (when API provides)
```

Avoid nested upload cards. Use one focused upload dialog with direct progress and cancel action.

## 8.4 Retrieval / Query / Chat

**Reference pattern:** port old CE client `LightRagChatShell` two-column layout; restyle composer/messages with Local Studio tokens.

- Center canvas holds conversation/query result.
- Collapsible/resizable **ContextPanelShell** with tab registry; v1 **`context`** tab ports session context and source inspector from old CE (`context-panel-tabs.md`).
- Query input/composer follows the same dark raised composer grammar.
- Model, domain, and retrieval mode controls stay compact and local.
- Response uses readable sans body; copied technical values use mono.
- Sources/citations are compact inline references and open in the right detail panel.
- A source drawer/panel should show document, chunk, path, evidence content, and associated image/table if supplied.
- Retrieval state is shown by restrained status/progress, not a colored “AI” hero panel.

## 8.5 Settings Panel

**Reference pattern:** Local Studio settings shell — left `SectionNav` + compact content column — via `.reference-LS-frontend/templates/nextjs-feature-demos/features/settings-panel/` and the shared `SettingsLayout` / `SettingsGroup` / `SettingsRow` primitives.

### Shell

- One Settings page inside the app shell; section switching is in-panel (state or hash), not a competing top-level destination per section.
- Left sticky section nav with sky accent on the active item; content column stays dense (~640px reference width), not a full-bleed dashboard.
- Admin-only sections stay role-gated in the nav; non-admins keep personal sections only.
- Use `SettingsGroup` + `SettingsRow` / `SettingsFactRows` for lists and facts. Prefer dividers and rows over cards.
- Reload/status chrome stays quiet (header status text + compact reload), matching the reference layout.

### Provider and model (admin)

- Use standard form rows, selects, tokenized inputs, concise help text, and right-aligned save/test actions.
- API keys must use password/masked input patterns and never be rendered as normal metadata.
- Locked embedding model uses disabled/muted input plus an explanation, not a hidden setting.
- Model/provider status uses standard status dot/pill.

Do not introduce large marketing-style provider cards or logo grids.

### Setup checks (admin)

**Reference pattern:** settings-panel `setup` section — `SettingsGroup` titled **Setup checks**, one `SettingsRow` per check, monospace detail, `StatusPill` for status.

Visual parity means the **chrome and row grammar**, not Local Studio fixture content:

| Keep from LS | Replace for CE |
| --- | --- |
| Section id/label **Setup**, `SettingsGroup` “Setup checks” | Pillars: `postgres`, `migrate`, `api`, `worker`, `frontend` (compose stack vocabulary) |
| `SettingsRow` + mono detail + `StatusPill` | Safe status copy / reason codes — never live URLs, filesystem paths, runtime targets, or raw healthcheck dumps |
| Tones: `ok` → `good`, `warning` → `warning`, `error` → `danger` | Host-dev vs compose: missing compose-only pillars are N/A/warning, not false danger |

Rules:

- Setup is a **read-only readiness board**, not the Local Studio setup wizard and not an operator console (no Docker controls, logs browser, storage browser, or node management in this surface).
- Prefer dependency order in the list (`postgres` → `migrate` → `api` / `worker` → `frontend`). Treat migrate as a one-shot gate; treat worker as heartbeat freshness, not “container exists.”
- Optional overall readiness line may sit above the checklist; do not turn Setup into a status-page dashboard with uptime charts or service cards.
- Detail text uses Geist Mono at `--fs-xs` when showing machine-safe tokens; never paste controller URLs, `api:8000`, storage roots, or heartbeat file paths into the UI.
- Backend remains the source of truth for check status. Frontend maps contracted fields to pills; it does not invent health by probing Docker or private runtimes.

Do not ship LS fixture strings (`Pi binary`, `Controller reachable` with `http://…`, `~/models`, local data dirs) as live CE Setup content.

## 8.6 Operations and Logs

**Reference pattern:** table/list with detail inspection.

- Operations list is an admin work surface.
- Each row: status, operation type, domain, started/finished time, operator, detail action.
- Details open in right panel.
- Logs and payloads use Geist Mono and quiet code containers.
- Destructive/administrative capability remains visibly role-limited, but server authorization decides access.

## 8.7 Empty, Loading, Error, and Permission States

| State | Required treatment |
| --- | --- |
| Empty | short functional explanation + one primary next action; no illustration by default |
| Loading | local skeleton/placeholder or compact progress; retain page geometry |
| Background refresh | small status/refresh indicator, no page flash |
| Error | `ErrorBox` / danger tone + concise problem + recovery action |
| Permission denied | neutral/danger compact explanation; no pretend-disabled success UI |
| No domain selected | preserve work canvas, guide selection or creation without a large onboarding card |

---

# 9. Motion and Interaction

Motion is brief and functional.

Allowed:

- opacity/background transition for hover,
- disclosure expansion/collapse,
- row insertion/removal,
- local progress updates,
- panel/drawer open and close.

Avoid:

- bounce easing,
- card lift,
- pulsing decoration,
- large gradient animation,
- automatic route-level movement,
- “AI magic” animated visual effects.

The Local Studio animated gradient treatment is an exceptional startup treatment. Do not use it in normal Context Engine surfaces.

---

# 10. Accessibility and State Integrity

- Do not communicate state by color alone.
- Keep keyboard focus visible through tokenized borders/rings.
- Use real labels for inputs; placeholders do not replace labels.
- Icon-only controls need accessible names/tooltips.
- Preserve contrast in both themes.
- Do not disable controls solely because the frontend assumes authorization; FastAPI remains the authority.
- Loading, failed, and completed lifecycle states must remain understandable to screen-reader and keyboard users.

---

# 11. Implementation Rules for Coding Agents

## 11.1 Token First

Before writing a class, check whether the value already exists:

```text
color → --ui-* / --color-* / legacy alias
type → --fs-* / --font-geist-*
radius → --rad-*
spacing → 4px rhythm
height → --ui-control-h / --row-h / --row-h-sm
state → StatusDot / StatusPill / existing status tone
layout → AppPage / PageHeader / ListGroup / Table / Drawer (right detail = Drawer or compose; see gaps)
```

## 11.2 Primitive First

**Authority split**

- This document owns visual parity rules, coloring consumption, import path, and gap policy.
- Live primitive inventory is whatever `frontend/src/components/ui` (`@/components/ui`) exports. Do not treat a hand-maintained name dump in this file as the inventory source of truth.
- `@/_shared/ui` is the internal shared kit behind that barrel. New agent/feature UI must import from `@/components/ui` only (going forward). Existing `@/_shared/ui` call sites may remain until a later migration.

**Import path**

```ts
import { Button, SettingsGroup, StatusPill, PageState } from "@/components/ui";
```

Do not add new `@/_shared/ui` imports in feature or app code. Do not deep-import thin legacy files under `components/ui/*.tsx` for shared kit names when the barrel already exports them.

**Coloring**

- Components paint with applied theme tokens (`--ui-*`, `--fs-*`, `--rad-*`, kit tone APIs).
- Appearance Mode / Theme catalog / token overrides belong to the user-preferences / central theme runtime. Feature chrome must not set `data-theme` or appearance CSS variables, invent a palette, or hard-code colors/radii when tokens exist.
- Tiny bordered theme swatches belong on the appearance surface only — not a second design language in feature chrome.
- Reference: `.reference-LS-frontend/templates/nextjs-feature-demos/features/user-preferences/`.

**Available primitives**

Discover names from the `@/components/ui` barrel exports. Representative kit names include `Button`, `Input`, `Select`, `Textarea`, `Checkbox`, `ToggleSwitch`, `SegmentedControl`, `Tabs`, `Card`, `Alert`, `Table` / `THead` / `TBody` / `TRow` / `TH` / `TCell`, `ListGroup` / `ListRow`, `SettingsLayout` / `SettingsGroup` / `SettingsRow` / `SettingsFactRows` / `SettingsNotice`, `AppPage` / `PageHeader`, `UiModal`, `Drawer`, `ProgressBar`, `StatusDot` / `StatusPill`, plus CE-only `ErrorBox`, `PageState`, `AppLogo`.

**Naming aliases**

| Prefer (exported) | Do not invent |
| --- | --- |
| `UiModal` | `Modal` as a separate primitive |
| `Drawer` / compose | `RightDetailPanel` as a kit export |
| Label + `Input` / `SettingsInput` rows | `FormField` as a kit export |

**Not in kit yet**

These Local Studio / template patterns are **not** exported as shared primitives. When needed, adapt only a cited named template under `.reference-LS-frontend/templates/nextjs-feature-demos/`, still under token/coloring rules — do not invent a parallel component API or palette.

| Gap | Cite |
| --- | --- |
| Controllers-style accordion / expandable list rows + storage bars (Knowledge Graphs evidence) | `features/environment-controls/` |
| Settings shell / SectionNav grammar | `features/settings-panel/` |
| Appearance Mode / Theme / token editor | `features/user-preferences/` |

A Context Engine-specific component may compose barrel primitives but must not recreate their token system.

## 11.3 Variant Rule

Create a new variant only when:

1. an existing primitive cannot express the required accessible state,
2. the behavior will appear in more than one Context Engine feature,
3. it is documented here or added here in the same change,
4. it inherits tokens and geometry from the base primitive.

Do not create a variant for one isolated screen.

## 11.4 Prohibited Drift

Do not add:

- `rounded-full` as a default,
- arbitrary `bg-*` brand colors,
- page-level gradients,
- shadows on ordinary cards,
- 32–44px controls where 28px dense controls fit,
- new UI font families,
- oversized headings,
- per-feature CSS variables that duplicate global tokens,
- generic shadcn default colors/radius when Local Studio tokens already exist,
- nested panels just to create visual separation.

---

# 12. Visual Acceptance Checklist

Before merging a Context Engine UI change, verify:

## Theme

1. Dark mode uses the Local Studio dark token system by default.
2. Light mode uses its matching Local Studio light tokens.
3. No hard-coded feature color overrides a semantic/global token.

## Typography

4. Geist / Geist Mono are used correctly.
5. Compact `--fs-*` scale is used, not arbitrary browser/default sizes.
6. Weight hierarchy stays within 400 / 500 / 600.
7. Paths, IDs, commands, models, timestamps, and payloads use mono.

## Geometry

8. Compact rows and inline controls respect 24px/28px geometry.
9. Sidebar, detail panel, and central canvas preserve workstation proportions.
10. Radius values come from `--rad-*`; full pills are exceptional.

## Components

11. Existing primitives are used before new components.
12. Status uses dots/pills and text, not colored panels.
13. Tables/lists use dividers and quiet selection, not card grids.
14. Modals and right detail panels are used for focused/contextual work.
15. Primary action remains high-contrast monochrome, not default blue.

## Behavior

16. Hover, focus, disabled, loading, error, empty, and permission states are complete.
17. Long-running state uses compact progress and backend-confirmed status.
18. No visual embellishment hides operational information.

## Visual Regression

19. Compare changed screens to reference behavior at:
    - `1440 × 900` dark,
    - `1440 × 900` light,
    - `1280 × 800` dark,
    - narrow-width layout for changed responsive surfaces.
20. Review screenshot differences for:
    - font rendering,
    - density,
    - surface stack,
    - border contrast,
    - control height,
    - radius,
    - sidebar/detail panel width,
    - status semantics,
    - accidental generic shadcn styling.

---

# 13. Short Agent Prompt

Use this for feature implementation:

> Build this Context Engine surface with Local Studio visual parity. Import shared UI only from `@/components/ui` (live inventory). First inspect `.references/code/local-studio/` and the closest `.reference-LS-frontend/templates/nextjs-feature-demos/features/<slice>/` template for tokens, shell geometry, or screen pattern. Use the dark-first theme runtime / user-preferences token system (`--ui-*`, Geist, compact `--fs-*`, 4px rhythm, dense 24/28px controls). Prefer barrel primitives (`SettingsLayout`/`SettingsGroup`/`SettingsRow`, `StatusPill`, `UiModal`, …). If a pattern is marked not in kit yet (e.g. Controllers accordion rows), cite and adapt a named template — do not invent colors or a parallel component API. Preserve the workstation shell. No generic dashboard, gradients, full pills, or feature-local `data-theme` writes.
