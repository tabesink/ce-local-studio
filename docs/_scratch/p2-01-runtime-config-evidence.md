# P2-01 Runtime Configuration Schema and Services Evidence

Date: 2026-07-24

Slice: P2-01

Requirements and cases: FR-02; service readiness for A-02/A-13 defaults

Status: DONE

## Implemented and retained behavior

- Retained baseline `provider_configs`, `model_profiles`, and `runtime_settings`
  schema/ORM checks (closed provider/profile/parser kinds, embedding/synthesis
  dimension rules, singleton `runtime_settings.id = 1`).
- Made `seed_runtime_config` insert-only so restart/re-seed cannot rewrite
  provider labels, credential flags, ciphertext, or catalog profile names.
- `ensure_runtime_settings` now flushes without an early independent commit.
- Adopted `commit_protected_mutation` for provider credential rotate, model
  profile create/update/delete, and runtime-defaults update when an audit
  context is supplied.
- Reject deletion of default catalog model profiles in addition to active
  synthesis and domain-referenced embedding profiles.
- Kept Fernet crypto helpers and lifted snapshot shapes; authoritative
  `ProviderSummaryDto` / version / `If-Match` adoption remains P2-02.

## Proof-first evidence

Unit proofs cover default-catalog delete rejection, protected-mutation rollback
when audit validation fails on create, and synthesis activation rejection when
the provider is not configured. PostgreSQL 16 then proved schema constraints,
insert-only seed, catalog create+audit, default-delete denial, synthesis and
Reducto readiness gates, and snapshot absence of ciphertext/plaintext secrets.

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
  tests/test_health_contract.py -q
```

Observed:

```text
...........................                                              [100%]
27 passed
```

Focused counts: 3 unit runtime-config proofs, 1 PostgreSQL runtime-config proof,
plus 23 focused foundation/audit/schema/health regressions on the same head.

## PostgreSQL assertions

- Fresh install reaches single head `c4e8f1a02b93` with the three runtime-config
  tables and named check constraints.
- First seed inserts four providers, the closed model catalog, and singleton
  runtime settings; second seed preserves customized OpenAI display name and
  sentinel ciphertext.
- Invalid embedding-without-dimensions and `runtime_settings.id = 2` inserts
  fail at the database boundary.
- Creating a non-default catalog synthesis profile writes
  `runtime_settings.model_profile_created` with the request ID.
- Default synthesis profile delete returns `409 model_profile_in_use`.
- Synthesis activation requires a configured provider; Reducto parser activation
  requires Reducto credentials; successful defaults write
  `runtime_settings.defaults_updated`.
- Snapshot providers expose only `providerKind` / `isConfigured` and never
  ciphertext or plaintext credentials.

## Rollback and restore boundary

No new Alembic revision was required; the retained baseline schema already
matches the authoritative table/check contract for this slice. Service behavior
changes are forward-compatible with the current head. Populated legacy
compatibility remains blocked under P12-01.

## Boundaries retained

- P2-02 owns credential encryption/rotation contract proof, closed
  `ProviderSummaryDto` / `ModelProfileDto` / `RuntimeSettingsDto` projection,
  version/ETag/`If-Match` stale-revision behavior, and A-01 race coverage.
- P2-03 owns immutable embedding-dimension rules and defaults validation beyond
  the current in-use delete fence.
- P8-01 owns broad protected-mutation call-site allowlist coverage and privacy
  scans across sinks.
- P10 may later move catalog ensure out of API lifespan into an explicit
  release bootstrap step.
