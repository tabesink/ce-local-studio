# P1-05 Ingress, CSRF, Session Policy, and Throttling Inventory

Date: 2026-07-24

Owner: P1-05

Status: DONE - implemented and proven 2026-07-24

Requirements and cases: FR-01, M-01, C-05

## Stop condition

The normative behavior requires trusted BFF-peer/Host/Origin validation, signed
session-bound CSRF, absolute and idle expiry with bounded touches, and
multi-replica login throttling. The current authoritative contracts do not
specify:

1. PostgreSQL persistence for login throttle buckets or attempts;
2. the trusted private BFF peer/network configuration and canonical public
   origin setting contract;
3. CSRF signing-key ownership, rotation, or derivation policy; or
4. idle timeout, bounded-touch cadence, and optional concurrent-session limit
   configuration names/ranges.

`docs/database-schema.txt` has no throttle table. `Settings` exposes only cookie
name, Secure, SameSite, and one session TTL. Process-local counters would not be
a durable multi-replica correctness boundary. Reusing credential-encryption
keys for CSRF without authority would conflate key purposes. Trusting forwarded
public host/proto without a configured private-peer check would make caller
headers authoritative.

Per `AGENTS.md`, P1-05 cannot invent these persistence/configuration contracts.
The implementable route code is therefore not changed until an explicit
contract decision is approved.

## Disposition register

| Surface | Current evidence | Disposition | Required P1-05 action |
| --- | --- | --- | --- |
| Session cookie settings | Config validates `lax`, `strict`, or secure `none`; route sets HttpOnly, Path, Secure, SameSite, and no Domain | retain-and-reverify | Freeze fail-closed cookie combinations and exact attributes |
| CSRF bootstrap route | Generates a random token and sets readable `ce_csrf`, but token is unsigned and unbound | replace | Issue a signed opaque pre-auth token; rotate to session-bound token at login |
| Unsafe-request enforcement | No global Origin/CSRF enforcement exists | add | Validate trusted request path, exact allowed Origin, cookie/header equality, signature, binding, and replay semantics before route work |
| BFF/private-peer trust | No configured peer/CIDR or server-derived public host/proto validation exists in FastAPI | add after decision | Reject direct/untrusted peers and caller-forged forwarding/public-host headers |
| Absolute expiry | `auth_sessions.expires_at` is enforced on each request | retain-and-reverify | Pin it as absolute expiry and prove boundary behavior |
| Idle expiry | `last_used_at` is written on every request and is not used for expiry | modify after decision | Enforce configured idle timeout and update at a bounded cadence, including stream checkpoints owned by P7 |
| Login rotation | Presented session replacement is row-locked and atomic from P1-02 | retain-and-reverify | Compose with pre-auth/session-bound CSRF rotation and session-fixation denial |
| Logout | Revokes a presented token but is unauthenticated, returns lifted JSON, and expires only the session cookie | replace | Require current session plus valid Origin/CSRF, revoke first, expire both cookies, return `204` |
| Login throttling | No persistence, service, or schema contract exists | blocked | Add approved PostgreSQL durable bucket/attempt design keyed by verified client bucket plus normalized username hash |
| Concurrent session limit | No configured limit exists; independent sessions are supported | retain default | Keep unlimited independent sessions unless an approved optional limit is added |
| BFF header stripping and direct-public API denial | Frontend/BFF and deployment work remain open | defer to P9-05/P10 | FastAPI still validates its side; deployed topology proves direct access denial later |

## Recommended contract decision

Approve a coordinated internal security contract update before implementation:

- Add a PostgreSQL `login_throttle_buckets` authority keyed by a server-derived
  client-bucket hash plus normalized-username hash, with bounded window/failure
  state, `blocked_until`, update timestamp, and deterministic cleanup policy.
- Add fail-closed settings for canonical public origin, internal upstream Host,
  trusted private BFF peer networks, CSRF signing key/reference, idle timeout,
  and touch cadence, including production validation and test-only defaults.
- Define CSRF token signing/binding and key-rotation compatibility without
  exposing token structure publicly.
- Keep rate-limit responses generic `429` with safe `Retry-After`; never store
  raw usernames, client addresses, cookies, CSRF values, or passwords.

Approval must update `docs/database-schema.txt` and the applicable security and
deployment contracts before migration/service implementation. Deferral keeps
P1-05 blocked and prevents later P1/P9/P10 completion credit.


## Approved decision

The recommended coordinated contract change was explicitly approved on
2026-07-24. The normative schema/security/deployment documents now own the
throttle table, server-derived client bucket, trusted peer/public origin,
dedicated CSRF key, and bounded session/throttle settings. Migration, service,
middleware and hostile-ingress proof may proceed against that authority.
