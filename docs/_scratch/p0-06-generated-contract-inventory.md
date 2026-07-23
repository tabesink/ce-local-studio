# P0-06 Generated Contract Reproducibility Checkpoint

Date: 2026-07-23  
Status: partial P0-06 evidence; P0-05 bounded CI deliverable complete.

## Observed baseline

- `scripts/generate_openapi.py` overwrote one fixed artifact and had no check mode or alternate output.
- `app/contracts/openapi.json` and `app/client/src/lib/api/generated/openapi.ts` existed, but `scripts/verify.sh` did not regenerate or compare them.
- Browser capability modules mostly handwrite request, response, and SSE types.
- The current producer and chat client still implement the retired pilot `stage`, `token`, `evidence`, `done`, and `error` stream events. They do not implement the versioned envelope in `docs/contracts/sse-event-catalog.md`.

## Proof-first result

`app/tests/test_generated_contract_gate.py` was added before implementation. Its first run failed because:

1. `generate_openapi.py --check --output <stale-file>` ignored both arguments and returned success.
2. The root verification script did not invoke a generated-contract snapshot check.
3. `LoginRequest` remained handwritten in the browser.

The root-gate assertion was then strengthened and failed again before the adversarial snapshot-fixture runner was added.

The identity-request proof was added before changing `LoginRequest`. Its first run rejected none of the empty or over-limit username/password cases, and the generated component lacked all four length constraints. After implementation, route-level tests also prove invalid, missing, and extra fields return a safe `422 validation_error` without echoing submitted secrets or invoking authentication.

A review regression was also written before consolidating route assembly. It failed because the production app and generator independently included routers, which could allow production registration to drift while snapshot generation continued to pass.

## Implemented boundary

- `generate_openapi.py` now renders deterministic bytes, supports an alternate `--output`, and fails closed with `--check`.
- Production startup and generation share one side-effect-free contract route registrar and common API metadata; P0-03 subsequently removed the alternate-prefix seam so the registrar itself owns the non-configurable `/api/v1` prefix.
- `scripts/check-generated-contracts.sh` regenerates OpenAPI and TypeScript into a temporary directory and byte-compares both committed artifacts. Inherited artifact-path environment variables cannot redirect the production check.
- `scripts/tests/check-generated-contracts.sh` proves unchanged artifacts pass, independently corrupted OpenAPI and TypeScript artifacts fail, and inherited artifact-path overrides are ignored. Alternate artifacts require the explicit fixture-only argument.
- `scripts/verify.sh` invokes both the live comparison and adversarial fixtures after the pinned frontend dependency install.
- Browser `LoginRequest` now aliases the generated OpenAPI component instead of maintaining a duplicate shape; `/auth/login` is pinned to that component, username/password enforce the approved 1..320/1..1024 bounds, and the capability call is characterization-gated against a handwritten payload substitute.
- Every currently generated JSON request body used by the browser now crosses its capability adapter as a generated OpenAPI component: domain create; provider credential; model-profile create; runtime-settings patch; conversation title; composer discovery; and turn start. Transport-only wrapper fields remain local and response/event types are not falsely projected as generated while producer contracts still drift.
- The closed shared response vocabulary is now generated independently of route adoption: identity, provider/model/runtime configuration, domain, operation, source, document, conversation, turn, composer-ref, Evidence, and anchor components appear in committed OpenAPI and TypeScript. The shared registrar merges them collision-safely without adding a schema-only route or attaching them to handlers whose runtime projections still drift.
- Registered path templates and OpenAPI path-parameter names now use the authoritative camelCase names. Matched operations are regression-compared directly with the catalog, including its exact `{kind}` and `{id}` provider/model-profile placeholders; snake_case remains internal to Python handlers only.
- Health liveness/readiness now use closed generated response components and the contracted `live`/`ready` status values. Database readiness failure returns the approved closed `dependency_unavailable` code through the common error envelope, with a matching nonempty response/request ID. P0-03 subsequently closed the shared Phase 1 HTTP error-code union and regenerated it into both artifacts.
- Four lifted shortcuts absent from the catalog were removed transitively from backend registration/services, generated artifacts, browser adapters, and active tests: administrator user mutation, member source listing, raw source preview, and Evidence-to-source resolution. Settings users are read-only; member Library, governed preview, and Evidence document navigation render deliberate unavailable states until the replacement opaque routes land in P4/P6/P9.

## Registered-versus-authoritative delta

The semantic route comparison normalizes path-placeholder spelling before comparing the registered OpenAPI document with `http-api-catalog.md`. At this checkpoint, all 39 registered operations match the catalog, no registered operation is absent from it, and seven catalog operations are not yet registered.

Cataloged but not registered:

- `GET /auth/csrf`
- `GET /conversations/{conversationId}/turns/{turnId}/events`
- `POST /conversations/{conversationId}/turns/{turnId}:cancel`
- `GET /documents`
- `GET /documents/{documentRef}`
- `GET /documents/{documentRef}/content`
- `GET /evidence/{evidenceRef}/location`

The login request shape and bounds now align. Identity responses still have unresolved behavioral drift: login and `/auth/me` emit an undeclared `session` object and the lifted `username`/`isDisabled` projection instead of the closed `displayName`/`disabled:false` DTO; logout returns `200 {ok:true}` instead of `204`. These are not silently normalized by response filtering because doing so would break the current browser and pull P1 authentication/CSRF behavior into this bounded P0-06 slice. The seven absent catalog operations and identity contract conflict remain blockers for their owning vertical slices.

## Verification

- Focused generated-contract tests: 9 passed.
- Focused authoritative-component tests: 3 passed.
- Focused health contract tests: 3 passed.
- Focused identity request contract tests: 14 passed.
- Live OpenAPI and TypeScript regeneration comparison: passed.
- Adversarial stale OpenAPI and stale TypeScript fixtures: passed.
- Frontend typecheck: passed.
- Full root gate after transitive uncataloged-route removal: 55 backend tests and 51 frontend tests passed; reproducible OpenAPI/TypeScript snapshots, production frontend build, backend Docker build, and Compose validation passed.

## Remaining P0-06 boundary

P0-07 has now cleared the deferred-surface blocker: the active route tree, generated OpenAPI, production source/manifests and clean-install ORM target exclude later-release publication and product-observability surfaces. The remaining work below is contract parity, generated-client adoption and canonical SSE, not deferred-feature removal.


### Registered response-adoption matrix

The 39 registered operations are classified by owning vertical slice. A matching status code alone is not DTO adoption; the handler must also satisfy authorization, precondition, cache, error, and projection rules before attaching an authoritative response model.

| Registered group | Operations | Current P0 disposition | Owning slice |
| --- | ---: | --- | --- |
| health | 2 | adopted: closed live/ready components, including safe readiness failure | P1-04/P8-03 |
| authentication | 3 | defer: login/me expose lifted identity/session fields; logout status/body drifts; CSRF route is absent | P1-02/P1-03/P1-05 |
| admin users | 1 | defer: list projection is lifted; the uncataloged mutation was removed and the browser surface is read-only | P1-03/P9-04 |
| runtime configuration | 6 | defer: generated components exist, but current projections, ETags, credential rules, and lifecycle behavior are not proven | P2 |
| domains | 9 | defer: generated domain/operation components exist; lifecycle routes currently return the wrong projection and lack required concurrency/idempotency proof | P3 |
| source administration | 10 | defer: admin DTOs and upload/delete operation semantics require P4/P5; uncataloged member listing/raw preview routes were removed and unavailable states remain until opaque document routes land | P4/P5/P9-03 |
| scoped evidence retrieval | 1 | defer: the lifted two-field evidence projection is not the authoritative Evidence item/location contract | P6 |
| conversations and turn start | 6 | defer: summaries/details lack closed adoption and streaming remains the retired pilot protocol | P7/P9-02 |
| composer discovery | 1 | defer: authoritative component exists, but one-use token, ownership, expiry, and domain compatibility remain unproven | P11 |


This checkpoint proves reproducibility and catalog inclusion of the current registered HTTP surface, closed health responses, and the shared authoritative response-component vocabulary; it does not prove that the remaining handlers emit those components. Most routes still lack closed response-model adoption, while registered path parameters now use the exact authoritative names and browser capability modules still contain handwritten response and event substitutes. Current JSON request-body substitutes have been removed where generated components exist.

SSE is intentionally not snapshotted from the current code because doing so would canonize the explicitly retired pilot event protocol. P7-04/P9-02 must implement the versioned producer, persisted events, fixtures, parser, and canonical reducer before a generated SSE schema/snapshot gate can pass honestly.

P0-06 remains `IN_PROGRESS`, but its closure cannot require implementing later vertical behavior as a prerequisite for P1: the absent identity, document/evidence, resume, and cancel operations stay with P1/P4/P6/P7, and canonical SSE stays with P7-04/P9-02. P0-06 owns deterministic generation, catalog-delta enforcement, contract components available before their consuming slice, and removal of handwritten HTTP substitutes as each registered operation becomes authoritative. Final registered-route/response convergence is a cross-phase contract gate, not permission to scaffold future handlers in P0.
