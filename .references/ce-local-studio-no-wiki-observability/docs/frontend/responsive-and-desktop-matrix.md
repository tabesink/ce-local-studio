# Responsive and Desktop Matrix

Status: normative. Breakpoints describe behavior changes, not supported-device exclusions.

## Breakpoints

| Name | Width | Shell behavior |
| --- | --- | --- |
| compact | below 640 px | mobile bar, modal navigation, one primary pane |
| small | 640-767 px | same shell; wider dialogs/forms |
| medium | 768-1023 px | mobile navigation; route may show two compact columns |
| desktop | 1024-1279 px | persistent rail; inspector is a drawer unless space permits |
| wide | 1280-1535 px | persistent rail and adjacent inspector |
| extra-wide | 1536 px and above | same composition; clamp readable content, do not stretch prose |

Use CSS/container queries for pane internals. JavaScript media queries may select behavior only through a shared responsive store and must not produce hydration-dependent authorization or content.

## Shell matrix

| Capability | compact/small | medium | desktop | wide/extra-wide |
| --- | --- | --- | --- | --- |
| App navigation | right modal drawer | right modal drawer | persistent collapsible rail | persistent resizable rail |
| Top bar | 56 px | 56 px | route pane header only | route pane header only |
| Inspector | full/right drawer | right drawer max 440 px | right drawer or adjacent if room | adjacent resizable pane |
| Main scroll | route-owned | route-owned | pane-owned | pane-owned |
| Touch targets | 44 px minimum | 44 px for coarse pointer | 28-36 px visual, 40 px hit where needed | same |
| Modal width | calc(100vw - 24px) | min(560px,calc(100vw - 48px)) | intrinsic max | intrinsic max |

The desktop rail never collapses automatically after the user explicitly pinned it. If viewport shrink forces substitution, restore the previous rail state when width returns.

## Route matrix

| Route | below 768 px | 768-1023 px | 1024 px and above |
| --- | --- | --- | --- |
| /login | 24 px page gutter; full-width 360 px max card | same | centered card |
| /chat | transcript; composer fixed; evidence drawer | transcript plus evidence drawer | transcript plus adjacent inspector where width permits |
| /documents | library or viewer, explicit Back | list/detail, one dominant pane | resizable library/viewer split |
| /database-visualize | deliberate unavailable state | deliberate unavailable state | deliberate unavailable state until graph DTO approval |
| /settings | section list then section page | section list/detail | 220 px section nav plus content |

Hiding a secondary pane must create an explicit control to open it. Do not omit evidence, filters, operation status, or admin consequences.

## Chat constraints

- Composer horizontal gutter is 12 px compact, 24 px at 640 px, and centered at max --composer-w on desktop.
- Transcript bottom padding equals measured composer height plus safe-area inset.
- A virtual keyboard resize uses visual viewport height; it must not scroll the selected turn out of reach.
- Reference chips wrap above the textarea and never shrink the send control.
- At widths below 560 px, composer metadata wraps to a second line.
- Evidence drawer occupies min(100vw,440px), with an accessible backdrop and focus trap.

## Document constraints

- Viewer toolbar wraps into two rows before controls overflow.
- Page canvas may horizontally pan inside its own region; the route must not create body overflow.
- Library columns reduce in this order: Blocks, Size, Updated. Filename and status remain.
- Hidden table facts remain in row detail, not discarded.
- On mobile, opening Viewer pushes safe URL state so Back returns to Library.

## Height constraints

| Available height | Required adaptation |
| --- | --- |
| 800 px or more | normal compact workstation |
| 600-799 px | reduce route header margins; preserve toolbars and composer |
| 480-599 px | dialogs use full available height; sticky actions; internal scroll |
| below 480 px | still operable; no minimum-height content that hides actions |

The rail header/footer remain visible; its middle region scrolls. Pane headers and composer remain visible while their content scrolls. Avoid viewport-height units without dynamic viewport or --app-height fallback.

## Zoom and text scaling

- Support browser zoom at 100, 125, 150, 200, and 400%.
- At 400% in a 1280 px-wide browser window, the approximately 320 CSS px layout must reflow without losing content or actions.
- No two-dimensional page scroll except the PDF viewer, data tables with an accessible alternative, and a future graph canvas only after its DTO is approved.
- Text must not be clipped by fixed-height controls; one-line resource rows may grow when system text metrics require it.
- Do not set user-scalable=no in the production web viewport.

## Pointer, touch, and keyboard

- Fine pointer: compact 28-36 px controls are allowed with at least an 8 px resize hit zone.
- Coarse pointer: primary interactive targets are at least 44 x 44 px and have 8 px separation or an equivalent nonoverlapping hit area.
- Hover content must also appear on focus; touch exposes an explicit action menu.
- Pane resize supports pointer drag and keyboard arrows, with Shift for larger steps.
- Swipe gestures are optional enhancements and never the only navigation.

## Safe areas and virtual keyboard

Use env(safe-area-inset-*) for mobile bar, composer, drawers, and modal actions. The composer follows visualViewport resize and remains above the keyboard. Do not persist keyboard-induced pane dimensions as user preferences.

## Deterministic test viewports

| Fixture | Purpose |
| --- | --- |
| 390x844, coarse pointer | phone, safe area, drawer, keyboard |
| 768x1024 | tablet portrait and medium substitution |
| 1024x768 | minimum desktop shell |
| 1280x800 | required compact desktop parity |
| 1440x900 | primary visual baseline |
| 1920x1080 | wide clamping and three-region composition |
| 1280x800 at 200% zoom | reflow and text scaling |
| 1440x600 | low-height workstation |
| 320x640 | minimum-width reflow and long-label handling |
| 1280x800 at 400% zoom | WCAG reflow equivalent to approximately 320 CSS px |

Run dark theme at all fixtures and light theme at 390x844 and 1440x900. Test both empty and maximum-realistic labels. Locale fixture strings must include a 40-character domain, 80-character filename, and multi-line status message.

## Layout invariants

Automated assertions must prove:

- no document/body horizontal overflow;
- every visible pane has exactly one vertical scroll owner;
- fixed/sticky UI does not overlap focused content;
- opening a drawer does not shift the underlying layout;
- closing a drawer restores focus;
- rail and inspector widths stay clamped during rapid resize;
- route selection, draft, and selected turn survive responsive substitution;
- status/action content available on desktop remains reachable on compact screens.
