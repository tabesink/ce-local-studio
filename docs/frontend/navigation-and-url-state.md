# Navigation and URL State Contract

This contract makes navigation deterministic and shareable without treating a URL as authorization. Query values are untrusted presentation hints. FastAPI reauthorizes every referenced resource.

## Canonical routes

| Route | Audience | Canonical URL state | Invalid or unauthorized state |
| --- | --- | --- | --- |
| `/` | all | none; redirect to `/chat` or `/login` | never render a second home surface |
| `/login` | anonymous | `next=<allowlisted-relative-url>` | authenticated users replace to `next` or `/chat` |
| `/chat` | member | `conversation`, `turn`, `evidence`, `domain` safe refs | remove the narrowest invalid value; preserve draft |
| `/documents` | member/admin | `domain`, `document`, `evidence`, positive `page` | close protected preview and show safe unavailable state |
| `/database-visualize` | member/admin | reserved `domain`, optional `node` safe ref | while graph contract is unavailable, drop both values and render deliberate unavailable state |
| `/settings` | authenticated | allowlisted `section`; admin sections require admin | select first permitted section |
| `/forbidden` | authenticated | none | provide return to `/chat`, not protected details |

Do not add nested `/documents/[id]`; document preview remains inline. Do not rename `/database-visualize`. New routes require the product and route/workspace contracts to change together.

`/database-visualize` is a reserved route, not an enabled graph capability. Until the HTTP catalog defines an approved graph endpoint and DTO, its parser drops `domain` and `node`, the route makes no graph/LightRAG request, and visual/browser tests cover only the deliberate unavailable state. When enabled, `node` remains the canonical selection key.

## URL value rules

- Safe refs are opaque API-issued strings. They may identify a document, evidence row, turn, domain, or node but are not database IDs, object keys, paths, provider URLs, or bearer tokens.
- `page` is a base-10 integer `1..100000`. Evidence remains the semantic anchor; page is a harmless initial hint.
- Do not encode excerpts, prompts, answers, filenames, usernames, errors, coordinates containing source internals, or serialized DTOs.
- Parse with one schema per route. Unknown keys are dropped on the next canonical replace.
- Preserve parameter order shown in the table so copied URLs and visual snapshots are stable.
- Never interpolate URL values into HTML or an API path without generated-client encoding.

## Canonicalization algorithm

1. Parse pathname against the route registry; unknown routes resolve to the product 404.
2. Parse only allowlisted keys and bounded values.
3. Apply role-visible defaults without fetching protected target details.
4. Fetch the route's primary resource through the typed client.
5. Reconcile dependent values left-to-right: domain -> conversation/document/page -> turn -> evidence.
6. If a dependency is stale, remove it and every child with `router.replace`; do not redirect to a different resource.
7. Render `loading`, `empty`, `safe failure`, or `ready`; a URL alone never yields `ready`.

Example: `/documents?document=doc_opaque&evidence=ev_opaque&page=18` may open page 18 only after the content and anchor endpoints authorize both refs. A `404`/`403` closes the viewer and displays “Evidence no longer available” plus request ID.

## History semantics

| Intent | History operation |
| --- | --- |
| Select primary route, conversation, or document | `push` |
| Select an allowlisted Settings admin section (`provider`, `domains`, `users`) | `push` |
| Select turn/evidence/node, filter, or page during viewer scroll | debounced `replace` |
| Open evidence from chat in Library | `push` to `/documents`; retain chat entry behind it |
| Close an inline panel | `replace` removing its dependent parameters |
| Invalid/unauthorized Settings `section` → General, or other auth/canonical cleanup | `replace` |

Browser Back restores the prior safe selection, then revalidates it. “Return to answer” uses Back when the preceding entry is same-origin `/chat`; otherwise it builds `/chat?conversation=<ref>&turn=<ref>&evidence=<ref>` from authorized safe refs. Never accept a free-form return URL.

## Route transitions

- Route change does not cancel a turn or operation. Only a contracted cancel action does.
- Preserve chat drafts plus selected refs in per-tab memory when navigating within the authenticated shell. Do not persist drafts in `sessionStorage`, `localStorage`, IndexedDB, or service-worker caches. Reload may discard them; logout or identity epoch change clears them.
- M-04/M-05: evidence click pushes Library state, expands viewer, resolves evidence anchor, focuses the viewer heading, then the region. Failure leaves the user on Library with a safe state.
- M-06: selecting a turn replaces `turn` and clears `evidence` before fetching its projection. A stale response cannot restore the old values.
- M-11: a redaction/authorization event removes document/evidence parameters, closes cached content, and retains a safe route-level notice.
- C-03: viewer parameters are local to a history entry; they never write shared source state.
- C-05: role refresh canonicalizes navigation immediately; it does not wait for a protected request to fail again.

## Authentication redirects

`next` must decode to a same-origin path in the route registry, contain no credentials, and be at most 2 KiB. Anonymous access stores no protected response. On `401`, clear the in-memory identity epoch and replace to `/login?next=<encoded-current-relative-url>`. On logout, replace to `/login` and prevent Back from rendering cached protected UI.

## Required tests

- Unit: schema parsing, canonical ordering, dependent-key cleanup, `next` open-redirect rejection, page bounds.
- Browser: Back/Forward revalidation; chat -> figure -> scoped PDF -> Back; draft preservation; role revocation; redaction while preview is open.
- Two-context: two members navigate the same source to different anchors without state crossover.
- Security: every safe ref is reauthorized and no protected query appears in safe server logs or referrer destinations.

Traceability: M-01, M-02, M-04 through M-06, M-11, C-03, and C-05.
