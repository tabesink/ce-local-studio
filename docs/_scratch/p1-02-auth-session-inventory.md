# P1-02 Authentication and Session Brownfield Inventory

Date: 2026-07-24

Owner: P1-02

Status: DONE

Cases: FR-01, M-01

## Scope boundary

P1-02 owns the existing `users` and `auth_sessions` persistence, Argon2
password handling, insert-only initial-administrator bootstrap, opaque cookie
session creation, presented-session replacement, revocation, and the login
success projection.

P1-03 owns authoritative current-user/admin dependencies and denial behavior.
P1-05 owns Host/Origin and CSRF enforcement, session-bound CSRF, idle-expiry
cadence, login throttling, concurrent-session limits, and hostile-ingress proof.
P1-04 owns bootstrap/readiness reporting. Those behaviors are not implemented
or credited here.

## Disposition register

| Surface | Current evidence | Disposition | P1-02 action and proof |
| --- | --- | --- | --- |
| `users` and `auth_sessions` schema | Baseline migration and ORM include required IDs, roles, disabled state, token hash, expiry, revocation, creation, and last-use fields | retain-and-reverify | Prove constraints, opaque hash-only persistence, expiry, revocation, and user cascade behavior on PostgreSQL 16 |
| Password hashing | `security.py` uses Argon2id with per-password salt and fail-closed verification | retain-and-reverify | Prove valid verification, wrong-password denial, distinct hashes for the same password, and no raw password persistence |
| Session token generation and hashing | 48-byte URL-safe random token; SHA-256 hash persisted | retain-and-reverify | Prove returned token differs from the stored 64-character hash and raw tokens do not appear in rows |
| Initial administrator bootstrap | `seed_admin` inserts when absent but rewrites the password, role, disabled state, and timestamps whenever the username already exists | modify | Make bootstrap insert-only; restart or changed environment input must not rewrite, promote, or re-enable an existing identity |
| Credential authentication | Enabled users verify through Argon2 and unknown/disabled/wrong-password states all return the same internal absence result | retain-and-reverify | Prove generic HTTP denial without existence or disabled-state disclosure |
| Session creation transaction | New session creation commits independently and does not revoke a presented session | modify | Revoke an active presented session and insert its replacement in one transaction; unrelated sessions remain independently revocable |
| Login cookie | Route sets the configured opaque `ce_session` cookie with HttpOnly, Secure, SameSite, path, and max-age | retain-and-reverify | Prove cookie attributes and that neither response JSON nor persistence exposes the raw token |
| Login success DTO | Lifted response exposes `username`, `isDisabled`, and session expiry, which conflicts with the closed `{user: CurrentUserDto}` contract | modify | Return only opaque user ref, safe display name, role, and `disabled:false`; do not expose session internals |
| Current-session last-use and expiry | Dependency enforces revocation and absolute expiry but writes `last_used_at` on every request | defer to P1-03/P1-05 | Do not claim bounded idle-expiry or authoritative role-revocation proof in P1-02 |
| CSRF/bootstrap and logout semantics | CSRF bootstrap is absent and logout does not yet match authenticated `204` plus dual-cookie expiry | defer to P1-05 | Preserve explicit dependency ownership; no partial CSRF protocol in P1-02 |

## Completed evidence strategy

Strengthen the existing identity tests with service-level bootstrap/password
characterization and add a PostgreSQL 16 HTTP/session scenario. Observe failures
for bootstrap rewrite, stale-session survival, and the lifted response before
changing production code. The real-boundary proof must show atomic replacement,
hash-only persistence, independent parallel sessions, generic denial, and the
closed login projection.
