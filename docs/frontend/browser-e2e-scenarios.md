# Browser E2E Scenarios

Use Playwright against the production Next build, BFF, FastAPI, worker, PostgreSQL 16, and governed test object store. Release streaming tests also traverse the deployed ingress. No test may depend on fixed sleeps or another test's state.

## Harness rules

- Create isolated users/domains/conversations by fixture API; retain only safe refs in the browser.
- Use separate `BrowserContext` instances for users and pages within one context for tabs.
- Synchronize on responses, operation states, SSE event barriers, or database-backed test hooks, never animation time.
- Assert visible outcome, URL, focus, network request count, and authoritative API state where applicable.
- Capture trace, screenshot, console, and sanitized network log on failure.
- Test selectors use roles/names first and stable `data-testid` only for non-semantic stream barriers/regions.

## Member scenarios

| ID | Browser proof |
| --- | --- |
| E2E-M01 | login rotates session; invalid login is nondisclosing; logout blocks Back cache |
| E2E-M02 | select domain, stop it in admin context, submit preserves draft and clears stale selection |
| E2E-M03 | submit grounded turn; evidence precedes answer; disconnect/resume yields one durable answer |
| E2E-M04 | click figure evidence; Library/PDF opens page 18/region; focus and Back return correctly |
| E2E-M05 | text/table evidence opens semantic section and safe fallback without pixel anchor |
| E2E-M06 | select T1 then T2 under delayed T1 response; panel remains scoped to T2 |
| E2E-M07 | direct question creates no evidence; domain-seeking question preserves draft and requests domain |
| E2E-M08 | rename/delete own conversation; second user receives indistinguishable denial/not-found |
| E2E-M09 | ordered ref chips submit; expired/unauthorized chip is identified without target leakage |
| E2E-M10 | two tabs submit same request ID; one turn/provider invocation; changed fingerprint gets conflict |
| E2E-M11 | admin deletes cited source while answer/PDF open; answer redacts and viewer closes safely |
| E2E-M14 | open `/database-visualize` for authorized ready domain; snapshot fields are closed Graph DTOs only; no browser→LightRAG/runtime request |
| E2E-M15 | label-search selects relief-valve node; list/detail, canvas, and opaque `domain`/`node` URL state converge |
| E2E-M16 | unknown and unauthorized domain graph reads share one `404` shape; safe failure shows request ID |
| E2E-M17 | stopped/unready/deleting domain graph reads render contracted conflict/dependency UI, not empty success |
| E2E-M18 | during deletion rebuild, refresh shows retryable `graph_refreshing`; post-rebuild snapshot omits deleted nodes |
| E2E-M19 | exhausted graph-read permits shed with `429`/`Retry-After` or `503 capacity_unavailable` before runtime call |
| E2E-M20 | oversized/truncated snapshot surfaces `dependency_unavailable` or `truncated:true`; label search still works |
| E2E-M21 | keyboard/touch/narrow/zoom/forced-colors/reduced-motion graph path uses list/detail without canvas dependence |

## Administrator scenarios

| ID | Browser proof |
| --- | --- |
| E2E-A01 | replace credential; UI receives presence/version only; stale second admin conflicts |
| E2E-A02 | immutable embedding change is rejected; new profile remains available |
| E2E-A03 | create/start domain; operation status reconciles to running after worker success |
| E2E-A04 | stop during query fences new retrieval and shows documented terminal policy |
| E2E-A05 | two admins stop/delete; one legal generation wins and both UIs reconcile |
| E2E-A06 | concurrent identical uploads yield one canonical source/preparation workflow |
| E2E-A07 | retry races late completion; only winning generation publishes blocks |
| E2E-A08 | indexing becomes query-eligible only after readiness; timeout remains retryable |
| E2E-A09 | source delete fences retrieval, redacts answer, invalidates governed refs, exposes cleanup state |
| E2E-A10 | domain delete removes selection, rejects concurrent work, and leaves recoverable operation on failure |
| E2E-A11 | change defaults during operation; operation displays frozen version and next work uses new version |

## Concurrent shared-state scenarios

| ID | Setup and proof |
| --- | --- |
| E2E-C01 | N member contexts query one domain; each transcript/evidence/request ID stays isolated; overload sheds safely |
| E2E-C02 | member list overlaps admin mutation; stale item transitions to safe unavailable, not crash |
| E2E-C03 | two members open same document at different anchors; each viewer remains independent |
| E2E-C04 | users attempt each other's conversation operations/streams; bodies/timing do not disclose existence |
| E2E-C05 | revoke admin role during session; next mutation is denied, navigation refreshes, committed operation remains |

## Fault injection

The harness must be able to pause/reorder safe API responses, sever SSE after a chosen sequence, return one `502/429/410`, pause a worker before commit, expire a lease, fail object cleanup, and count provider/retrieval invocations. Faults are keyed to test-owned request/operation IDs and cannot affect parallel tests.

## Assertions common to every case

- no browser request targets PostgreSQL, object storage, LightRAG, Docker, parser, model provider, a direct `/graphs` path, or a configurable backend URL;
- no console error, hydration mismatch, raw stack/upstream message, path, secret, private identifier, or raw graph property bag;
- unauthorized personalized responses are not served from cache;
- keyboard path and focus outcome match the accessibility contract;
- retry/refresh does not duplicate durable work.

## Suite layers and gate

Run fast browser cases with deterministic real services on each PR; tag expensive provider/parser/load paths `release`. Every interaction PRD case must have one E2E ID plus service/repository/contract coverage for invariants the browser cannot prove. A green mocked UI suite cannot waive real PostgreSQL races or deployed-ingress SSE proof.
