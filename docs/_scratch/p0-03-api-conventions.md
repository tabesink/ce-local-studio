# P0-03 API Convention Evidence

Date: 2026-07-23  
Status: complete for the bounded P0-03 convention package; feature-level adoption remains dependency-owned.

## Authority and reviewed baseline

The governing sources are `AGENTS.md`, `docs/contracts/http-api-catalog.md`, `docs/contracts/dto-schema-catalog.md`, `docs/architecture/api-and-integration-flows.md`, and the reviewed no-Wiki/observability reference package. The reviewed reference carried the same unresolved convention gap as the root package: it named `ErrorCode` without closing the common HTTP union.

The lifted runtime already generated server request IDs and usually emitted a safe error shape, but it also:

- allowed production route registration to use a settings-selected API prefix while generation independently used `/api/v1`;
- allowed the request-ID response header name to vary through settings;
- serialized a timezone-aware datetime as an invalid value such as `+00:00Z`;
- generated only `dependency_unavailable` as the entire shared `ErrorCode` schema;
- showed an error example without the required `fields` member.

## Bounded completion decision

P0-03 defines and proves only conventions shared by later vertical slices:

1. production product routes have one non-configurable `/api/v1` prefix; health remains outside it;
2. the server generates an opaque 1..80 request ID, emits exactly `X-Request-ID`, never adopts a caller value, and repeats it in error bodies;
3. the four inner error members `code`, `message`, `requestId`, and `fields` are required, and the Phase 1 HTTP code union is closed in the DTO catalog and generated schema;
4. public datetimes serialize as whole-second RFC 3339 UTC with `Z`, converting aware offsets and treating lifted naive database datetimes as UTC at the serialization boundary.

P0-03 does not implement endpoint-specific ETags, `If-Match`, idempotency claims, authorization outcomes, cache policy, or feature error transitions. Those remain with P1 and P3-P7. It also does not claim route/response parity or SSE generation, which remain P0-06/P7 work.

## Implementation and proof

- `context_engine.api.contract_app` owns the canonical prefix and request-ID header constants. Route registration accepts no alternate prefix, and production plus generation call the same registrar.
- `context_engine.api.conventions.format_utc_timestamp` is the shared serializer used by the lifted public DTO projections through `services.auth.iso_utc`.
- `public_schemas.ErrorCode` and the regenerated OpenAPI/TypeScript artifacts carry the catalogued Phase 1 HTTP union.
- The authoritative HTTP example now contains the required empty `fields` record.
- `tests/test_api_conventions.py` proves prefix immutability, caller request-ID rejection, response/error correlation, the 1..80 bound, and naive/UTC/offset timestamp normalization.
- Existing health and malformed-login tests prove the generated closed envelope and safe fixed validation-field messages without echoing submitted content.

Focused verification after regeneration:

- API convention, health, identity-request, and generated-contract tests: 28 passed.
- Full root gate: passed against the final source state.
- Backend: lint passed; 45 tests passed.
- Generated OpenAPI/TypeScript live comparison and adversarial stale-artifact fixtures: passed.
- Frontend: typecheck, 53 tests, and production build passed.
- Backend Docker image build and Compose configuration: passed.
- Stable authority/implementation/generated/test manifest SHA-256: `b15b833cacda574b896df37bbaa23c4925cd9570735443e855a9e652ee3e1462`.

Known non-blocking inherited warnings remain: the Starlette TestClient/httpx deprecation, six high-severity npm audit findings, Node's module-type warning, and Next's middleware-file deprecation.

The requested structured code-review workflow could not resolve its mandatory diff base because this extracted workspace has no Git metadata. Per that workflow's fail-closed rule, no branch-diff review is claimed. A bounded audit of the exact files above found no additional actionable defect; the full gate was rerun afterward.

## Remaining adoption boundary

Several lifted feature services still emit historical capability codes and responses that are not registered as closed OpenAPI error schemas. They do not gain contract authority from this task. P0-06 and the owning P1/P3-P7 vertical slices must replace or explicitly approve them while synchronizing route models, generated clients, fixtures, and behavior tests.

DRIFT-18 remains open: P0-03 defines the concurrency and idempotency vocabulary only; real PostgreSQL transaction/race evidence belongs to the feature packages.
