# Motion and Feedback Specification

Motion explains spatial change; feedback reports authoritative progress. Neither may imply a server transition that has not committed.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| `--duration-basic` | `150ms` | hover, focus, selection, and short panel movement |
| `--duration-relaxed` | `300ms` | drawer and modal entry/exit |
| `--ease-enter` | `cubic-bezier(.19,1,.22,1)` | standard entry |
| `--ease-enter-snappy` | `cubic-bezier(.23,1,.32,1)` | short panel movement |

These are the sole application motion tokens defined by `design-token-contract.md`; do not introduce a parallel `--motion-*` family. Do not animate layout longer than `--duration-relaxed`. Never animate answer text per token, PDF scrolling to anchor, table sorting, focus, or destructive state changes. Under reduced motion translations, scales, and delayed opacity transitions become immediate state changes.

## Feedback state machine

```text
idle -> submitting -> accepted -> running -> completed
                    -> failed | cancelled | redacted
       -> conflict | retryable-unknown
```

Only a response/event moves state beyond `submitting`. EOF moves `running -> reconnecting`, never to a terminal state.

| Intent | Immediate feedback | Authoritative feedback |
| --- | --- | --- |
| send question | composer busy; retain draft | `turn.accepted` moves message to transcript |
| stream answer | compact stage + reconnect state | evidence/text/terminal reducer projection |
| start/stop/index | button busy, no status claim | returned operation/domain DTO |
| upload | local byte transfer if measurable | source/operation record after acceptance |
| protected mutation/delete | confirmation when destructive, then busy dialog | committed DTO/event; close dialog on acceptance |
| preference change | immediate presentation update | none when allowlisted/local |

## Panels and navigation

- Sidebar, Evidence Panel, and mobile viewer use `--duration-basic` for short movement or `--duration-relaxed` for modal/drawer entry and preserve focus rules.
- Pointer resize has no easing while dragging; persist the bounded width on pointer-up.
- Deep-linking evidence opens the route first, renders viewer loading state, then focuses/scrolls to the authorized anchor without a decorative fly-over.
- Skeletons preserve final geometry and stop when any ready/empty/error state renders. No skeleton shimmer in reduced motion.

## Toast policy

Toasts are supplemental and never the only error/status record.

- Success toast only after authoritative acceptance: `Domain start requested`, not `Domain running`.
- No toast for routine navigation, selection, stream token/evidence updates, or initial loads.
- Error toast may summarize a background failure; the owning surface retains recovery and request ID.
- One toast per operation key; retries update the existing toast. Default duration 5 seconds, persistent when an action is required.
- Never include prompts, evidence text, filenames classified as sensitive, provider errors, or object paths.

## Conflicts, retries, and concurrency

- `409 stale_revision`: preserve edits, show inline `This changed elsewhere`, and offer `Review current version`; do not shake or discard the form.
- `409 operation_conflict`: replace stale status with current server state and identify the accepted operation.
- `429/503`: show retry guidance/countdown only from `Retry-After`; keep the intent enabled after the bound.
- Reconnect indicator appears after 500 ms to avoid flicker and announces once. Backoff continues without pulsing animation.
- Cross-user deletion/redaction fades nothing out before authorization confirms; protected content is removed immediately on the committed event/failed revalidation.

## Destructive feedback

Dialogs use object label, immediate fence effect, downstream effect, and recovery truth. Example:

```text
Delete “Safety Manual”?
It will stop being available for new questions immediately. Existing answers
that cite it will be redacted. Cleanup may continue in Operations.
[Cancel] [Delete document]
```

Closing before submission commits nothing. After submission, prevent duplicate clicks but allow dismissal only when the operation remains visible elsewhere.

## Required tests

- Fake-clock unit tests for toast deduplication, reconnect delay, and reduced-motion timing.
- Browser snapshots with animations disabled at initial, loading, running, reconnecting, terminal, conflict, and redacted states.
- Assert no success message precedes mutation acceptance and no EOF produces completion.
- Keyboard/focus tests across animated panel/dialog transitions.
- Concurrency tests for A-05, M-10, M-11, and C-05 feedback.

Traceability: all interaction cases; terminal and concurrency behavior is especially normative for M-03, M-10, M-11, A-03 through A-10, and C-01 through C-05.
