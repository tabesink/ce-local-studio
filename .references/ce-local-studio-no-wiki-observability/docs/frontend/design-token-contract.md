# Design Token Contract

Status: normative. Context Engine owns a fork of the Local Studio token system; it must not import Local Studio at runtime.

## Token architecture

Tokens have three layers:

1. Primitive values: gray, blue, semantic color ramps; base spacing, radius, type, and motion.
2. Semantic values: background, panel, surface, border, foreground, muted, link, success, warning, danger.
3. Component values: sidebar width, row height, toolbar height, composer width/radius, inspector width.

Feature code may consume semantic or component tokens only. Shared UI code may consume primitives to define semantic variants. Raw hexadecimal, rgb, oklch, pixel spacing, radius, shadow, and transition values outside styles/tokens.css fail the style-token lint.

## Primitive defaults

| Token | Value |
| --- | --- |
| --ui-scale | 1 |
| --space-base | 4px |
| --radius-base | 10px |
| --border-width | 1px |
| --leading | 1.5 |
| --leading-tight | 1.25 |
| --weight-normal | 400 |
| --weight-medium | 500 |
| --weight-strong | 600 |

Spacing aliases are --space-1 through --space-12 and resolve to 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, and 48 px. Use the smallest alias that preserves the reference layout. Arbitrary spacing requires a component token and a visual-regression fixture.

## zai-dark semantic colors

| Token | Resolved value | Use |
| --- | --- | --- |
| --bg / --color-background | #181818 | window and workbench canvas |
| --color-panel | #181818 | main panes |
| --sidebar-bg | mix of #212121 at 45% over #181818 | discovery rail |
| --surface / --color-card | #212121 | cards, user messages, selected details |
| --color-surface-hover | #282828 | elevated hover surface |
| --color-popover | #282828 | menus, dialogs, popovers |
| --color-popover-header | #303030 | drawer and popover headers |
| --color-input | #ffffff0d | resting inputs |
| --border | #ffffff14 | normal hairline |
| --separator | #ffffff0a | subtle internal rule |
| --hover | #ffffff0d | hover overlay |
| --active | #ffffff14 | selected overlay |
| --fg | #ffffff | primary foreground |
| --dim | #ffffffb3 | secondary foreground |
| --hl2 | #ffffff80 | tertiary foreground |
| --link | #339cff | links, focus, evidence anchors |
| --ok | #40c977 | successful/ready status |
| --warn | #ff8549 | pending/degraded status |
| --err | #ff6764 | failure/destructive status |

Do not use --accent as the only focus color: the dark brand accent resolves to white. Interactive focus uses --link with a visible two-pixel ring and two-pixel offset.

## zai-light semantic colors

| Token | Resolved value |
| --- | --- |
| --bg / --color-panel | #ffffff |
| --sidebar-bg | #f9f9f9 |
| --surface | #ffffff |
| --color-surface | #f3f3f3 |
| --color-surface-hover | #ededed |
| --border | #1a1c1f14 |
| --separator | #1a1c1f0d |
| --hover | #1a1c1f0d |
| --active | #1a1c1f14 |
| --fg | #1a1c1f |
| --dim | #5f6165 |
| --hl2 | #8c8e91 |
| --link | #0285ff |
| --ok / --warn / --err | #00a240 / #e25507 / #e02e2a |

Theme switching changes tokens only. It must not remount routes, clear drafts, alter geometry, or cause a flash of the wrong theme. The server-rendered root declares the persisted safe theme before hydration.

## Typography

| Token | Value |
| --- | --- |
| --font-sans | Geist Sans with system sans fallback |
| --font-mono | Geist Mono with system monospace fallback |
| --fs-2xs | 10px |
| --fs-xs | 11px |
| --fs-sm | 12px |
| --fs-md | 13px |
| --fs-base | 14px |
| --fs-lg | 16px |
| --fs-xl | 18px |
| --fs-2xl | 20px |
| --fs-3xl | 24px |
| --fs-4xl | 28px |
| --fs-display | 36px |

All sizes multiply by --ui-scale. Browser zoom remains supported; do not counter-scale. Monospace is limited to identifiers, sequence numbers, timestamps, request IDs, counts, code, and diagnostics.

## Radius and geometry

| Token | Value |
| --- | --- |
| --rad-2xs / xs / sm / md / lg | 2 / 4 / 6 / 8 / 10px |
| --rad-xl / 2xl / 3xl / 4xl | 12 / 16 / 20 / 24px |
| --rad-full | 9999px |
| --sidebar-w | 275px |
| --sidebar-w-collapsed | 48px |
| --sidebar-row-height | 30px |
| --sidebar-row-radius | 10px |
| --row-h / --row-h-sm | 36px / 28px |
| --h-toolbar / sm / pane | 46px / 36px / 40px |
| --thread-w | 900px |
| --composer-w | clamp(25vw, 48rem, 52vw) |
| --composer-radius | 24px |

Controls use 28, 32, or 36 px visual height on desktop. On coarse-pointer narrow devices the hit target expands to at least 44 px without changing desktop screenshots.

## Elevation and motion

Use the Local Studio elevation ramp: --elev-sm, md, lg, xl, 2xl, and side-panel. The dark composer uses a 0 10px 28px rgba(0,0,0,.18) shadow plus an inset translucent hairline. Ordinary cards and table rows do not cast shadows.

The shared stacking scale is --z-base: 0, --z-sticky: 20, --z-popover: 40, --z-drawer: 50, --z-modal: 60, and --z-toast: 70. A feature may not create a higher local layer; nested components use an isolated stacking context beneath their owning overlay.

| Motion token | Value | Use |
| --- | --- | --- |
| --duration-basic | 150ms | hover, selection, collapse |
| --duration-relaxed | 300ms | drawer and modal entry |
| --ease-enter | cubic-bezier(.19,1,.22,1) | enter |
| --ease-enter-snappy | cubic-bezier(.23,1,.32,1) | short panel movement |

This is the only application motion token family. Do not add `--motion-fast`, `--motion-base`, `--motion-slow`, or alternative easing aliases. Components choose `--duration-basic` or `--duration-relaxed`; interactions that must be immediate use no transition.

Under prefers-reduced-motion, remove spatial and looping animation; retain immediate opacity/state changes. Streaming must remain understandable from text and ARIA status without shimmer.

## Semantic status mapping

| Product state | Tone | Required label example |
| --- | --- | --- |
| ready, running, completed | success | Ready |
| queued, pending, preparing, indexing | warning | Indexing |
| stopped, cancelled | neutral | Stopped |
| degraded, reconnecting | warning plus icon | Reconnecting |
| failed, redacted, unauthorized | danger or neutral by severity | Evidence unavailable |

Never map arbitrary backend strings directly to classes. Exhaustively translate typed states; an unknown state renders Unknown with neutral styling and emits a client diagnostic.

## Enforcement

- token-lint rejects raw visual values in app and feature files, except normalized PDF/graph coordinates.
- token-contract.test verifies both themes define every semantic token.
- component stories render at ui-scale 1 and 1.25 and with reduced motion.
- contrast tests cover text, focus, status pills, disabled controls, chart legends, and evidence highlights.
- visual snapshots prove theme changes do not alter element bounds.
