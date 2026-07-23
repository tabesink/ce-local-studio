# Accessibility Contract

Context Engine targets WCAG 2.2 AA for authenticated and anonymous surfaces. Accessibility is an acceptance gate, not a later visual pass.

## Global requirements

- Use semantic HTML before ARIA. Every control has an accessible name and visible focus.
- Keyboard access must not depend on hover, drag, pointer precision, or color.
- Text and interactive contrast meet AA; status always includes text/icon shape, never color alone.
- Reflow works at 400% zoom and 320 CSS px width without losing actions or evidence.
- Respect `prefers-reduced-motion`; no flashing, auto-playing media, or token-by-token announcements.
- Page title and one `h1` identify the route. Landmark order is navigation, main, optional complementary inspector.
- Safe errors identify the affected action, recovery, and request ID without moving focus unexpectedly.

## Keyboard and focus matrix

| Surface | Required behavior |
| --- | --- |
| sidebar | links in DOM order; collapse button named; mobile drawer traps focus and Escape closes |
| conversation list | native links/buttons; rename menu is keyboard operable; deletion returns focus to logical neighbor |
| transcript | messages remain normal document flow; assistant turn selector is a button only when interactive |
| composer | label exists; Enter submits, Shift+Enter newline; chips have named remove buttons |
| evidence panel | `aside` labelled Evidence; rows are buttons/list; arrows optional, Tab always works |
| PDF viewer | labelled region/title; page control, zoom, and close are keyboard accessible |
| dialogs | initial focus, trap, Escape unless destructive commit is running, opener focus restore |
| tables | real table headers; row actions are controls, not click-only rows |
| graph route | until an approved graph DTO exists, expose a named unavailable region and no inert canvas; once enabled, canvas data requires an equivalent searchable node list/detail |
| toasts | no focus steal; persistent actionable errors also appear in route/form content |

Opening evidence focuses the viewer heading, then the resolved figure/table/text anchor. Closing returns to the originating evidence card when it still exists; otherwise to the selected assistant turn. This is required for M-04/M-05.

## Streaming announcements

Use one polite live region outside the transcript. Announce lifecycle changes only:

```text
Answer started.
3 evidence sources found.
Answer complete.
Connection lost. Reconnecting.
Answer failed. Request ID …
Answer redacted because its source is no longer available.
```

Do not announce answer tokens, elapsed time ticks, skeleton changes, or every evidence row. Debounce evidence counts for 500 ms. Terminal/failure announcements occur once after canonical reducer commit.

## Evidence and documents

- Citation text names its label and source, for example `Evidence 2, Quarterly report, figure`.
- Selected evidence exposes `aria-current` or `aria-pressed`; visual selection is not color-only.
- Figure regions require an available caption/description or bounded extracted text. Tables require an HTML/text alternative when the PDF canvas is not readable.
- Viewer zoom must not scale surrounding controls. Page/anchor updates announce once through a dedicated status region.
- If exact highlighting is unavailable, announce that the containing page/section opened.
- Authorization loss closes protected content, moves focus to the safe notice, and never leaves an inaccessible blank object.

## Forms and operations

- Labels, descriptions, required state, and field errors are programmatically associated.
- Validation runs on submit and may run on blur; do not erase input or announce on every keystroke.
- Busy controls retain their name and expose `aria-busy`; disabled state is never the only explanation.
- Destructive dialogs name the object and consequence. The least destructive action receives initial focus.
- Progress exposes determinate values only when backend truth provides them; otherwise use a named indeterminate status.

## Visual and motion details

Minimum target size is 24x24 CSS px with adequate separation; primary touch actions target 44x44 on narrow layouts. Focus indicators are at least 2 CSS px and not clipped by panes. Text spacing overrides must not hide content. Reduced motion replaces panel slides with an immediate state change and disables animated skeleton shimmer.

## Verification

- Automated axe checks on every golden route/state for member and admin.
- Playwright keyboard-only flows for login, chat submit, evidence deep-link, viewer close/return, upload, settings, and logout.
- Screen-reader manual pass with NVDA/Firefox or VoiceOver/Safari for chat stream, evidence/PDF, dialogs, tables, and role-revocation failure.
- Zoom/reflow at 200%, 400%, and 320x640, including 400% in a 1280 px-wide browser window (approximately 320 CSS px), plus high-contrast/forced-colors mode.
- Tests fail for unnamed icon buttons, focus loss, duplicate live announcements, or, after graph enablement, graph-only data without the equivalent list/detail view.

Traceability: M-01 through M-07, M-11, A-03 through A-10, A-13, C-02, and C-05.
