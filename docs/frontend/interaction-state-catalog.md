# Interaction State Catalog

Status: normative visual and behavioral state vocabulary. Features may add typed detail but may not invent conflicting global states.

## State precedence

When several facts are true, render the first applicable state:

1. session expired;
2. forbidden or authorization lost;
3. deleted/redacted/unavailable resource;
4. fatal initial-load failure;
5. initial loading;
6. empty;
7. ready with stale/refresh/action overlays.

This prevents stale data from remaining visible after authorization loss and prevents a background refresh from replacing useful data with a spinner.

## Data-surface union

Every remote data surface models:

    idle
    initial-loading
    empty
    ready(data, freshness)
    fatal-error(error)
    forbidden
    unavailable

Ready freshness is fresh, refreshing, stale, or refresh-error. A component must not represent these with independent booleans.

| State | Required presentation | Prohibited behavior |
| --- | --- | --- |
| idle | nothing before intent, or named prompt | accidental empty-state flash |
| initial-loading | geometry-preserving skeleton | blank shell or indefinite unlabeled spinner |
| empty | reason plus one valid next action | generic No data when filters caused it |
| ready/fresh | full data | hidden refresh status |
| ready/refreshing | retain data, subtle progress | replacing data with skeleton |
| ready/stale | retain data, Stale label, Refresh | implying current truth |
| ready/refresh-error | retain data, safe warning/request ID | destructive reset |
| fatal-error | safe message, Retry, request ID | stack/provider payload |
| forbidden | generic access message | resource existence disclosure |
| unavailable | safe prior label if permitted, recovery/navigation | fallback to another resource |

## Action union

Mutating controls use idle, submitting, accepted, reconciling, succeeded, conflict, failed, or cancelled.

- submitting: local request has not been accepted; prevent repeat activation.
- accepted: server committed intent/operation; show returned state.
- reconciling: waiting for authoritative projection after asynchronous work.
- succeeded: display only after authoritative response/event.
- conflict: preserve input, show current server state and resolution.
- failed: preserve recoverable input; show safe message and request ID.
- cancelled: terminal only when server confirms cancellation.

Do not show a success toast when a request merely returned 202. Show Operation queued and track it.

## Chat turn states

| State | Transcript | Composer/inspector |
| --- | --- | --- |
| draft | no server turn | editable; submit enabled when valid |
| submitting | pending bubble/skeleton only | submitted snapshot protected |
| accepted | durable user message and assistant frame | draft snapshot clears |
| routing | safe stage label | domain/ref controls apply to next turn only |
| retrieving | Searching domain | Evidence may begin populating |
| answering | incremental sanitized answer | evidence remains turn-scoped |
| reconnecting | retain projection; Reconnecting | Resume available after exhaustion |
| completed | stable answer/citations | selectable turn |
| failed | safe terminal error | Retry creates new request ID |
| cancelled | Cancelled terminal | no inferred partial completion |
| redacted | question plus redaction notice | evidence/actions removed |

Unknown additive events do not create a new visual state. Socket close does not create completed, failed, or cancelled.

## Evidence states

| State | Card/detail behavior |
| --- | --- |
| pending | ordered skeleton only after retrieval begins |
| available | selectable, citation label and source locator |
| selected | semantic selected state; detail shown |
| opening | retain card, show localized progress |
| stale | retain safe label; reauthorization pending |
| unavailable | disabled navigation; Evidence no longer available |
| redacted | remove excerpt/asset and public linkage |

Selecting a turn with no evidence shows No evidence was used for this answer. A domain answer with no grounded evidence presents the grounded refusal; it must not look like a normal uncited answer.

## Domain and source operations

| Backend state family | Tone | Allowed UI action pattern |
| --- | --- | --- |
| stopped | neutral | Start as contracted |
| queued/pending | warning | view operation; cancel only if allowed |
| starting/preparing/indexing/deleting | warning | progress and server-projected actions |
| running/ready | success | query or stop |
| stopping/cancelling | warning | no duplicate control intent |
| cancelled | neutral | retry when allowed |
| failed/error | danger | safe failure plus retry when allowed |
| degraded | warning | inspect/repair |
| deleted | unavailable | remove from active lists |

Allowed actions come from typed service rules or an allowed-actions projection, not string comparisons spread across components.

## Settings → Knowledge Domains accordion

Administrator-only Settings section (`/settings?section=domains`). One-open disclosure; no storageSummary UI.

| UI state | Behavior |
| --- | --- |
| loading | Domains list skeleton/notice; no invent empty success |
| empty | `No Knowledge Domains are available.`; Deploy affordance remains when product allows |
| ready / collapsed | Header shows name, mono id, state StatusPill, Start/Stop XOR |
| ready / expanded | Locked facts from closed `AdminDomainDto`; quiet Delete |
| stale / refresh failure | Retain prior list when present; non-blocking notice + request ID; Reload |
| fatal failure | Safe Domains load error + request ID; no infra dump |
| deploy validation | Local id/name/profile rules before submit; preserve draft |
| deploy create-fail | Keep deploy draft; danger notice; no phantom domain row |
| deploy start-failed-keep | Create succeeded, start failed: domain remains listed (typically stopped); clear deploy draft; danger notice; Start retry after refresh (A-03 UI half) |
| start/stop busy | Disable conflicting lifecycle controls until refresh reconciles |
| delete confirm | Modal open; Cancel-first focus; If-Match delete |
| delete stale / conflict | Keep modal useful; show safe conflict/stale copy + request ID; Reload/reconfirm (A-05 / A-10 UI half) |
| deleting | Domain shows deleting tone; controls disabled; refresh until gone or recoverable op state |
| role revocation / unauthorized section | Drop admin sections; `replace` to General with notice; clear in-memory domains; never flash Domains chrome for members |
| one-open transition | Opening B collapses A; if selected domain disappears after refresh, collapse |

Traceability: A-03, A-05, A-10 UI halves; C-05 section fallback.

## Settings → Model Provider

Administrator-only Settings section (`/settings?section=provider`). Compact grouped rows; no dashboard card grid.

| UI state | Behavior |
| --- | --- |
| loading | Provider section skeleton/notice; no invent empty success |
| ready | Providers show `configured` status; credential action only when `requiresCredentials` |
| unconfigured provider | Warning status; cannot become active synthesis default until configured (where credentials required) |
| Ollama / no-credential | Neutral status; no secret field |
| credential modal / inline replace | Write-only input; clear on success/navigation; busy without disabling cancel |
| synthesis change | If-Match from runtime `version`; copy that in-flight work keeps frozen config |
| stale / conflict (428/409) | Preserve pending intent and typed secret; refresh snapshot; review/retry |
| forbidden / not-found | Safe Settings failure; no secret or private ID disclosure |
| embedding facts | Read-only list; no replacement control on this page |

Traceability: A-01, A-02, A-13 UI halves; FE-10.

## Authentication and permission states

- Resolving session: shell-private skeleton; no personalized data.
- Authenticated: cache partition includes current user identity.
- Expired/revoked: clear memory caches, stop streams, route to login.
- Forbidden: retain app shell, remove resource data, generic message.
- Role revoked: immediately remove admin navigation and cancel admin queries; open admin route becomes forbidden.
- Logout pending: disable repeat action; after confirmation clear projections and replace route history.

Never briefly render admin controls while current-user state is unresolved.

## Form states

| Condition | Behavior |
| --- | --- |
| pristine | no validation noise |
| locally invalid | field message and summary only after submit/blur policy |
| dirty | preserve across non-destructive internal navigation where specified |
| submitting | retain values; lock only conflicting controls |
| server invalid | map field codes; focus first error |
| conflict | retain values; show current version and Reload/Review |
| success | reconcile values from response; announce once |

Passwords and provider credentials clear after any accepted rotation and on navigation. They are never draft-persisted.

## Empty-state catalog

Use specific copy and action:

| Surface | Empty text | Primary action |
| --- | --- | --- |
| conversations | No conversations yet | Ask a question |
| domain selector | No domains are available | admin: Manage domains; member: none |
| library | No documents in this domain | admin: Upload document |
| filtered library | No documents match these filters | Clear filters |
| evidence | No evidence was used for this turn | none |
Do not offer an action the current actor cannot perform.

## Concurrency and stale state

- A response carries request/selection generation. A response from an older generation is discarded.
- A 409 does not retry blindly. Render current state and a user-safe resolution.
- Duplicate idempotent success attaches to the existing result without duplicate toast or row.
- Source/domain deletion invalidates open detail, related evidence, and action menus together.
- Two tabs may hold different presentation selection. Product mutations converge through server state.
- A tab returning from background revalidates session and visible resource before applying queued results.

## Feedback placement

| Feedback | Placement |
| --- | --- |
| field validation | adjacent field plus summary |
| pane fetch failure | within pane |
| stream stage/error | transcript header/turn |
| operation progress | resource row and operation detail |
| global session loss | route replacement |
| short confirmed success | nonblocking toast, maximum one per intent |
| destructive conflict | originating dialog/panel |

Toasts never carry the only copy of an error, request ID, or recovery action.

## Accessibility and motion

- Initial loading surfaces expose one polite status.
- Errors use alert only when immediate; background refresh failures use status.
- Streaming announces stage and terminal result, not tokens.
- Progress has text and determinate values when known.
- Focus moves only for route changes, opened modal/drawer, explicit evidence focus, or validation error.
- Reduced motion removes shimmer, smooth scroll, and spatial transition while retaining state changes.

## Test contract

Each feature test matrix includes every applicable catalog state. Deterministic fixtures use codes such as data.initial-loading, data.refresh-error, action.conflict, turn.reconnecting, evidence.unavailable, auth.revoked, and operation.indexing.

Browser tests must prove state precedence, retained data during refresh, request-ID copy, no stale paint after revocation, no duplicate success under idempotent replay, selection-generation race handling, and accessible announcements. A screenshot of ready state alone is not state coverage.
