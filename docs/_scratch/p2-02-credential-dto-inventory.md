# P2-02 Credential Encryption and Safe DTO Projection Inventory

Date: 2026-07-24

Owner: P2-02

Status: DONE - implemented and proven 2026-07-24

Requirements and cases: FR-02; A-01; concurrency vocabulary from
`docs/contracts/http-api-catalog.md` (`If-Match` → `428` / `409 stale_revision`)

## Scope

Close the P2-01 deferrals for provider credential encryption/rotation contract
proof and closed public projections:

- Encrypt replacement credentials with the deployment Fernet key; never project
  plaintext or ciphertext.
- Project `ProviderSummaryDto` / `ModelProfileDto` / `RuntimeSettingsDto`
  including `version`, `configured`, `displayName`, `inUse`, and
  `credentialUpdatedAt`.
- Persist monotonic `version` on the three runtime-config tables; serialize into
  strong `ETag`; require `If-Match` on catalogued mutations; reject missing with
  `428` and stale with `409 stale_revision`.
- Prove A-01 races at the PostgreSQL boundary.

Out of scope: immutable embedding edit rules beyond the current in-use fence
(P2-03); CSRF previous-key window; inventing a credential-encryption previous-key
env var without contract; domain/source/conversation ETag adoption; broad
OpenAPI response adoption for non-runtime-settings routes.

## Disposition register

| Surface | Current evidence | Disposition | P2-02 action and completion proof |
| --- | --- | --- | --- |
| Fernet `SecretCrypto` + `rotate_provider_credential` | Encrypt/decrypt and protected-mutation rotate exist; no version fence or closed DTO | modify | Require `If-Match`/expected version; prove ciphertext at rest, decrypt for trusted resolver only, write-only request body, atomic audit |
| Safe projections | Lifted `providerKind`/`isConfigured`/`isDefault` shapes | replace | Project closed catalog DTOs; snapshot leak scan for secrets |
| Optimistic concurrency | No `version` column; no `If-Match`/`ETag` handlers | add | Schema/migration/ORM `version >= 1`; row lock + bump; HTTP `428`/`409`/`ETag` |
| Admin runtime-settings routes | Free-form dict responses | modify | Return closed DTO wrappers; set strong `ETag` on mutating successes |
| `docs/database-schema.txt` | Timestamps only for the three tables | modify | Record `version integer NOT NULL CHECK >= 1` with default 1 |

## Retained invariants

- Credentials remain write-only request fields and never appear in responses.
- `CONFIG_ENCRYPTION_KEY` stays outside product tables and distinct from CSRF keys.
- Protected mutations and required audit rows still commit together.
- Insert-only catalog seed must not rewrite ciphertext or bump version on existing rows.

## Completed evidence design

1. Unit proofs for closed projection shape, Fernet round-trip / wrong-key failure,
   missing/stale `If-Match` parsing, and version bump on rotate.
2. Disposable PostgreSQL 16 proof of version columns, encrypted rotate, closed
   snapshot, sequential and concurrent stale-revision losers, and HTTP A-01
   `428`/`409`/`200` with `ETag`.
