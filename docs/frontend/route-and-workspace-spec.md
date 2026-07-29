# Route and Workspace Specification

Status: normative route, composition, role, and safe URL contract.

## Route registry

| Route | Actor | Primary composition | Canonical URL state |
| --- | --- | --- | --- |
| /login | anonymous | LoginCard | return path only when same-origin allowlisted |
| /chat | member/admin | ConversationRail + Transcript + EvidenceInspector | conversation, turn, evidence, domain |
| /documents | member read; admin operate | DocumentLibrary + DocumentViewer | domain, document, evidence, page |
| /database-visualize | member/admin if authorized | DomainGraphWorkbench (read-only) | domain, node |
| /settings | member/admin | SettingsNav + Section | section |
| /forbidden | authenticated | SafeForbidden | from reason category, not resource ID |

The authenticated root redirects to /chat. Unknown routes render a safe not-found page inside the shell. Login renders without the shell.

## Authorization behavior

- Navigation is projected from GET /auth/me and removes disallowed items.
- Next middleware redirects only for user experience; FastAPI remains authoritative.
- A 401 clears personalized in-memory projections and replaces the route with /login.
- A 403 retains the shell and renders SafeForbidden without confirming resource existence.
- Role revocation removes admin navigation on the next current-user reconciliation and invalidates open admin data.
- Back navigation after logout must not reveal cached personalized markup.

## Shared desktop frame

    +------------------+--------------------------------------+------------------+
    | discovery rail   | route-owned primary workspace        | optional inspector|
    | app navigation   | one scroll owner per visible pane    | route selection   |
    +------------------+--------------------------------------+------------------+

The shell owns viewport height and overflow. Routes own inner scroll regions. No route adds a second full-page sidebar. The inspector is route-specific but uses the shared RightInspector contract.

## /login

- Center a 360 px maximum card vertically and horizontally.
- Show Context Engine identity, username, password, and Sign in.
- Submit on Enter; keep username after failure, clear password, focus the password field.
- Error copy is generic. Optional request ID is available in details.
- While pending, disable repeat submit without freezing the page.
- Successful login replaces history with /chat or an allowlisted same-origin return path.

Test hooks: login-form, username, password, login-submit, auth-error.

## /chat

Desktop composition:

    +----------------+--------------------------------+------------------+
    | app/conversation| transcript                    | Evidence/Refs/... |
    | discovery       | lifted governed composer      | turn inspector   |
    +----------------+--------------------------------+------------------+

- The app rail contains New chat, Search, route navigation, recent conversations, Settings, and Logout.
- The transcript header contains the conversation title, safe stream stage, conversation actions, and inspector toggle.
- The transcript owns vertical scroll. The composer is pinned below it and never scrolls with messages.
- The inspector is bound to selectedTurn, not merely the newest turn.
- Safe URL example: /chat?conversation=cv_opaque&turn=tr_opaque&evidence=ev_opaque&domain=dm_opaque.
- A new unsaved conversation uses no fake server ID. First submit creates or resolves it.
- Navigating to evidence in /documents preserves a return URL containing conversation and turn only.

Detailed behavior is in chat-and-evidence-workbench.md.

## /documents

- Default view is the library list filtered by an authorized domain.
- Members can open documents reached through authorized evidence and any other member-readable library contract. Only admins see upload, retry, cancel, index, and delete controls.
- Desktop opens the viewer beside the list. The split defaults to 50/50 and is resizable.
- A direct evidence link opens the viewer immediately, resolves the safe document ref, then applies page and semantic anchor.
- URL example: /documents?document=doc_safe&evidence=ev_safe&page=18.
- Closing the viewer removes document/evidence/page parameters with replace-state and keeps list filters.
- If the ref is unavailable, retain the requested label if safe and show Evidence no longer available.

Detailed behavior is in document-viewer-spec.md.

## /database-visualize

- The route is the Phase 1 read-only Knowledge Domain graph workbench backed by `GET /domains/{domainId}/graph` and `GET /domains/{domainId}/graph/labels`.
- Composition: authorized domain selection, bounded refresh, Sigma/Graphology canvas pan/zoom/select, searchable node list/detail equivalent to the canvas, and safe empty/loading/ready/stale/truncated/failure states.
- Canonical URL state is opaque `domain` and optional opaque `node` only. The selection parameter is `node`, never `entity`. Graph coordinates, layout, hover, focus, and client-side pruning are presentation state, not product truth.
- All product data loads through the same-origin BFF and generated client. The route must not call LightRAG, private runtimes, or a direct `/graphs` path, and must not expose raw vendor identifiers, property bags, or mutation controls.
- Below 1024 px, secondary list/detail becomes an accessible drawer rather than disappearing. Keyboard and touch paths must equal pointer selection.

## /settings

Use a two-column section layout at 1024 px and above and a section list/detail flow below it.

Member sections:

- General: theme, density, reduced-motion preference if not system-derived
- Account: current safe identity, session logout

Administrator additions:

- Providers and models
- Parser
- Knowledge Domains
- Users
- Operations defaults, where contracted

Section selection uses `/settings?section=<allowlisted>`. Live Phase 1 allowlisted ids are `general`, `provider`, `domains`, and `users` (Knowledge Domains for administrators). Invalid or newly unauthorized sections fall back to General with a nonintrusive notice. Derive the effective section from role before first paint so members never flash Domains chrome. Parser, Account, and Operations defaults remain contracted later additions — do not scaffold them in P9-04. Credentials are write-only; configured status is safe metadata. Settings Domain accordion interaction is owned by `docs/frontend/component-contracts.md` and `docs/frontend/interaction-state-catalog.md`; production-boundary Playwright acceptance remains P12-07.

## Navigation and draft preservation

- Route changes are initiated by router navigation, not location assignment.
- URL parameters contain only opaque safe refs, enums, positive page numbers, and allowlisted filters.
- Transcript drafts are keyed by safe conversation refs in tab-memory feature stores only. Reload may discard an uncommitted draft; logout or identity change always clears it.
- Passwords, drafts, composer-ref tokens, source excerpts, answers, and assembled prompts are never stored in browser storage.
- Back/Forward restores selection but reauthorizes content. Cached data may paint only after current session identity matches its cache partition.
- A mutation in flight may continue across internal navigation; its completion updates server-derived caches but cannot display a toast in an unrelated session.

## Route acceptance

Every enabled route must pass:

1. anonymous, member, administrator, revoked-role, and expired-session entry where applicable;
2. direct deep link, reload, Back, and Forward;
3. initial loading, empty, ready, refresh failure, fatal failure, and forbidden;
4. desktop, narrow/320 CSS px, keyboard-only, and 200%/400% zoom;
5. two-user cache isolation and logout/back-navigation;
6. URL validation proving private identifiers and unsafe return paths are rejected.

`/database-visualize` proves authorized ready/empty/truncated/failure states, list/detail and canvas selection convergence, opaque `domain`/`node` URL state, and zero browser requests to LightRAG or private runtimes.
