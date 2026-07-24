# P2-03 Synthesis/Embedding Validation and Immutable Dimensions Evidence

Date: 2026-07-24

Slice: P2-03

Requirements and cases: FR-02; A-02; schema critical invariant 2;
HTTP `PATCH /admin/runtime-settings/model-profiles/{id}` used-embedding
immutability

Status: DONE

## Implemented and retained behavior

- Embedding profile validation now rejects missing and non-positive
  `vector_dimensions` before catalog membership (`vector_dimensions_required` /
  `vector_dimensions_invalid`); synthesis still forbids dimensions.
- Domain reference detection for used embeddings uses the ORM `Domain` query
  instead of inspector/raw SQL, so update/delete fences and `inUse` projection
  work against the baseline `domains` table.
- Domain-referenced embedding profiles remain immutable under PATCH (name,
  model name, dimensions) and DELETE with `409 model_profile_in_use`; unused
  catalog embeddings remain creatable and patchable.
- Runtime defaults continue to reject embedding profiles as active synthesis;
  `TrustedRuntimeResolver.resolve_embedding_profile` rejects synthesis profiles
  and unready providers.
- No Alembic revision was required; DB check
  `ck_model_profiles_vector_dimensions_positive` remains the persistence backstop.

## Proof-first evidence

Unit proofs first failed for non-positive dimensions (catalog miss) and
domain-referenced update (RecordingSession lacked `get_bind`). After the
service changes, unit coverage proves non-positive rejection, A-02 update
denial with `inUse: true`, embedding-as-synthesis denial, and embedding resolve
fail-closed paths. PostgreSQL 16 then proved domain-referenced dimension/name
denial, unused-profile create/rename, DB zero-dimension rejection, defaults
gate, and HTTP A-02 `409` plus successful create of another catalog embedding.

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
.....................................                                              [100%]
37 passed
```

Focused counts: 11 unit runtime-config proofs, 3 PostgreSQL runtime-config
proofs (P2-01/P2-02 retained plus P2-03 A-02), plus foundation/audit/schema/
health regressions on head `b7e2a91c04d8`.

## PostgreSQL / HTTP assertions

- Domain row referencing `openai-embedding-default` projects `inUse: true`.
- Service PATCH of dimensions/model name or name-only on that profile returns
  `409 model_profile_in_use` without bumping version or changing stored
  dimensions.
- Delete of the domain-referenced embedding returns `409 model_profile_in_use`.
- Creating and renaming an unused catalog embedding succeeds with a version bump.
- Activating an embedding profile as active synthesis returns
  `invalid_active_synthesis_profile`.
- Direct SQL `vector_dimensions = 0` fails the positive-dimensions check.
- HTTP admin PATCH of the used embedding with valid `If-Match` returns `409
  model_profile_in_use`; HTTP create of another catalog embedding returns `201`
  with `inUse: false`.

## Rollback and restore boundary

No schema migration landed. Service behavior is forward-compatible with head
`b7e2a91c04d8`. Populated legacy compatibility remains blocked under P12-01.

## Boundaries retained

- P3 owns domain lifecycle create/start/stop/delete and must not introduce an
  in-place domain embedding-profile replacement without an approved re-index
  workflow.
- P9 owns Settings UI adoption of closed DTO field names and stale-revision
  recovery copy.
- Runtime-config service error codes such as `model_profile_in_use`,
  `vector_dimensions_invalid`, and `provider_not_ready` remain outside the
  closed HTTP `ErrorCode` catalog row; catalog closure is a contract residual,
  not invented here.
- A-13 frozen operation execution inputs remain with P4/P5/P7.
