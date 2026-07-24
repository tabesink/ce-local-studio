# P1-05 Ingress, CSRF, Session Policy, and Throttling Evidence

Date: 2026-07-24

Slice: P1-05

Requirements and cases: FR-01, M-01, C-05

Status: DONE

## Implemented and retained behavior

- Trusted BFF peer, internal Host, and public host/proto headers are enforced
  for `/api/v1/*` when ingress settings are configured.
- Unsafe methods require exact public `Origin`, cookie/header CSRF equality,
  signature verification, and binding (`preauth` for login; session-token hash
  otherwise).
- `GET /auth/csrf` issues a signed pre-auth CSRF cookie that is readable by the
  browser and returns `{csrfToken}` with `Cache-Control: private, no-store`.
- Login requires pre-auth CSRF under enforced ingress, rotates the session, and
  rotates CSRF to the new session binding.
- Logout requires an authenticated session plus session-bound CSRF, revokes
  first, expires both cookies, and returns `204`.
- Absolute expiry remains `expires_at`; idle expiry uses `last_used_at` with
  bounded touch cadence.
- Login throttling persists hashed client-bucket and username keys in
  PostgreSQL `login_throttle_buckets`, returns generic `429 rate_limited` with
  integer `Retry-After`, and never stores raw usernames, addresses, cookies,
  CSRF values, or passwords.

## Proof-first evidence

Unit coverage first pinned CSRF binding mismatches and hostile Origin/CSRF
rejection. PostgreSQL 16 HTTP proof then covered untrusted peer denial, CSRF
bootstrap attributes, wrong-origin login denial, login/session CSRF rotation,
authenticated logout `204`, durable throttle block after configured failures,
idle touch update, and idle expiry.

## Verification

Real PostgreSQL 16 disposable databases plus unit security tests:

```bash
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://.../postgres \
.venv/bin/python -m pytest \
  tests/test_postgres_ingress_security.py \
  tests/test_csrf_and_request_security.py -q
```

```text
.....                                                                    [100%]
5 passed
```

Focused P1 regression including prior foundation/identity/health/contract gates:

```bash
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://.../postgres \
.venv/bin/python -m pytest \
  tests/test_postgres_foundation.py \
  tests/test_identity_request_contract.py \
  tests/test_csrf_and_request_security.py \
  tests/test_postgres_ingress_security.py \
  tests/test_generated_contract_gate.py \
  tests/test_health_contract.py -q
```

```text
........................................                                 [100%]
40 passed
```

Generated contract snapshots:

```bash
bash scripts/check-generated-contracts.sh
```

```text
generated contract snapshots: PASS
```

## Boundaries retained

- Deployed direct-public API denial, BFF header stripping, and production
  ingress topology remain with P9-05/P10.
- Broad sink privacy scans remain with P8.
- Stream idle checkpoints remain with P7.
- Transactional audit helper breadth remains with P1-06/P8-01.
