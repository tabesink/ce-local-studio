# Frontend Component Contracts

Status: normative for component ownership, variants, states, and accessibility.

## Layer boundary

    app routes -> feature compositions -> ui primitives
                       |
                       +-> feature client/store

- src/app contains route, layout, metadata, and same-origin BFF handlers only.
- src/features contains one product capability per folder and owns orchestration.
- src/ui contains API-free, router-free, product-neutral primitives.
- src/lib contains generated contracts and utilities used by at least two features.
- A shared primitive never imports app, feature, auth, API, or store code.
- Feature components receive public DTOs and callbacks. They never receive credentials, object keys, runtime URLs, or database rows.

Structural validation must fail imports that point upward or create a second component tree under src/components.

## Required primitives

| Primitive | Required variants | State contract |
| --- | --- | --- |
| Button | primary, secondary, danger, ghost, icon; sm/md/lg | idle, hover, pressed, focus, loading, disabled |
| Input | text, password, search-compatible | label, help, error, required, disabled |
| Textarea | fixed or auto-grow | same as Input; composition-safe |
| Select | native on narrow; popover on desktop if accessible | loading, empty, invalid, disabled |
| Checkbox | checked, unchecked, indeterminate | label owns hit area |
| SegmentedControl | sm/md, single selection | roving keyboard selection |
| Tabs | underline, pill | manual activation unless content is instant |
| StatusPill | neutral, info, success, warning, danger | icon/text; never color only |
| Card | none/sm/md/lg padding; selected/interactive | semantic button/link when clickable |
| Table | compact header/body/row/cell | sortable headers, selected row, row action |
| ListRow | resource/actionable/selectable | fixed density and keyboard activation |
| Modal | default/destructive | title, description, focus trap/restore |
| Drawer | navigation/detail/task | Escape, backdrop, focus trap on modal form |
| Skeleton | text/row/card/pane | aria-hidden; parent names loading state |
| Alert | info/success/warning/danger | role status or alert by urgency |
| MarkdownContent | answer | sanitized, semantic headings/tables/code |

Button loading keeps its original width, sets aria-busy, disables repeat activation, and retains its label beside or for the spinner. Disabled controls expose a nearby explanation when the reason is not obvious.

## Shared compositions

| Composition | Owns | Must not own |
| --- | --- | --- |
| AppShell | rail, mobile bar, main slot, global overlays | authentication truth |
| NavigationRail | allowed route projection, collapse/resize UI | role authorization |
| PaneHeader | title, status, actions, pane border | data fetching |
| PageHeader | route title, description, page actions | sticky app navigation |
| DataSurface | loading/empty/error/ready choice | endpoint-specific retry policy |
| RightInspector | resize, close, header, responsive drawer | selected record semantics |
| ResourceTable | keyboard row selection and columns | destructive action rules |
| OperationStatus | progress/state/attempts/safe message | polling or mutation |
| ConfirmActionDialog | target, consequence, confirm/cancel | calling the mutation directly |

Product-specific compositions belong to their features:

- chat: ConversationRail, Transcript, Composer, EvidenceInspector
- documents: DocumentLibrary, DocumentViewer, SourceOperationPanel
- settings: SettingsNav, SettingsGroup, SettingsRow, Settings Domain accordion (Settings-owned; not a shared Accordion primitive)

### Settings Domain accordion

Settings-owned Controllers-style expandable list for administrator Knowledge Domains. Cite Local Studio Controllers/environment-controls and Knowledge Graphs packs as grammar evidence only; do not export `@/ui` Accordion or StorageBar.

| Element | Contract |
| --- | --- |
| Ownership | `src/features/settings-panel` only until a second consumer and contract change justify a shared primitive |
| Disclosure | One open row at a time; collapsed by default; expand state is local UI only |
| Collapsed header | Display name, mono id, domain `state` StatusPill, Start/Stop XOR via contracted `ToggleSwitch` (busy/disabled while in flight) |
| Expand body | Locked safe facts from closed `AdminDomainDto` only: nested `embeddingProfile.name` / `vectorDimensions`, `state`, `queryEligible`, `runtimeReady`, `controlGeneration`, `version` as safe labels. Administrator Settings only — never member/chat surfaces |
| Explicit non-requirement | No `storageSummary`, ProgressBar-on-expand, paths, ports, runtime URLs, or browser-computed quotas |
| Deploy | Create then start as one gesture; if create succeeds and start fails, keep the domain listed (`start_failed_keep`) and allow Start retry after refresh |
| Delete | Expand-only quiet danger control + `UiModal`; Cancel receives initial focus; `If-Match` from `version`; display-name typing only when closed DTO/precondition metadata supplies nonzero affected-count; otherwise confirm-only with downstream-effects copy; keep dialog open on conflict/stale with request ID |
| Post-mutation | After `202 {operation}`, disable conflicting controls until list refresh reconciles `state` / `allowedActions`; `allowedActions` remains advisory |
| Forbidden | Shared Accordion kit export; Phase 2 ops/logs/usage chrome; Phase 3 publication UI |

## Prop and event rules

- IDs in public props are opaque branded safe references, never plain private strings.
- Async callbacks return Promise<void> and the parent owns pending/error reconciliation.
- Controlled selection uses selectedId plus onSelectionChange.
- Closing a panel emits intent only; the route/store decides whether selection persists.
- Components do not accept whole API clients or stores. Hooks adapt clients into view models.
- Exhaustive discriminated unions define state; boolean pairs such as loading plus failed are prohibited.

Example:

    type EvidenceCardState =
      | { kind: "ready"; evidence: EvidenceView }
      | { kind: "opening"; evidence: EvidenceView }
      | { kind: "unavailable"; label: string; requestId?: string };

This prevents an evidence card from being both opening and unavailable.

## Component-specific contracts

### NavigationRail

- Desktop width clamps to 240-520 px; default 275 px.
- Items are derived from a fixed route registry filtered by current-user projection.
- Members never see admin-only items. A direct URL still relies on server authorization.
- Cmd/Ctrl+K opens conversation search. Escape closes it and restores focus.
- Collapse, width, and theme are browser preferences; selected route is URL state.

### DataSurface

State precedence is forbidden/unauthorized, fatal error with no data, initial loading, empty, ready. A refresh error with existing data renders ready plus a non-blocking stale notice. Request IDs appear in a copyable disclosure, never as the primary message.

### RightInspector

- Desktop is an adjacent aside, not an overlay; default 440 px, min max(320px,25vw), max 65vw.
- Below 1024 px it is a modal right drawer no wider than min(100vw, 440px).
- Resize separator is keyboard operable in 16 px steps and resets on double click.
- The inspector header remains visible while its body scrolls.

### Table and ListRow

- Rows are 36 px minimum desktop; resource rows may expand to 48 px for two lines.
- Row click selects; embedded actions stop selection and have labels.
- Enter opens the selected row; Space selects; Arrow Up/Down moves roving focus.
- Sort state is encoded in the URL for durable lists.
- Virtualization is allowed only above 200 rows and must preserve semantic table/list access.

### Modal and destructive confirmation

The dialog names the resource, describes downstream effects, starts focus on Cancel, and requires an explicit confirm activation. Domain/source delete may require typing the display name when affected-count metadata is nonzero. On server conflict, keep the dialog open and render current state plus request ID.

## Accessibility contract

- Every interactive element is reachable without pointer input.
- Icon-only controls have aria-label and tooltip; decorative icons are hidden.
- Focus indicators use the link token and remain visible over every surface.
- Dialog/drawer focus is trapped only while modal; nonmodal desktop inspectors do not trap.
- Live updates announce stage changes, not every streamed token.
- Selected evidence, row, tab, and domain expose semantic selected state.
- Headings form one route-level h1 followed by ordered pane headings.

## Test hooks

Prefer role, name, and visible state in browser tests. Add data-testid only for nonsemantic boundaries:

- app-shell, discovery-rail, primary-workspace, right-inspector
- chat-transcript, chat-composer, stream-stage
- evidence-card-{safe-ref}, document-viewer, pdf-page-{number}
- operation-{safe-ref}, request-id

Never derive a test hook from a private ID. Each primitive has unit tests for keyboard, focus, disabled/loading, and ARIA. Each composition has a browser test for narrow substitution and focus restoration.

## Reuse rule

Port Local Studio primitives by copying into Context Engine ownership with provenance, then remove product-specific assumptions and add these contracts. Do not wrap a flawed pilot component indefinitely; replace it at the shared boundary and migrate call sites once.
