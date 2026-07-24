# P2-02 Credential Encryption and Safe DTO Projection Evidence

Date: 2026-07-24

Slice: P2-02

Requirements and cases: FR-02; A-01; `If-Match` / `428` / `409 stale_revision`
concurrency vocabulary

Status: DONE

## Implemented and retained behavior

- Added persisted `version integer NOT NULL DEFAULT 1 CHECK >= 1` on
  `provider_configs`, `model_profiles`, and `runtime_settings` (schema text,
  Alembic `b7e2a91c04d8`, ORM, readiness head).
- Closed admin projections now match `ProviderSummaryDto` /
  `ModelProfileDto` / `RuntimeSettingsDto` (`kind`/`configured`/`displayName`/
  `credentialUpdatedAt`/`inUse`/`version`).
- Credential rotate encrypts with Fernet `CONFIG_ENCRYPTION_KEY`, bumps version
  under `SELECT FOR UPDATE`, and commits through protected mutation + audit.
- Catalogued mutations require strong `If-Match`; missing/malformed → `428
  validation_error`; stale → `409 stale_revision`; success returns strong `ETag`
  and `private, no-store` cache policy.
- Regenerated OpenAPI/TypeScript so runtime-settings responses reference the
  closed DTO wrappers.

## Proof-first evidence

Unit proofs cover closed provider projection without secrets, Fernet round-trip
and wrong-key fail-closed decrypt, `If-Match` parse, and stale rotate rejection
before commit. PostgreSQL 16 then proved version check constraints, encrypt-at-
rest rotate, closed snapshot shapes, sequential stale denial, concurrent
winner/loser race, and HTTP A-01 `428`/`409`/`200` with `ETag`.

## Verification

```bash
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres \
app/.venv/bin/python -m pytest \
  tests/test_runtime_config_service.py \
  tests/test_postgres_runtime_config.py \
  tests/test_postgres_foundation.py \
  tests/test_postgres_audit.py \
  tests/test_audit_service.py \
  tests/test_phase_one_schema_scope.py \
  tests/test_health_contract.py \
  tests/test_authoritative_dto_components.py -q
```

Observed:

```text
...................................                                      [100%]
35 passed
```

Focused counts: 7 unit runtime-config proofs, 2 PostgreSQL runtime-config proofs
(including A-01 race/HTTP), plus 26 focused foundation/audit/schema/health/DTO
regressions on head `b7e2a91c04d8`.

Also: `bash scripts/check-generated-contracts.sh` → PASS.

## PostgreSQL assertions

- Fresh install reaches single head `b7e2a91c04d8` with positive-version checks
  on the three runtime-config tables.
- Rotate writes ciphertext distinct from plaintext; decrypt recovers the secret;
  snapshots never include ciphertext or plaintext.
- Snapshot providers/profiles/settings expose only closed catalog fields.
- Stale `expected_version` / `If-Match` loses with `409 stale_revision` and no
  secret rewrite; concurrent same-version rotates converge to one winner.
- HTTP missing `If-Match` returns `428 validation_error`; success returns
  `ETag: "<version>"` and closed `ProviderSummaryDto` without credentials.

## Rollback and restore boundary

Revision `b7e2a91c04d8` downgrades by dropping the three version check
constraints and columns. Populated legacy compatibility remains blocked under
P12-01. Credential ciphertext encrypted under the prior key remains readable
only with that key; this slice does not invent a previous-key decrypt window.

## Boundaries retained

- P2-03 owns immutable embedding-dimension rejection when a domain already
  references a profile, beyond the current in-use delete/`inUse` fence.
- P9 owns Settings UI adoption of closed DTO field names, `If-Match`/`ETag`, and
  stale-revision recovery copy (lifted `settings-panel` still uses
  `providerKind`/`isConfigured` locally).
- P8-01 owns broad protected-mutation allowlist coverage and sink privacy scans.
- CSRF previous-key window remains a separate ingress residual, not a
  credential-encryption key window.
