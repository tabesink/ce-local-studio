# Known Residuals — feat/p5-03-index-eligibility

Source review: focused P5-03 Bugbot pass on branch tip after initial commit;
high finding (wrong OpenAPI response model) and medium finding (version bump)
applied in follow-up commit.

## Applied from review

1. Index retry/cancel `response_model` switched from
   `AdminSourceMutationResponse` (`source`+`operation`) to
   `AdminSourceDetailResponse` (`{source}` only) to match
   `http-api-catalog.md` and regenerated OpenAPI/TypeScript.
2. Public index-state transitions bump `source.version` so ETag/`version`
   tracks `queued`/`processing`/`ready`/`failed`/`cancelled` changes.

## Residual risks (deferred owners)

1. Process-wide `_NATIVE_LIGHTRAG_LIFECYCLE_LOCK` retained — per-domain
   concurrency proof remains open under DRIFT-27.
2. Idempotency-Key transport persistence for index retry — shared residual
   with P4-04; no approved idempotency store yet.
3. Member Library / Evidence document routes remain P6/P9.
4. Worker graceful stop-claim drain remains P10-03 (DRIFT-31).
