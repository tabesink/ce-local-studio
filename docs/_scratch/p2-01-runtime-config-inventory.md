# P2-01 Runtime Configuration Schema and Services Inventory

Date: 2026-07-24

Owner: P2-01

Status: DONE - implemented and proven 2026-07-24

Requirements and cases: FR-02; A-02 (service readiness only); A-13 (defaults owned here; freeze-at-operation remains later)

## Scope

This inventory is the required brownfield checkpoint for the P2-01
`provider_configs`, `model_profiles`, and `runtime_settings` migrations and
services slice. Existing files are evidence only. P2-01 receives completion
credit only after PostgreSQL 16 proves the authoritative schema constraints,
insert-only catalog/default seed, and transactional service mutations for
profiles and singleton runtime defaults.

P2-01 does not claim credential encryption/rotation contract proof or closed
`ProviderSummaryDto` / version / `If-Match` projection (P2-02), immutable
embedding-dimension rejection when a domain already references a profile
beyond the current in-use delete fence (P2-03 completion), admin OpenAPI
response-component adoption, or A-13 frozen-operation execution inputs owned
by P4/P5/P7.

## Disposition register

| Surface | Current evidence | Disposition | P2-01 action and completion proof |
| --- | --- | --- | --- |
| `provider_configs` / `model_profiles` / `runtime_settings` tables | Baseline migration and ORM match closed kinds, embedding/synthesis dimension checks, and singleton `id=1` | retain-and-reverify | Prove fresh-install head includes tables, check constraints, and FKs against PostgreSQL 16 |
| Catalog / singleton seed | `seed_runtime_config` inserts providers, catalog profiles, and singleton settings, but rewrites provider display/credential flags and profile names on every API lifespan call | modify | Make seed insert-only; prove restart/re-seed does not mutate existing rows or credentials |
| Model-profile service | Create/update/delete validate catalog membership and reject active-synthesis / domain-referenced deletes; uses ad-hoc `record`+`commit` | modify | Keep catalog/dimension validation; reject default-catalog deletes; adopt `commit_protected_mutation`; prove create/delete/update boundaries |
| Runtime-settings service | Patch updates active synthesis/parser with provider readiness; ad-hoc audit commit | modify | Keep readiness gates; adopt protected mutation; prove docling/reducto and synthesis activation paths |
| Credential rotate + crypto | Fernet encrypt/decrypt and rotate path exist | defer to P2-02 | Retain call sites; do not claim A-01 ETag/DTO/encryption boundary proof here |
| Safe public projections / ETag | Lifted `isConfigured` / `isDefault` shapes omit catalog `version`, `inUse`, `configured`, `displayName` | defer to P2-02 | Keep service-level safe helpers usable for tests; authoritative DTO/ETag adoption is P2-02 |
| Lifespan seed | API lifespan seeds runtime config and prompt templates | retain-and-reverify (insert-only) | Keep ensure-on-start for closed catalog after insert-only fix; explicit release bootstrap ownership remains available to P10 |

## Retained invariants

- Provider kinds are exactly `openai`, `bedrock`, `ollama`, and `reducto`.
- Model profiles are synthesis or embedding; embedding requires positive
  dimensions; synthesis forbids dimensions.
- Runtime settings are a singleton row (`id = 1`) with closed parser kinds.
- Protected mutations and their required audit rows commit together or roll
  back together.
- Credentials never appear in service snapshot projections used by admin GET.
- Default catalog profiles and the active synthesis profile cannot be deleted.

## Gaps closed by task-owned evidence

1. PostgreSQL 16 proof of schema checks/FKs/singleton for the three tables.
2. Insert-only seed that preserves existing provider credential material.
3. Protected-mutation adoption for profile create/update/delete and runtime
   defaults update.
4. Rejection of default-catalog profile deletion.
5. Focused unit plus disposable PostgreSQL service proofs for seed, profile,
   and defaults flows.

## Completed evidence design

The P2-01 proof will use the disposable PostgreSQL 16 harness pattern, upgrade
to the current Alembic head, seed runtime config twice, prove provider rows and
catalog profiles exist without credential rewrite, create a non-default catalog
profile with audit, activate synthesis/parser defaults only when providers are
ready, and reject default-profile deletion and invalid dimension rows at the
database boundary.
