# Known Residuals — P2-02 review

Source: post-implementation review of `d98a1c9` + fix `settings-version-on-activate` (2026-07-24)

Verdict: approve-with-nits after applying P1 settings version bump on auto-activation.

## Applied in-slice

1. Credential rotate auto-activation now locks `runtime_settings`, mutates under
   `SELECT FOR UPDATE`, and increments `version`; proven by PostgreSQL stale
   settings PATCH after first OpenAI rotate.

## Accepted residuals

1. HTTP `428`/`409`/`ETag` proof is focused on provider credential PUT; model-
   profile and runtime-settings PATCH reuse the same parser/service path without
   separate HTTP fixtures.
2. Settings UI (`settings-panel`) still uses lifted `providerKind` /
   `isConfigured` and does not send `If-Match`; closed DTO/`ETag` adoption remains
   with P9.
3. Immutable embedding-dimension rejection when a domain already references a
   profile remains with P2-03.
4. CSRF previous-key window and inventing a credential-encryption previous-key
   env var remain out of contract for this slice.
5. `POST .../model-profiles` still lacks catalogued `Idempotency-Key` enforcement.
