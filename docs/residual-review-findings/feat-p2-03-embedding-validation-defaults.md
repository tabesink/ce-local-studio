# Residual review findings — feat/p2-03-embedding-validation-defaults

Source review: interactive `/ce-work` P2-03 defect-first pass (2026-07-24)

Applied:

1. Non-positive embedding dimensions now raise approved HTTP `validation_error`
   instead of inventing `vector_dimensions_invalid`.

Accepted residuals:

1. Pre-existing runtime-config service codes (`model_profile_in_use`,
   `provider_not_ready`, `vector_dimensions_required`,
   `vector_dimensions_not_allowed`, `model_profile_not_in_catalog`, and peers)
   remain outside the closed HTTP `ErrorCode` catalog in
   `docs/contracts/dto-schema-catalog.md`. Catalog closure is a contract
   residual; this slice did not invent additional codes beyond the approved
   `validation_error` path for non-positive dimensions.
2. In-place domain embedding-profile replacement remains impossible and stays
   with P3 / a separately approved re-index workflow (A-02).
3. Settings UI DTO/`If-Match` adoption remains with P9.
