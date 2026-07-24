# P2-03 Synthesis/Embedding Validation and Immutable Dimensions Inventory

Date: 2026-07-24

Owner: P2-03

Status: DONE - implemented and proven 2026-07-24

Requirements and cases: FR-02; A-02; schema invariant
`docs/database-schema.txt` critical invariant 2; HTTP catalog
`PATCH /admin/runtime-settings/model-profiles/{id}` (“used embeddings immutable”)

## Scope

Close the P2-01/P2-02 deferral for immutable embedding-dimension rules and
complete synthesis/embedding/defaults validation beyond the current in-use
delete fence:

- Reject mutation of an embedding profile that any domain already references
  (dimensions, model name, and other patch fields — used embeddings are
  immutable).
- Keep creating new catalog profiles allowed; domain embedding-profile
  replacement remains out of scope (no domain patch of `embeddingProfileId`;
  re-index workflow is a later approved change).
- Enforce embedding/synthesis dimension rules at the service boundary
  (embedding requires positive dimensions; synthesis forbids dimensions;
  catalog membership unchanged).
- Keep singleton runtime-defaults validation: active synthesis must be a
  synthesis profile with a ready provider; parser readiness unchanged.
- Prove A-02 at disposable PostgreSQL 16 and HTTP admin PATCH boundaries.

Out of scope: Settings UI/`If-Match` adoption (P9); domain lifecycle create/start
ownership beyond the embedding-profile resolve gate already used by domain
create (P3); A-13 frozen operation execution inputs (P4/P5/P7); inventing new
HTTP `ErrorCode` values beyond the established service code
`model_profile_in_use` (catalog closure of runtime-config codes remains a
known residual).

## Disposition register

| Surface | Current evidence | Disposition | P2-03 action and completion proof |
| --- | --- | --- | --- |
| `_reject_if_embedding_profile_in_use` on update/delete | Rejects domain-referenced embedding updates/deletes via inspector + raw SQL; no A-02 proof | modify | Prefer ORM domain reference check; prove update of domain-referenced embedding fails with `409 model_profile_in_use`; unused embedding still patchable |
| `_validate_model_profile` | Requires/forbids dimensions by kind; does not reject non-positive dimensions before DB | modify | Reject `vector_dimensions <= 0` at service boundary; keep catalog + DB checks |
| Runtime defaults update | Synthesis-kind + provider readiness gates exist | retain-and-reverify | Prove embedding profile cannot become active synthesis; ready synthesis/parser paths remain green |
| `TrustedRuntimeResolver.resolve_embedding_profile` | Validates embedding kind, dimensions present, provider configured | retain-and-reverify | Prove invalid/non-embedding/unready embedding resolve fails closed |
| Domain `embedding_profile_id` mutation | No admin PATCH replaces a domain’s embedding profile after create | retain-and-reverify | Keep absence; A-02 “replace A’s profile” remains impossible without a later re-index contract |
| Safe `inUse` projection | Includes defaults, active synthesis, and domain references | retain-and-reverify | Prove domain-referenced embedding projects `inUse: true` |

## Retained invariants

- Embedding profiles require positive vector dimensions; synthesis profiles omit
  dimensions.
- A domain’s embedding profile/dimensions never change after domain creation.
- Used embedding profiles cannot be patched or deleted; new catalog profiles may
  still be created.
- Protected mutations and required audit rows still commit together.
- Credentials never appear in admin snapshots.

## Gaps closed by task-owned evidence

1. Unit proofs for non-positive dimension rejection, domain-referenced update
   denial, unused-profile update success, and defaults/embedding resolve gates.
2. Disposable PostgreSQL 16 proof that a domain-referenced embedding rejects
   dimension/model patch and delete while a new unused catalog profile remains
   mutable/deletable.
3. HTTP A-02 proof: admin PATCH of a used embedding returns `409
   model_profile_in_use` with `If-Match`; create of another catalog profile
   still returns `201`.
