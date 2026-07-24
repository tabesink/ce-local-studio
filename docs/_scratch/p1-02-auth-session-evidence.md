# P1-02 Authentication and Session Evidence

Date: 2026-07-24

Slice: P1-02

Requirements and cases: FR-01, M-01

Status: DONE

## Implemented behavior

- Retained Argon2id password hashing and fail-closed verification.
- Retained random opaque session tokens with SHA-256 hashes as the only stored
  token representation.
- Made initial-administrator bootstrap insert-only. Existing identities are
  never rehashed, promoted, or re-enabled from changed environment input.
- Removed administrator bootstrap from API replica lifespan.
- Added the explicit `python -m context_engine.bootstrap_admin` command and
  placed it after Alembic in the local development release sequence.
- Added row-locked presented-session revocation and replacement-session insert
  in one database commit.
- Changed login success JSON to the closed `{user}` projection with opaque ID,
  safe display name, role, and `disabled:false`; session internals are absent.
- Preserved independently revocable sessions for independent successful logins.

## Proof-first evidence

The initial PostgreSQL characterization failed because `seed_admin` replaced an
existing Argon2 hash and rewrote role/disabled state. After the insert-only
change, the service proof passed. A second characterization then failed because
API lifespan still created the configured administrator. After moving bootstrap
to the explicit command, that boundary passed.

One HTTP fixture initially created the presented cookie without TestClient's
host domain, producing two same-name cookies after successful replacement. The
fixture was corrected to `testserver.local`; no production behavior changed for
that test correction.

## Verification

Real PostgreSQL 16, empty disposable databases, Alembic head:

```text
.venv/bin/python -m pytest tests/test_postgres_foundation.py -q
.....                                                                    [100%]
5 passed
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

The only emitted warning is the dependency-owned Starlette notice that its
`TestClient` HTTPX compatibility import is deprecated.

## PostgreSQL assertions

- Same plaintext password produces distinct valid Argon2id hashes.
- Unknown user, wrong password, and disabled user produce the same safe HTTP
  status/code/message/fields tuple.
- Existing bootstrap identity survives changed bootstrap credentials, role,
  and disabled-state input without mutation.
- API startup does not create the configured administrator; the explicit
  command does.
- Presented session is revoked while its replacement is inserted, and only
  token hashes are persisted.
- A second login without a presented cookie remains independently active when
  the first replacement is revoked.
- User deletion cascades to owned sessions on PostgreSQL.
- Login cookie carries configured HttpOnly, Path, and SameSite attributes and
  does not appear in response JSON.

## Dependency boundaries retained

P1-03 still owns current-user/admin reauthorization and denial behavior. P1-05
still owns Host/Origin, CSRF bootstrap and binding, idle/absolute-expiry policy,
bounded last-use writes, login throttling, concurrent-session limits, and exact
logout cookie behavior. P10 owns production Compose/release orchestration of the
explicit bootstrap command. No completion credit for those surfaces is claimed
here.
