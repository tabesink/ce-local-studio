# Chat and Evidence Workbench

Status: normative implementation contract for /chat. Case IDs refer to interaction-behavior-prd.md.

## Workspace composition

Desktop has three logical regions:

| Region | Width | Owns |
| --- | --- | --- |
| Discovery rail | 240-520 px; 275 default | navigation, conversation discovery/search |
| Conversation workbench | remaining width; 560 px useful minimum | header, transcript, composer |
| Turn inspector | 320 px-65vw; 440 default | Evidence, Refs, Source tabs |

The inspector is optional presentation state. Closing it does not clear selectedTurn or selectedEvidence. Below 1024 px it becomes a modal right drawer. Below 768 px the discovery rail becomes the app navigation drawer.

## Conversation header

Show:

- editable conversation title or New conversation;
- stream stage for the active running turn;
- conversation picker/actions;
- New conversation;
- inspector toggle.

Rename saves on Enter or blur, cancels on Escape, and reconciles conflicts. Delete uses a destructive dialog. An in-flight turn does not prevent viewing another conversation; its completion remains scoped to its owning conversation.

## Transcript

- Width clamps to --thread-w, centered inside the scroller.
- User messages align right, max 80%, on a subtle surface.
- Assistant messages align left, max 92%, and render sanitized semantic Markdown.
- Persisted assistant messages are keyboard-selectable turn containers. Selecting one atomically replaces the inspector projection with that turn's data (M-06).
- The active turn has a two-pixel link-colored left rule and selected semantics.
- Auto-scroll occurs only when the reader is within 64 px of the bottom. Otherwise show Jump to latest and do not steal position.
- A redacted turn preserves its user question and renders a neutral redaction notice; answer and citations are absent (M-11).

Do not announce every token. The live region announces stage changes and one terminal result.

## Composer

The lifted composer is centered, max --composer-w, radius 24 px, with:

- ordered governed-reference chips;
- multiline textarea, 96 px minimum;
- reference picker;
- explicit Knowledge Domain selector;
- send button;
- safe status line using display labels, not raw IDs.

Keyboard:

- Enter submits when not composing IME text.
- Shift+Enter inserts a newline.
- Escape closes the reference picker first.
- Cmd/Ctrl+Enter may also submit but is not the only shortcut.

Submission rules:

1. Capture message, selected domain, ordered refs, conversation, and one generated clientRequestId.
2. Disable duplicate local activation but rely on server idempotency for correctness.
3. Preserve the draft until turn.accepted is applied.
4. After acceptance, clear only the submitted snapshot; newer typing remains.
5. If domain or refs become invalid, preserve the draft and identify the invalid selection (M-02, M-09).
6. Never silently change a domain, drop a ref, or route a domain-seeking question to direct chat.

## Domain selector

- Direct chat is an explicit option.
- Show only server-returned query-eligible domains to members.
- Display label and safe availability; never show runtime location or internal ID.
- A domain selected for the next turn does not mutate an earlier turn or conversation.
- If the selected domain disappears, mark it Unavailable until submit reconciliation or explicit user change.

## Governed reference picker

Tabs are Sources, Evidence, and Templates. Discovery is debounced, cancellable, and generation-checked. Results contain a one-use or short-lived token plus safe label/description.

- Chips preserve order because order participates in the request fingerprint.
- Disabled results state a safe reason.
- Used, expired, incompatible, duplicate, or revoked tokens reject before provider work.
- Raw tokens live in memory only and disappear after acceptance, rejection, logout, or expiry.
- Accepted history renders safe accepted-reference metadata, not the token.

## Stream state machine

Live POST, resumed GET, and durable replay feed one reducer.

| Event | Observable effect |
| --- | --- |
| turn.accepted | bind turn ID; clear submitted draft snapshot |
| route.selected | show Direct chat or Grounded answer stage |
| retrieval.started | stage becomes Searching domain |
| evidence.delta | insert/deduplicate evidence by safe ref; citations may render |
| retrieval.completed | show evidence-found or grounded-no-context result from the server |
| answer.delta | append token at exact sequence position |
| turn.completed | commit terminal answer/status; announce completion |
| turn.failed | retain safe partial projection only if contract permits; show retry |
| turn.cancelled | terminal Cancelled; no invented answer |
| unknown additive event | record cursor, no UI mutation |

Reducer invariants:

- Apply only matching schema major and turn ID.
- Ignore only an exact duplicate with matching `eventId`, sequence, and payload digest.
- Treat a regression or same/lower sequence with different identity/content as `stream_protocol_error`.
- On a forward gap, apply nothing after the gap and reconnect after `lastAppliedSequence`.
- Never infer completion from socket close.
- Persist received and applied cursors separately.
- A 410 cursor_expired uses the authorized terminal snapshot or reloads turn history.

The send control becomes Stop only when a cancellation API is contracted and authorized. Do not display a nonfunctional stop affordance.

## Failure and reconnect presentation

| Condition | UI |
| --- | --- |
| network closes before terminal | Reconnecting pill; keep rendered content |
| bounded retry active | attempt-neutral status; no countdown noise |
| retry exhausted | Connection interrupted, Resume action, request ID |
| domain unavailable | draft retained; stale domain marked; choose-domain action |
| no mapped evidence | grounded refusal; Evidence tab empty explanation |
| idempotency conflict | draft retained; conflict message; new request ID only after user intent |
| auth expires | clear private view, route to login, do not resume automatically |

Retrying a terminal failure creates a new clientRequestId. Resuming a disconnected accepted turn does not.

## Inspector tabs

| Tab | Source | Behavior |
| --- | --- | --- |
| Evidence | selected turn evidence projection | ordered cards and selected excerpt/asset |
| Refs | accepted refs for selected turn | read-only chips and safe descriptions |
| Source | selected evidence document context | safe metadata and Open in Library |

If a tab has no content, render a contextual empty state. Never fall back to evidence from a different turn. Slow responses are discarded when conversation, turn, tab, or session generation changes.

## Evidence cards

Every card includes citation label, source display label, kind, safe locator such as page/section, and excerpt or asset thumbnail when authorized. The card is a button with selected state.

- Text: open the document at its semantic block/highlight.
- Table: open the page/section and focus the table region.
- Figure: open /documents with safe document/evidence refs, page, and figure region (M-04).
- Unavailable: disable navigation, preserve safe label, show Evidence no longer available and request ID.

Example navigation:

    /documents?document=doc_safe_7&evidence=ev_safe_12&page=18

The document route reauthorizes the refs; the chat route never passes a storage path, object URL, raw block ID, or trusted excerpt through the URL.

## Concurrent behavior

- Identical submissions from two tabs with one clientRequestId converge on one turn (M-10).
- Each tab may select a different turn/evidence without cross-tab presentation synchronization (C-03).
- Conversation cache keys include authenticated user identity. Another user's event cannot enter the reducer (C-04).
- Source deletion during viewing turns the affected answer redacted on refresh/event reconciliation; it does not leave stale citations clickable (M-11).
- Domain stop after turn acceptance follows the server terminal outcome. The client does not rewrite it based on a later domain-list refresh.

## Required test hooks and proofs

Hooks: conversation-title, chat-transcript, message-{safe-turn-ref}, chat-composer, domain-selector, ref-picker, stream-stage, inspector-tab-{name}, evidence-card-{safe-ref}, jump-to-latest.

Tests must cover M-02 through M-11, C-01 through C-04, live/resume/replay fixture equivalence, duplicate/out-of-order events, slow selection responses, IME submit, scroll anchoring, keyboard evidence selection, narrow drawers, redaction, and reconnect through the deployed ingress.
