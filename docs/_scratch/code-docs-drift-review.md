# Context Engine Legacy Code vs Reviewed Docs

## Code Review Results

**Review date:** 2026-07-22  
**Scope:** full inherited-tree audit of `app/client`, `app/server`, the Context Engine integration surface around `app/vendor/lightrag`, application Docker/Compose/environment examples, and `scripts/dev.sh` against root `AGENTS.md` and the normative `docs/` package. Generated/dependency output (`node_modules`, `.next`, `test-results`, `__pycache__`, bytecode, and build caches) was excluded. Vendored LightRAG internals were treated as a read-only dependency; its Context Engine adapter, lifecycle, provenance, timeout, and delivery boundaries were reviewed.  
**Intent:** establish how far the lifted previous build deviates from the reviewed rebuild contract before any implementation changes.  
**Mode:** markdown report-only. No application, infrastructure, test, vendor, or script code was changed. This report is the only repository file written.  
**History limitation:** the workspace is not a Git repository, so there is no merge base, branch, revision, or reliable introduced-versus-inherited classification. Findings describe current-tree behavior, not authorship or recency.  
**Authority:** `docs/master-build-plan.md` explicitly keeps P0-P13 `NOT_STARTED` and says reviewed source is evidence, not rebuild completion evidence.

**Reviewers:** correctness, project-standards, testing, maintainability, security, api-contract, reliability, and adversarial.

- Security was selected for cookie authentication and the public Next-to-private FastAPI boundary.
- API-contract was selected because HTTP, DTO, document/evidence, and SSE catalogs are normative.
- Reliability was selected for workers, leases, external calls, deletion, Docker, and release scripts.
- Testing was selected for the required PostgreSQL, contract, browser, privacy, and deployed-ingress evidence.
- Maintainability was selected because the lifted layout differs from the target modular monolith.
- A performance persona was not run because this was not a scoped performance change; security/reliability still reviewed unbounded upload and worker-starvation behavior.
- An external cross-provider adversarial packet was ineligible without a Git revision/diff. An in-process adversarial pass and a separate independent validator were used.

**Overall result:** the lifted code is useful implementation evidence, but it is not aligned enough to serve as the rebuild foundation without staged contract, security, persistence, lifecycle, frontend, and verification work. The supplied launch paths do not currently build the checked-in tree.

### Triage Groups

| Group | Findings | Context | Preferred resolution | Why |
| --- | --- | --- | --- | --- |
| Repository and verification spine (apply queue) | #6, #7, #8, #9 | Release paths are stale and tests validate parts of the superseded pilot | Establish the canonical package/migration layout (#8), one root gate (#9), then replace obsolete/visual-only tests (#6, #7) | Every later fix needs a runnable contract-aware loop |
| Browser trust and identity (apply queue) | #5, #10, #16, #17, #19, #21 | The Next boundary and cookie session lifecycle do not implement the reviewed trust model | Build the narrow BFF and CSRF/Origin/Host policy (#5, #16), then session/auth DTO/cache/bootstrap behavior | These precede every authenticated feature |
| Public contract and safe projection (apply queue) | #1, #11, #12, #14, #18, #20 | Handwritten clients and legacy routes encode non-contract fields and identifiers | Generate the contract spine (#1), migrate opaque refs/closed DTOs (#14, #20), then enforce response/precondition semantics | One generated boundary prevents repeated drift |
| Durable chat and governed context (apply queue) | #3, #23, #24, #25, #26 | Pilot stream/state behavior cannot provide replay, idempotent attach, or one-use context | Implement durable event persistence/reducer (#24, #25), then attach/retry and consumption (#23, #26), then UI state (#3) | Live, resume, and replay need one truth |
| Real retrieval and integration (decision gate) | #22, #27, #28 | Parser/model/retrieval paths include stand-ins and unbounded native calls | Make the approved adapter decisions required by the stop conditions, then add timeouts, readiness, provenance, and fair polling | Scaffold semantics must not become production behavior |
| Ingestion, operations, and recovery (apply queue) | #13, #15, #29, #30, #31, #32, #33 | Upload, readiness, leases, external outcomes, deletion, shutdown, and wiki writes lack required boundaries | Introduce migrations plus operation/outbox and conditional-write primitives, then implement each lifecycle on them | Shared durability primitives resolve multiple races |
| Frontend workstation contract (apply queue) | #2, #4 | Routes, unavailable behavior, and inspector accessibility are incomplete | Implement generated-contract route slices and shared RightInspector/Drawer primitives after the API spine | Avoid another legacy-route or inaccessible UI pass |

### P1 -- High

| # | File | Issue | Reviewer | Confidence |
| --- | --- | --- | --- | --- |
| 1 | `app/client/src/features/chat-shell/api.ts:36` | Handwritten DTOs duplicate contract ownership | maintainability | 100 |
| 2 | `app/client/src/features/chat-shell/EvidencePanel.tsx:86` | Inspector controls are not keyboard or screen-reader complete | project-standards | 100 |
| 3 | `app/client/src/features/chat-shell/use-chat-shell.ts:76` | Chat loses drafts and lacks canonical state/inspector behavior | maintainability, project-standards | 100 |
| 4 | `app/client/src/features/navigation-sidebar/constants.ts:15` | Required frontend routes and unavailable states are incomplete | adversarial, project-standards | 100 |
| 5 | `app/client/src/middleware.ts:5` | Generic rewrite bypasses the required BFF trust boundary | security, project-standards, adversarial | 100 |
| 6 | `app/client/tests/chat.test.mjs:50` | Tests enforce obsolete API and SSE contracts | testing | 100 |
| 7 | `app/client/tests/e2e/visual-matrix.spec.ts:65` | Visual matrix never compares baselines | testing | 100 |
| 8 | `app/Dockerfile:11` | Release manifests/package layout cannot build the tree | correctness, project-standards, testing, reliability, adversarial | 100 |
| 9 | `app/pyproject.toml:32` | No backend or root verification gate exists | testing | 100 |
| 10 | `app/server/api/dependencies.py:48` | Auth lacks rotation, idle expiry, and abuse controls | security | 100 |
| 11 | `app/server/api/errors.py:12` | Error envelope fields have the wrong shape | api-contract | 100 |
| 12 | `app/server/api/routes.py:1040` | Domain lifecycle operations return wrong responses | api-contract | 100 |
| 13 | `app/server/api/routes.py:1138` | Uploads buffer before limits and trust declared type | correctness, security, project-standards, adversarial | 100 |
| 14 | `app/server/api/routes.py:1317` | Member documents expose private IDs and original bytes | correctness, security, project-standards, api-contract, adversarial | 100 |
| 15 | `app/server/api/routes.py:285` | Readiness ignores schema, bootstrap, and storage | reliability | 100 |
| 16 | `app/server/api/routes.py:291` | Unsafe requests lack CSRF and allowed-Origin enforcement | correctness, security, project-standards | 100 |
| 17 | `app/server/api/routes.py:312` | Auth endpoints/identity DTO violate the contract | api-contract | 100 |
| 18 | `app/server/api/routes.py:493` | Pagination, preconditions, and idempotency metadata are absent | project-standards, api-contract | 100 |
| 19 | `app/server/app.py:84` | Personalized responses lack no-store/security headers | security, project-standards | 100 |
| 20 | `app/server/services/audit.py:141` | Audit DTO leaks private trace/database IDs | security | 100 |
| 21 | `app/server/services/auth.py:44` | Startup rewrites and re-enables the bootstrap admin | security, reliability, adversarial | 100 |
| 22 | `app/server/services/chat_turns.py:138` | Chat/parsing paths still use deterministic stand-ins | correctness, adversarial | 100 |
| 23 | `app/server/services/chat_turns.py:336` | Identical running retries are rejected | correctness | 100 |
| 24 | `app/server/services/chat_turns.py:565` | Chat uses the retired, buffered SSE protocol | correctness, project-standards, api-contract | 100 |
| 25 | `app/server/services/chat_turns.py:899` | Turn execution is socket-coupled; no resume/cancel | correctness, api-contract, adversarial | 100 |
| 26 | `app/server/services/composer_refs.py:424` | Composer tokens are not one-use | security, project-standards | 100 |
| 27 | `app/server/services/indexing.py:333` | Hung LightRAG can block every domain in-process | reliability | 100 |
| 28 | `app/server/services/indexing.py:886` | Accepted index polling spins and starves deletion | reliability | 100 |
| 29 | `app/server/services/sources.py:630` | Deletion strands partial work without durable recovery | api-contract, reliability, adversarial | 100 |
| 30 | `app/server/services/sources.py:969` | Expired preparation workers can still publish | correctness, reliability | 100 |
| 31 | `app/server/worker.py:64` | Worker cannot drain or stop claiming gracefully | reliability | 100 |
| 32 | `app/server/services/domains.py:478` | Unknown external outcomes are not reconciled | reliability | 75 |
| 33 | `app/server/services/wiki.py:390` | Submitted wiki drafts are vulnerable to stale edits | correctness | 75 |

#### Evidence and required response

- **#1** - `api.ts:36-89` handwrites DTOs and the legacy stream union. The DTO catalog and stream-runtime spec require generated HTTP types plus separately versioned SSE schemas. Generate those before migrating feature adapters.
- **#2** - `EvidencePanel.tsx:86-103` is pointer-only and puts the mobile panel inside an `aria-hidden` backdrop without dialog/focus behavior. Adopt the shared inspector/drawer contract and test keyboard, focus, reflow, and zoom.
- **#3** - `use-chat-shell.ts:76-102` duplicates fetched/live state; `:244-260` clears draft/refs before a recoverable failure. Implement normalized resources, one stream reducer, generation guards, canonical URL keys, full Evidence/Refs/Source/Wiki inspection, and draft preservation.
- **#4** - the route tree omits `/wiki` and shell `not-found.tsx`; `GraphPage.tsx:17-31` fetches domains and scaffolds a selector while unavailable. Implement the exact wiki/not-found states and remove every unavailable-graph request/control.
- **#5** - `middleware.ts:5-7` rewrites the browser request wholesale. The security boundary requires narrow BFF handlers, header allowlists/stripping, trusted public host/protocol, streaming/ranges, and abort propagation. Replace the rewrite.
- **#6** - `chat.test.mjs:50` asserts pilot events and `:112` requires unapproved `/evidence-refs/{id}/source`. Replace regex assertions with schema-validated HTTP/SSE fixtures for the approved location route, chunking, gaps, replay, cancel, and redaction.
- **#7** - `visual-matrix.spec.ts:65-66` writes a screenshot and only checks existence. Use approved committed baselines and the documented Playwright pixel threshold.
- **#8** - Docker copies absent `README.md`, `context_engine`, and `migrations`; Compose builds absent `./frontend`; `scripts/dev.sh:188-220` expects the same stale root layout. Choose one layout and align Docker/Compose/Alembic/package/scripts, then prove clean build and fresh/upgrade migrations.
- **#9** - pytest points at absent `app/tests`; no migrations, contract snapshots, root command, or CI exists. Add one gate covering backend, frontend, PostgreSQL, contracts, E2E, privacy, build, and container smoke.
- **#10** - session validation checks only absolute expiry and updates `last_used_at` every request; login does not rotate a presented session and no throttling exists. Implement idle/absolute expiry, bounded updates, rotation/revocation, and ingress-verified throttling.
- **#11** - errors use an optional list of path/message entries. The closed catalog requires a `Record<string,string>` fields object. Normalize all errors and freeze schema tests.
- **#12** - start/stop return `200 {domain}`; the contract requires `202 {operation}`. Return observable operations and reconcile UI from authoritative refresh.
- **#13** - upload calls `await request.body()` before its limit and trusts multipart type. Stream with byte/time limits, abort, hash, sniffing, bomb checks, governed temporary storage, and zero partial commit.
- **#14** - member listing reuses admin SourceDocument fields and raw IDs; preview returns original PDF/text/Markdown without ranges. Migrate opaque public refs and implement only governed document/content/location DTOs with PDF `200/206/416`, ETag/If-Range, anchors, and reauthorization.
- **#15** - readiness runs only `SELECT 1`. Verify configuration, schema head, bootstrap state, and indispensable governed storage; return safe `503` until ready.
- **#16** - no CSRF bootstrap/token/header, unsafe Origin check, or shared enforcement exists. Implement signed pre-auth and session-bound double-submit tokens on every unsafe method, including stream and upload.
- **#17** - login/me return undocumented session JSON, identity uses `username/isDisabled`, logout returns JSON instead of `204`, and CSRF bootstrap is absent. Project exact closed auth DTOs/statuses.
- **#18** - catalogued routes accept no cursors, `If-Match`, ETags, or `Idempotency-Key`. Implement them through the committing transaction, including `428`, `stale_revision`, and `idempotency_conflict` with PostgreSQL races.
- **#19** - middleware adds only `X-Request-ID`; authenticated JSON/SSE/errors/bytes lack mandatory cache/security policy. Centralize response classification and verify logout/back-cache/two-user isolation.
- **#20** - audit projection returns `actorUserId`, `targetId`, and `traceId`. Replace with the closed safe actor/target projection and keep private correlation internal.
- **#21** - every API lifespan calls `seed_admin`; existing users have password, role, disablement, and timestamps overwritten without protected audit. Make bootstrap insert-only in an explicit release step.
- **#22** - default synthesis returns fixed sentences and parser adapters decode binaries as UTF-8. The as-built gaps doc already labels these scaffolds. Fail closed until approved typed adapters are injected and native LightRAG provenance/readiness/delete semantics are proven.
- **#23** - identical running input returns `conversation_turn_in_progress`; lookup/insert are separate with no unique-conflict recovery. Claim idempotency transactionally, compare the effective fingerprint, and attach/replay identical work.
- **#24** - both ends use superseded pilot events and the client waits for `response.text()`. Implement persisted versioned envelopes, incremental parsing, received/applied cursors, compatibility checks, and one live/resume/replay reducer.
- **#25** - both stream generators cancel in `finally` on disconnect; resume and explicit cancel routes are absent. Decouple execution from sockets, persist events/terminal state, keep work alive on disconnect, and cancel only via the contracted endpoint.
- **#26** - token validation checks ownership/expiry, but the model has no consumed state. Atomically consume/bind refs with turn creation, reject reuse, roll back mixed sets, and replay without raw tokens.
- **#27** - native LightRAG uses `run_until_complete` under one process-global lock without a deadline. Add bounded typed timeouts/cancellation and per-domain isolation.
- **#28** - accepted-not-ready work is immediately reclaimable, advances no poll time, and reports work, so the short-circuit worker starves delete. Persist bounded backoff and schedule queue classes fairly.
- **#29** - deletion spans nested commits, remote/filesystem cleanup, row removal, and final audit without a durable operation; source DELETE returns `204` and failed domain deletion has no reclaim path. Atomically commit fence/operation/redaction/invalidation/audit intent, then use leased idempotent cleanup and reconciliation.
- **#30** - preparation has a finite lease/no heartbeat; publish checks status/generation but not owner/expiry. Heartbeat below one third of lease and fence publish on owner, lease, generation, and state.
- **#31** - production invokes the worker loop with its always-true default and no signal handler. Stop claims on SIGTERM/SIGINT, drain/checkpoint bounded work, and leave uncertainty reclaimable.
- **#32** - start/stop persist running before external calls and can strand the operation; index unknown outcomes become new-generation retries. Add stable keys, leased outbox work, unknown state, reconciliation, and fenced finalization.
- **#33** - wiki update and submit read/commit independently without lock/version/`If-Match`; a stale edit can commit after submit. Add strong ETags and conditional update/submit/review transitions returning `stale_revision`.

### Requirements Completeness

`docs/master-build-plan.md` was discovered as an inferred normative plan. Its statuses remain authoritative; physical legacy code does not advance them.

| Plan area | Review result | Evidence boundary |
| --- | --- | --- |
| P0 Contract/repository spine | Not completion evidence | No buildable layout, generated contract/client, snapshots, CI, or root gate (#1, #8, #9) |
| P1-P2 Identity/configuration | Partial scaffold | Useful crypto/auth pieces exist, but trust/session/DTO/audit/startup contracts fail (#5, #10, #16-#21) |
| P3-P6 Domain/source/LightRAG/Evidence | Partial scaffold | Some generation/provenance exists; ingestion, operations, public refs, adapters, recovery, and document delivery fail (#12-#15, #22, #27-#32) |
| P7-P8 Chat/accountability | Not aligned | Pilot SSE, socket cancellation, missing replay/cancel, idempotency, and audit drift (#20, #23-#26) |
| P9-P12 Frontend/wiki/context | Partial, incomplete | Wiki/not-found, state, inspector, accessibility, generated client, and one-use refs are incomplete (#1-#4, #26) |
| P13 Release/recovery | Not addressed | Images fail and migration, ingress, load, backup/restore, shutdown, and artifact evidence is absent (#8, #9, #15, #27-#32) |

### Reusable Foundations

These are starting points, not Definition-of-Done evidence:

- Argon2 password hashing, opaque session-token hashing, and encrypted provider credentials.
- Current-user/admin dependencies and several owner-scoped conversation/evidence queries.
- Request IDs, centralized error translation, and structured allowlisted logging, although shapes/privacy need work.
- Several generation, lease, request-identity, and provenance concepts; retrieval filters unmapped/cross-domain hits.
- Hashed composer tokens and persisted accepted-ref safe labels/private links, without one-use consumption.
- Pinned frontend versions/lockfiles, theme primitives, a workstation shell, and narrow preference storage.
- The graph route avoids graph/LightRAG calls, but still makes the prohibited domain request and scaffolds a selector.

### Actionable Findings

Every retained item is current-tree work. `manual` means a coordinated vertical slice, not permission to invent unapproved contracts or infrastructure.

| # | File | Route | Required next action |
| --- | --- | --- | --- |
| 1 | `app/client/src/features/chat-shell/api.ts:36` | `manual -> downstream-resolver` | Generate HTTP client/versioned SSE runtime; migrate features |
| 2 | `app/client/src/features/chat-shell/EvidencePanel.tsx:86` | `gated_auto -> downstream-resolver` | Adopt accessible inspector/drawer; test keyboard/focus/reflow |
| 3 | `app/client/src/features/chat-shell/use-chat-shell.ts:76` | `manual -> downstream-resolver` | Implement canonical stores/reducer/generations/URLs/inspector |
| 4 | `app/client/src/features/navigation-sidebar/constants.ts:15` | `manual -> downstream-resolver` | Add wiki/not-found; remove graph requests/scaffolding |
| 5 | `app/client/src/middleware.ts:5` | `manual -> downstream-resolver` | Build narrow allowlisted streaming/range BFF |
| 6 | `app/client/tests/chat.test.mjs:50` | `gated_auto -> downstream-resolver` | Replace with approved schema/reducer fixtures |
| 7 | `app/client/tests/e2e/visual-matrix.spec.ts:65` | `gated_auto -> downstream-resolver` | Add approved baselines/threshold assertions |
| 8 | `app/Dockerfile:11` | `manual -> downstream-resolver` | Establish one package/migration layout and align launchers |
| 9 | `app/pyproject.toml:32` | `manual -> downstream-resolver` | Add backend/migration/contracts/E2E/privacy/container root gate |
| 10 | `app/server/api/dependencies.py:48` | `manual -> downstream-resolver` | Add idle/absolute expiry, rotation, bounded updates, throttling |
| 11 | `app/server/api/errors.py:12` | `gated_auto -> downstream-resolver` | Emit closed fields record; freeze schemas |
| 12 | `app/server/api/routes.py:1040` | `manual -> downstream-resolver` | Return `202 {operation}`; reconcile server truth |
| 13 | `app/server/api/routes.py:1138` | `manual -> downstream-resolver` | Stream, limit, sniff, hash, and commit no partial source |
| 14 | `app/server/api/routes.py:1317` | `manual -> downstream-resolver` | Migrate opaque refs/governed PDF/location contracts |
| 15 | `app/server/api/routes.py:285` | `manual -> downstream-resolver` | Check schema/bootstrap/storage; safe `503` |
| 16 | `app/server/api/routes.py:291` | `manual -> downstream-resolver` | Implement CSRF bootstrap/rotation/all unsafe checks |
| 17 | `app/server/api/routes.py:312` | `manual -> downstream-resolver` | Implement exact auth endpoints/generated consumers |
| 18 | `app/server/api/routes.py:493` | `manual -> downstream-resolver` | Add cursors/ETags/idempotency and transactional races |
| 19 | `app/server/app.py:84` | `gated_auto -> downstream-resolver` | Centralize private cache/security response policy |
| 20 | `app/server/services/audit.py:141` | `manual -> downstream-resolver` | Project safe actor/target refs |
| 21 | `app/server/services/auth.py:44` | `manual -> downstream-resolver` | Move insert-only bootstrap to release step |
| 22 | `app/server/services/chat_turns.py:138` | `manual -> downstream-resolver` | Approve real adapter semantics; implement typed ports/fail closed |
| 23 | `app/server/services/chat_turns.py:336` | `manual -> downstream-resolver` | Transactionally claim and attach/replay identical work |
| 24 | `app/server/services/chat_turns.py:565` | `manual -> downstream-resolver` | Implement persisted envelope/parser/cursors/reducer |
| 25 | `app/server/services/chat_turns.py:899` | `manual -> downstream-resolver` | Decouple execution; add resume/replay/explicit cancel |
| 26 | `app/server/services/composer_refs.py:424` | `manual -> downstream-resolver` | Atomically consume/bind refs |
| 27 | `app/server/services/indexing.py:333` | `manual -> downstream-resolver` | Add deadlines/cancellation/per-domain isolation |
| 28 | `app/server/services/indexing.py:886` | `manual -> downstream-resolver` | Persist backoff; schedule queues fairly |
| 29 | `app/server/services/sources.py:630` | `manual -> downstream-resolver` | Fence/commit operation/redaction/audit; leased cleanup |
| 30 | `app/server/services/sources.py:969` | `manual -> downstream-resolver` | Heartbeat and fence publish on owner/lease/generation |
| 31 | `app/server/worker.py:64` | `manual -> downstream-resolver` | Stop claims on signals; drain/checkpoint |
| 32 | `app/server/services/domains.py:478` | `manual -> downstream-resolver` | Add stable keys/unknown state/reconciliation/finalization |
| 33 | `app/server/services/wiki.py:390` | `manual -> downstream-resolver` | Add ETag/version conditional transitions |

### Coverage

#### Checks executed

| Check | Result | Meaning |
| --- | --- | --- |
| `cd app/client && npm test` | Failed: 47 passed, 8 failed of 55 | Failures expect missing legacy design/docs files; passing tests still assert pilot behavior |
| `cd app/client && npm run typecheck` | Failed | `SettingsPanel.tsx:500` passes `className` absent from Button contract |
| backend import smoke with `app` on `sys.path` | Failed | `ModuleNotFoundError: context_engine`; authored backend is `app/server` |
| Docker/Compose/E2E startup | Not run | Static build inputs are absent; the stack cannot construct unchanged |
| Git provenance/status | Unavailable | Root is not a Git repository |

#### Review mechanics and validation

- Eight reviewer artifacts produced 66 raw findings; semantic reconciliation reduced them to 35 unique items.
- Two maintainability P2 observations moved to residual risks and one testing P2 moved to testing gaps, leaving 33 primary P1 findings.
- Final mechanics: 0 malformed returns, 0 malformed findings, 0 confidence suppressions, no pre-existing partition.
- No cross-model shortcut was used. A separate validator re-read every retained P1 in one batch: 33 validated, 0 rejected, 0 malformed.
- External adversarial cross-checking was ineligible without a Git revision/diff; the fallback was in-process and is not claimed as independent external corroboration.
- No session-settled decision conflicted with a finding; no settlement suppression occurred.

#### Residual risks

- `src/components` and `src/_shared/ui` compete instead of the single documented `src/ui` layer; no import-boundary gate exists.
- `routes.py` is 1,387 lines, `models.py` 1,070, `sources.py` 1,099, and `_shared/ui/index.tsx` 1,942; capability boundaries remain concentrated.
- Upload may orphan a finalized local object on some database commit failures; prove with storage/transaction fault tests.
- Domain/index leases need the same owner/expiry/heartbeat audit as preparation; #30 is the directly proven representative.
- API stream drain behavior depends on absent ASGI/ingress termination configuration.
- Vendor LightRAG logging may emit content/provider detail on unexercised paths; capture integrated privacy fixtures.
- CSP, `nosniff`, referrer, and permissions policy is incomplete; no executable XSS sink was proven, so this remains coupled to #19.

#### Testing gaps

- No real PostgreSQL tests prove authorization, constraints, audit rollback, ETags, idempotency, leases/generations, deletion, wiki atomicity, or M/A/C races.
- No OpenAPI/JSON Schema snapshot, generated-client gate, versioned SSE schemas, or transcript fixtures.
- No deployed-ingress Host/Origin/CSRF, forged-header, direct-API, cache, streaming, PDF-range, or logout/back-cache tests.
- No deterministic real parser/provider/native-LightRAG fixtures for timeout, uncertainty, readiness, provenance, idempotency, or deletion.
- Browser coverage omits two-user, multi-tab, role revocation, redaction, resume/replay, wiki, accessibility, 320px, zoom, reduced motion, and theme/density cases.
- `stack-seed.ts` uses fixed sleeps instead of response, operation, SSE, or database barriers.
- No privacy scan covers responses, browser storage, logs, audit, diagnostics, traces, snapshots, fixtures, and failure artifacts.
- No clean install/upgrade migration, artifact manifest, SBOM, backup/restore, graceful shutdown, capacity/load-shed, or rollback evidence.

---

### Verdict

> **Not ready.** The legacy tree is neither runnable through its supplied launch artifacts nor compatible with the reviewed security, HTTP/DTO, SSE, document/evidence, lifecycle, frontend, and completion-evidence contracts.
>
> **Most important next action:** establish P0 of `docs/master-build-plan.md` as a real repository/contract spine. Do not start with individual screens or path-only patches; choose the canonical package/migration layout, make clean build/migration/root verification possible, and generate the approved contract boundary.
>
> **Fix order:** repository/migration/test spine (#8, #9) -> generated contracts/opaque refs (#1, #11, #12, #14, #17, #18, #20) -> BFF/auth/cache boundary (#5, #10, #16, #19, #21) -> durable operation/recovery primitives (#13, #15, #29-#33) -> approved real adapters (#22, #27, #28) -> durable SSE/idempotency/governed refs (#23-#26) -> accessible frontend route/state slices (#2-#4, #6, #7) -> P13 release evidence.

Prioritized actionable recap:

1. **P1 - `app/Dockerfile:11`, `app/pyproject.toml:32` - manual:** canonical layout, migrations, clean builds, and root gate (#8, #9).
2. **P1 - `app/client/src/features/chat-shell/api.ts:36`, `app/server/api/routes.py:493` - manual:** generated HTTP/SSE, opaque projections, response shapes, cursors, ETags, idempotency (#1, #11, #12, #14, #17, #18, #20).
3. **P1 - `app/client/src/middleware.ts:5`, `app/server/api/routes.py:291` - manual:** narrow BFF plus CSRF/Origin/Host/session/cache boundary (#5, #10, #16, #19, #21).
4. **P1 - `app/server/services/sources.py:630`, `app/server/services/domains.py:478` - manual:** operation/outbox, leases, reconciliation, deletion, shutdown, conditional writes (#13, #15, #29-#33).
5. **P1 - `app/server/services/chat_turns.py:138`, `app/server/services/indexing.py:333` - decision gate/manual:** approve and implement real parser/provider/native-LightRAG semantics (#22, #27, #28).
6. **P1 - `app/server/services/chat_turns.py:565` - manual:** durable versioned SSE, attach/replay/cancel, one-use composer refs (#23-#26).
7. **P1 - `app/client/src/features/navigation-sidebar/constants.ts:15` - manual:** wiki/not-found/graph states, chat stores/URLs/inspector, accessibility, contract-aware tests (#2-#4, #6, #7).
