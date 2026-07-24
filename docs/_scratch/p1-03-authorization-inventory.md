# P1-03 Authorization and Ownership Brownfield Inventory

Date: 2026-07-24

Owner: P1-03

Status: DONE

Cases: FR-01, M-08, C-04, C-05

## Scope boundary

P1-03 owns authoritative current-session/current-user/administrator guards,
service-owned ownership predicates, indistinguishable not-found projection, and
the administrator-denial audit hook. P1-05 owns idle/absolute expiry policy,
bounded session touches, CSRF, ingress validation, and throttling. P1-06 owns
the reusable transactional protected-mutation audit primitive. Resource-specific
state and domain-compatibility checks remain with their feature phases.

## Disposition register

| Surface | Current evidence | Disposition | P1-03 action and proof |
| --- | --- | --- | --- |
| Current session guard | Loads the cookie hash, session row, and current user from PostgreSQL on every request; rejects absent, revoked, expired, deleted, or disabled state | retain-and-reverify | Prove disablement and revocation take effect on the next request; leave idle policy to P1-05 |
| Current user projection | `/auth/me` uses the authoritative guard but still returns lifted session expiry metadata | modify | Return only the closed `{user: CurrentUserDto}` runtime projection |
| Administrator guard | Uses the freshly loaded user role rather than cookie/header claims | retain-and-reverify | Prove member denial and administrator downgrade denial on the next request |
| Administrator denial audit | Records `security.admin_route_denied` with actor and request correlation before returning `403` | retain-and-reverify | Prove a safe denied audit row exists; broader transactional audit failure semantics remain P1-06 |
| Registered admin routes | Current route registration consistently declares `require_admin` | retain-and-reverify | Freeze a registration scan so newly exposed `/admin/*` routes cannot omit the guard |
| Conversation ownership helper | `get_owned_conversation` combines conversation ID and `owner_user_id` in one query and raises one service not-found result | retain-and-reverify | Prove unknown and cross-owner IDs produce the same public status/code/message/fields after canonical error translation |
| Conversation list/mutations | List filters by owner; get/update/delete call the owner-filtered helper | retain-and-reverify | Prove one user cannot read or mutate another user's row; administrator role grants no member-conversation access |
| Generic ownership abstraction | No repository-level authorization framework exists | retain absence | Keep authorization in services; do not introduce a generic helper that can be called without a resource-specific owner predicate |
| Client-supplied authority | No dependency trusts identity/role headers or browser-selected ownership | retain absence | Continue deriving all authority from the session hash and database state |

## Completed evidence strategy

Add a PostgreSQL 16 HTTP scenario using real session cookies and rows. Capture
the lifted `/auth/me` response as the expected red baseline, then prove exact
identity projection, disabled/revoked session denial, member and downgraded-admin
`403`, safe denial audit correlation, cross-owner/unknown `404` equivalence,
and administrator non-ownership. Add a static route-registration assertion for
all active `/admin/*` operations without claiming future/deferred routes.
