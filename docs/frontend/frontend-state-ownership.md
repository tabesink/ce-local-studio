# Frontend State Ownership

Frontend state is a projection, never product authority. Every field must have exactly one owner and an invalidation rule.

## Ownership matrix

| State | Owner | Frontend location | Persistence/invalidation |
| --- | --- | --- | --- |
| identity, role, session validity | FastAPI | request-scoped auth snapshot | refetch on boot/401/role event; clear on logout |
| conversations, turns, evidence | FastAPI/PostgreSQL | normalized in-memory resource cache | `no-store`; invalidate by response/event/version |
| domain/source/operation lifecycle | FastAPI/PostgreSQL | read-only feature projection | reconcile after every mutation and operation event |
| domain graph snapshot and label search | FastAPI graph endpoints | in-memory graph feature projection | `private, no-store`; invalidate on domain/generation/identity change; never persist DTOs |
| active route and selected safe refs | URL | route parser/selectors | browser history; reauthorize on restore |
| graph layout, hover, focus, local prune | browser presentation | graph feature store | memory only; coordinates are not product truth |
| composer draft and pending ref chips | browser tab | chat external store keyed by conversation | memory only; clear after accepted submit/logout |
| active stream and cursors | stream runtime | external store keyed by turn | memory only; rebuild from replay |
| panel open/width, sidebar width/collapse | browser presentation | component/external store | allowlisted local preference only |
| form edits and modal state | component/feature | nearest feature state | discard on close unless an approved contract persists the form |

## Storage allowlist

Only non-sensitive presentation preferences may use `localStorage`:

```text
ce.theme
ce.density
ce.sidebarCollapsed
ce.sidebarWidth
ce.evidencePanelWidth
ce.motionPreference
```

Validate enum/range and reset invalid values. Never store cookies, CSRF values, user DTOs, prompts, drafts, answers, evidence, graph snapshots/labels, safe refs, filenames, request IDs, operation data, provider settings, or server responses in `localStorage`, `sessionStorage`, IndexedDB, service-worker caches, or persisted Zustand state.

## Store boundaries

- `app` composes providers; `features` own product interaction; `lib/stream` owns transport/reduction; `ui` owns no product data.
- External stores expose `getSnapshot`, `subscribe`, and intent methods. A selector must return stable references when its data did not change.
- One store instance may be browser-global only for presentation and identity epoch. Personalized server clients and server-render caches are request-scoped.
- Key resource entries by `{identityEpoch, resourceKind, safeRef}`. Increment the epoch and drop all entries on login, logout, user replacement, or role change.
- A feature may not copy the same authoritative DTO into multiple independent stores. Derive views through selectors.

## Fetch generation rule

Every selection-dependent request captures `{identityEpoch, selectionKey, generation}`. Apply its result only when all three still match.

```text
select T1 -> generation 4 -> request A
select T2 -> generation 5 -> request B
response A -> discard
response B -> apply if still authorized
```

Abort old requests to save work, but correctness depends on the generation check. This is required for M-06 and C-02.

## Mutations and optimistic UI

Optimistic state is allowed for reversible presentation only: open/close, selection, input text, filter, and temporary button busy state. Do not optimistically claim `running`, `ready`, `deleted`, `redacted`, `completed`, or a changed role.

For a protected mutation:

1. retain the user's input;
2. disable duplicate intent locally;
3. send version/idempotency data;
4. reconcile the returned canonical DTO;
5. on `409`, keep the input, fetch current state, and show the conflict;
6. on unknown transport outcome, query by stable operation/request key before retry.

## Chat draft and submit

- Draft is keyed by conversation safe ref plus a new-conversation sentinel.
- The same rendered draft keeps one `clientRequestId` until input/domain/ordered refs change; a change creates a new ID and fingerprint.
- Submit does not clear the visible draft until `turn.accepted`. A recoverable failure restores it exactly.
- Once accepted, the transcript owns the user message and the draft clears. Socket closure does not roll it back.
- Two tabs do not coordinate draft contents. The backend idempotency boundary resolves same-ID submissions (M-10).

## Cache and browser lifecycle

- Personalized BFF/API responses use `Cache-Control: private, no-store`; document bytes use authorization-aware no-store delivery unless a separately approved private-cache design exists.
- Service workers must network-bypass `/api/v1`, document content, SSE, auth, and admin routes.
- `pageshow` with `persisted=true`, tab visibility restore, and browser Back trigger identity and visible-resource revalidation.
- Logout broadcasts only `{type:"logout", epoch}` over `BroadcastChannel`; no content or identifiers. Other tabs clear memory and navigate to login.
- Never render a previous user's snapshot while a new identity bootstraps. Use a neutral loading shell.

## Streaming ownership

The canonical reducer commits event effects and `appliedSequence` atomically. React render batching may lag; the store projection may not. Evidence is keyed by safe evidence ref and scoped to one turn. Terminal state comes from a terminal event or authorized terminal snapshot, never EOF, timeout, or component unmount.

## Required tests

| Test | Proof |
| --- | --- |
| storage allowlist scan | prohibited values never persist |
| identity epoch test | logout/login cannot reuse prior cache |
| stale generation test | T1 response cannot overwrite T2 |
| mutation conflict test | stale form is preserved and reconciled |
| stream atomicity test | cursor never advances ahead of reduced content |
| BFCache test | protected view revalidates before display |
| multi-tab logout test | all tabs clear without sharing content |

Traceability: M-02, M-03, M-06, M-09 through M-11, M-14 through M-21, A-01 through A-10, A-13, and C-01 through C-05.
