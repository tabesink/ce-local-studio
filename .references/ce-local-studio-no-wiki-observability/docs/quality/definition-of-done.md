# Definition of Done

"Implemented" means the feature meets every applicable gate below against the production contract. A screen that renders, a mocked happy path, or passing unit tests alone is not done.

## Feature evidence record

Every pull request or coding-agent slice produces one record containing:

```text
feature/slice ID and interaction case IDs
requirements + API/SSE/schema versions
changed migrations/routes/services/workers/components
test IDs and commands with results
reference screenshots at required viewports
security/privacy/accessibility/concurrency decisions
operational-safety impact and runbook changes
known exclusions linked to an approved decision
artifact/source revision used for evidence
```

No applicable item may be marked "not applicable" without one sentence explaining the boundary.

## Universal completion gates

### Contract and traceability

- [ ] Behavior maps to PRD requirements and every applicable `M-*`, `A-*`, or `C-*` case.
- [ ] HTTP and SSE shapes are generated/validated against committed snapshots; examples deserialize with production schemas.
- [ ] Public DTOs contain only approved fields; unknown request fields fail closed.
- [ ] State transitions, status/error codes, idempotency fingerprint, ETag/version, and retry/cancel rules are explicit.
- [ ] Any contract change updates producer, typed client, fixtures, tests, compatibility range, and migration/release note in one slice.
- [ ] A required behavior with no approved contract is blocked, not guessed.

### Domain and persistence correctness

- [ ] Service owns authorization and transaction boundaries; route/UI checks are not correctness controls.
- [ ] Legal and illegal transitions have unit tests; database constraints back critical uniqueness/check/FK invariants.
- [ ] Protected mutation and audit event commit or roll back together.
- [ ] External calls occur outside DB transactions with timeout, stable idempotency key, safe mapping, and uncertain-outcome reconciliation.
- [ ] Leases, heartbeats, generation fences, stale completion, retry, cancellation, and worker death are tested where asynchronous.
- [ ] Deletes identify query fence, redaction, governed-ref invalidation, remote/object cleanup, retry, tombstone/final removal, and restore implications.
- [ ] Migration passes fresh install and upgrade from the oldest supported schema on PostgreSQL 16; rollback/restore behavior is recorded.

### Authorization, security, and privacy

- [ ] Public, member, owner, administrator, disabled, expired, revoked, and role-changed sessions are covered.
- [ ] Cross-owner and cross-domain IDs return non-disclosing results under real database queries.
- [ ] Unsafe ingress requests prove Host/Origin/CSRF checks; login proves session fixation defense and logout revocation.
- [ ] BFF strips identity/infrastructure headers and cannot accept a browser-selected upstream.
- [ ] Upload/content limits, MIME sniffing, filename sanitization, range handling, and object-key/path traversal are tested when applicable.
- [ ] Responses, logs, audit rows, traces, metrics, snapshots, and browser stores are scanned for credentials, cookies/tokens, prompts, questions/answers, raw source/hits, private IDs, paths/URLs, provider payloads, and stack traces.
- [ ] Dependency, image, secret, and static security scans have no unaccepted release-blocking finding.

### Frontend behavior and parity

- [ ] Route is a thin composition; feature uses typed clients and approved UI primitives/tokens.
- [ ] Loading, empty, ready, stale, conflict, forbidden/not-found, partial failure, offline/reconnecting, deleted/redacted, and retry states are implemented where reachable.
- [ ] Server truth wins after mutations; stale responses are rejected by selection/request generation.
- [ ] Draft preservation, Back/Forward, deep link, refresh, multi-tab, and logout/back-cache behavior match the interaction PRD.
- [ ] Reference screenshots pass the visual-regression viewport/density matrix at the approved threshold; intentional diffs are reviewed.
- [ ] No hard-coded product color/spacing where a token exists and no frontend access to provider, LightRAG, object storage, database, Docker, or runtime URLs.

### Accessibility

- [ ] Semantic name/role/state, label/error association, heading order, landmark structure, and status text are correct.
- [ ] Full workflow is keyboard operable with visible focus; modal/drawer focus trap and return target are tested.
- [ ] Streaming updates use bounded live-region announcements; token-by-token speech is suppressed.
- [ ] Evidence/viewer navigation focuses the target and returns to the originating card.
- [ ] Contrast, 200% zoom, reflow, reduced motion, forced-colors/high-contrast behavior, and automated accessibility checks pass.
- [ ] Critical member/admin flows receive manual screen-reader smoke evidence before production release.

### Reliability and operational safety

For Phase 1 these checks produce internal deployment evidence only. They do not authorize a Logs, Usage, Server, audit-review, diagnostics, export, or dashboard product surface.

- [ ] Every failure returns a safe stable code plus request ID; raw exceptions remain private.
- [ ] Logs are structured/allowlisted; metrics have bounded labels; request/operation/turn correlation works without content.
- [ ] Expected latency, timeout, retry, queue, stream, and upload budgets are tested and recorded in release evidence.
- [ ] Capacity exhaustion sheds load with `429`/`503` before unbounded memory, queue, connection, or provider use.
- [ ] Liveness/readiness behavior, graceful shutdown, stream drain, claim drain, and restart recovery are tested when runtime behavior changes.
- [ ] Operator action exists for every recoverable terminal/non-terminal operation state.

## Required test layers

| Change | Minimum evidence |
| --- | --- |
| Pure validation/reducer | deterministic unit tests including boundaries and malformed input |
| Repository/state | real PostgreSQL transaction tests, constraints, rollback, locking |
| HTTP/SSE | FastAPI contract tests plus OpenAPI/event snapshot parity |
| External adapter | pinned fixture contract tests for success, timeout, malformed output, auth failure, uncertain result |
| Frontend feature | component/state tests plus production TypeScript/lint/build/structure gates |
| User workflow | browser E2E through Next BFF and API, not direct service calls |
| Shared-state race | two sessions/tabs and real PostgreSQL concurrency; barriers, not sleeps |
| Deployment-sensitive | container/staging ingress test using built artifacts |

Each interaction case test name contains its ID, for example `test_M04_figure_evidence_opens_scoped_pdf`. Every `Race/failure` clause involving shared state has a deterministic concurrency test.

## Capability-specific gates

| Capability | Additional required proof |
| --- | --- |
| Authentication | generic login errors, throttling, rotation, absolute/idle expiry, CSRF refresh, revocation, role change |
| Domain/source operations | generation/lease races, deduplication, immutable embedding/parser inputs, cleanup recovery |
| Retrieval/evidence | one-domain isolation, provenance mapping, unmapped-hit discard, safe excerpt bound, deletion fence |
| Chat/SSE | live/resume/replay equivalence, arbitrary chunking, duplicates/gaps, disconnect, idempotency, redaction, unbuffered ingress |
| Documents | authorized metadata/location, PDF 200/206/416, semantic anchor fallback, cache revocation |
| Audit writes | event/metadata allowlists, protected-mutation rollback on audit failure, denial coverage, privacy scan |

## Root verification gate

One pinned command (or CI workflow with an immutable manifest) must run formatting/lint, Python/TypeScript type checks, dependency/cycle/structure checks, unit/service/contract tests, PostgreSQL migrations, OpenAPI/SSE snapshots, frontend production build, browser E2E, privacy scans, and deployable container smoke. Parallel jobs are acceptable; omitted jobs are not.

Flaky reruns do not convert failure to pass. Quarantined tests carry an owner, reason, expiry, and release-risk decision; a quarantined acceptance or security test blocks the relevant feature.

## Production release gate

In addition to feature gates:

- [ ] Immutable image digests, SBOM, provenance, lockfiles, source revision, migration head, and API/SSE versions are recorded.
- [ ] Staging uses the production network/ingress shape and proves incremental SSE, range PDF, login/CSRF/logout, and direct API denial.
- [ ] Load/capacity tests meet environment SLOs and connection/provider budgets.
- [ ] Worker kill, API drain, database/provider/parser/LightRAG/object-store failures, and recovery paths pass.
- [ ] PostgreSQL plus matching object versions and keys restore within RPO/RTO; citations, redactions, governed-ref invalidations, and audit continuity verify.
- [ ] Rollback compatibility, minimum health/log ownership, incident/deletion/restore runbooks, and named recovery ownership are approved.

## Automatic not-done conditions

A feature is not done if it uses private IDs or infrastructure details in the browser; relies on disabled buttons for concurrency; calls providers/LightRAG/storage from the frontend; persists raw prompts/context/tokens; answers a domain question without grounded Evidence; treats socket close as completion; audits after a protected transaction; serves protected bytes from a shared cache; uses SQLite as production proof; requires manual database edits; or leaves a race/failure clause untested.
