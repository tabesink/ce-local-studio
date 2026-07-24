# P1-03 Authorization and Ownership Evidence

Date: 2026-07-24

Slice: P1-03

Requirements and cases: FR-01, M-08, C-04, C-05

Status: DONE

## Implemented and retained behavior

- Retained database-backed current-session and current-user loading on every
  request.
- Retained current-role administrator checks and safe denied audit writes.
- Retained service-owned conversation queries that combine resource ID and
  owner ID in one SQL predicate.
- Retained the rule that administrator role does not imply member-conversation
  ownership.
- Removed lifted session-expiry metadata from `/auth/me`; it now returns only
  the authoritative closed user projection.
- Added a guard-registration assertion covering every active `/admin/*` route.
- Added real PostgreSQL HTTP evidence for disablement, role downgrade, denial
  audit, and owner isolation.

## Proof-first evidence

The initial `/auth/me` PostgreSQL test failed because the response included
`session.expiresAt`. Removing that lifted field made the focused boundary pass.
The ownership scenario then established that unknown and cross-owner resources
already shared the approved `conversation_not_found` code and safe
`Conversation not found.` message. Two test expectations initially used a
generic not-found variant and were corrected without production changes.

## Verification

Real PostgreSQL 16, migrated disposable databases plus active route scan:

```text
.venv/bin/python -m pytest tests/test_postgres_foundation.py -q
........                                                                 [100%]
8 passed
```

Focused identity and generated-contract regression:

```text
.venv/bin/python -m pytest \
  tests/test_identity_request_contract.py \
  tests/test_authoritative_dto_components.py \
  tests/test_generated_contract_gate.py -q
..........................                                               [100%]
26 passed
```

The only warning is the dependency-owned Starlette `TestClient` HTTPX
compatibility deprecation.

## PostgreSQL and HTTP assertions

- `/auth/me` returns only opaque ID, safe display name, current role, and
  `disabled:false` for an enabled authenticated user.
- Disabling that user takes effect on the next request and returns the canonical
  unauthenticated envelope.
- A member is denied an administrator endpoint with canonical `403`.
- Downgrading an administrator in PostgreSQL takes effect on the next request
  using the same session and returns canonical `403`.
- Both denials persist safe `security.admin_route_denied` rows with actor,
  denied outcome, safe error code, and request correlation.
- Cross-owner and unknown conversation IDs have identical status, code,
  message, and fields.
- An administrator receives the same non-owner response for a member's
  conversation, while the actual owner succeeds.
- Every active registered `/admin/*` route directly depends on
  `require_admin`.

## Boundaries retained

P1-05 still owns Origin/CSRF, idle and absolute expiry policy, bounded session
touch, and throttling. P1-06 owns reusable transactional audit failure behavior
for protected mutations. P7 owns turn/stream ownership races and durable replay
isolation. Resource-specific authorization beyond conversations remains with
its feature phase.
