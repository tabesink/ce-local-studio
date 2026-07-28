---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
phase_compatibility: phase-1-active
title: P9-07 Contracted Browser Workflows - Plan
type: feat
date: 2026-07-28
deepened: 2026-07-28
---

# P9-07 Contracted Browser Workflows - Plan

## Goal Capsule

- **Objective:** Close P9-07 by wiring contracted member/admin browser workflows: conversation rename/delete (M-08), ordered source/template composer-ref discovery/attach (M-09 with P11-04 Evidence attach still deferred), administrator Model Provider Settings for credentials/profile visibility/global synthesis defaults (A-01/A-02/A-13), and safe domain/source operation-history UX (A-03/A-07/A-09/A-10).
- **Authority:** docs/prd.md FR-02 and closed Phase 1 chat capability manifest; interaction M-08/M-09/A-01/A-02/A-03/A-07/A-09/A-10/A-13; HTTP/DTO runtime-setting contracts; docs/frontend/* chat/settings/documents contracts and FE-10; P9-02/P9-04/P9-06/P11-02 dependencies; docs/master-build-plan.md P9-07.
- **Execution profile:** Feature-layer UI against generated clients; Vitest/component altitude; Playwright residual P12-07.
- **Readiness checkpoint:** Implementation-ready after 2026-07-28 deepen pass against live chat/settings adapters.
- **Stop conditions:** Stop if the provider UI needs a field, model-discovery endpoint, runtime URL/target, credential shape, or provider capability absent from the approved contracts; do not expose member model selection, claim Bedrock/Ollama production support before P10-05, invent user-admin mutation UI, add wiki/observability screens, or claim production Playwright DONE.
- **Tail ownership:** P12-07 production-boundary E2E/visual matrix.

---

## Product Contract

### Summary

Unlock contracted browser controls that backend/contracts already support but UI leaves disabled, incomplete, or incorrectly adapted. This includes a compact administrator Model Provider section composed from existing Settings primitives and guided by `docs/_scratch/provider-settings-imagined.html`.

Product Contract preservation: unchanged (deepen pass strengthened Planning Contract only).

### Problem Frame

Rename/delete adapters exist without product controls and currently omit required `If-Match`; source/template composer-ref picker remains hard-disabled despite P11-02; Settings uses lifted provider fields (`providerKind`/`isConfigured`) and omits required conditional/idempotent request headers; operation-history GETs exist in OpenAPI while Settings/Documents show only coarse current-operation actions. The current provider concept is intentionally quieter than a dashboard, but it is not yet an approved parity target. Browser model-profile create/edit forms remain blocked because the private `MODEL_CATALOG` has no approved public projection.

### Actors

| Actor | Role |
| --- | --- |
| Member | Renames/deletes conversations; attaches composer refs |
| Administrator | Replaces write-only credentials, reviews approved model profiles, sets the deployment-wide synthesis default, sees immutable embedding facts, and inspects operation history or uses separately contracted current-operation actions |
| Coding agent | Implements UI + component tests + evidence |

### Key Flows

**F1 — Conversation rename/delete.** Owner renames/deletes → server confirms → list/open views update; cross-owner indistinguishable not-found.

**F2 — Composer refs.** Discover ordered source/template refs → attach chips → submit consumes tokens; invalid chips identified safely. Evidence attach chips remain deferred under P11-04.

**F3 — Model Provider Settings.** Admin opens `/settings?section=provider` → sees safe provider status, approved model profiles, and the active deployment-wide synthesis profile → replaces credentials or changes a contracted setting with If-Match → success reconciles from server truth; 428/409 retains intent and refreshes.

**F4 — Operation history.** Admin opens domain/source history → sees safe state and request IDs → separately contracted current-operation retry/cancel controls remain available where their endpoints allow them → refresh reconciles server truth. Historical rows do not invent retry/cancel actions.

**F5 — Domain embedding lock.** Admin reviews embedding profiles in Model Provider Settings and chooses one in the Knowledge Domain creation/deploy form → the created domain displays the selected profile as locked during subsequent deployment and operation → no in-place replacement control is offered.

### Requirements

- R1. Inventory `docs/_scratch/p9-07-contracted-browser-workflows-inventory.md`.
- R2. Conversation rename/delete UI with server-truth and conflict handling (M-08).
- R3. Enable ordered source/template composer-ref discovery/attach using P11-02 APIs (M-09); no raw tokens in storage; retain Evidence attach chips as deferred under P11-04.
- R4. Implement the approved mutation-header matrix: credential PUT, model-profile PATCH, and runtime-settings PATCH use If-Match/ETag; model-profile POST uses a stable Idempotency-Key; model-profile DELETE sends only its contracted headers. Handle missing/stale preconditions, idempotent replay, and authoritative refresh without weakening CSRF.
- R5. Render domain/source operation history with safe failure/request IDs. Bind retry/cancel only to separately contracted current-operation endpoints and advisory allowedActions; historical cleanup rows remain read-only when no mutation endpoint exists.
- R7. Evidence `docs/_scratch/p9-07-contracted-browser-workflows-evidence.md`; mark P9-07 DONE; P9 phase DONE if no other open P9 tasks. (R6 was never assigned; R-IDs remain stable.)
- R8. Amend the provider Settings component/state/accessibility/parity contracts and add a `provider-settings` parity target. Use `docs/_scratch/provider-settings-imagined.html` as non-normative visual guidance, promote the approved result to `app/client/tests/parity/fixtures/provider-settings.html`, and compose only existing `settings-nav`, `settings-group`, `settings-row`, `button`, `select`, `status-pill`, `input`, and `ui-modal` targets. Reuse `operation-status`, `source-operation-panel`, and `confirm-action-dialog` where those surfaces apply.
- R9. Replace lifted Settings API types with generated `ProviderSummaryDto`, `ModelProfileDto`, and `RuntimeSettingsDto`; retain ETag/version metadata outside unsafe browser storage. The default provider view shows OpenAI/Bedrock write-only credential actions, Ollama local/no-credential status, one deployment-wide active synthesis selector, and a compact read-only embedding-profile list. Do not add browser model-profile create/edit/delete until an approved public catalog projection and interaction contract exist.
- R10. Keep scope explicit in the UI: synthesis defaults apply to all users' new turns; embedding profiles are selected in the per-domain creation/deploy form and rendered locked afterward; members never receive a provider/model picker. The browser may project only contracted `configured` and profile facts; it must not infer or claim provider runtime readiness from those fields. P10-05 owns production-support proof.

### Acceptance Examples

- AE1. Owner rename/delete updates list; non-owner sees safe not-found.
- AE2. Ordered source/template refs submit; expired/duplicate chips fail before provider work with safe labels; no Evidence attach affordance appears.
- AE3. Stale Settings mutation shows 409 and refreshes snapshot.
- AE4. Failed cleanup operation is visible with safe state and request ID; no retry/cancel control appears unless a contracted current-operation endpoint authorizes it.
- AE5. No passwords/tokens/private IDs in local/session storage.
- AE6. `/settings?section=provider` renders the compact HTML-guided hierarchy with correct generated fields (`kind`, `configured`, `inUse`, `version`), no dashboard card grid, and no duplicate primitive implementation.
- AE7. Admin replaces an OpenAI/Bedrock credential without rehydrating the secret, changes the active synthesis profile with If-Match, and sees a stale concurrent update preserved for review/reload.
- AE8. Ollama shows no credential action and no approved profile choices; an unconfigured credential-requiring provider cannot become the active synthesis default. The UI makes no runtime-readiness claim beyond the closed DTO.
- AE9. Embedding profiles are informational in Model Provider Settings, selectable only in the Knowledge Domain creation/deploy form, and read-only/locked for an existing domain.

### Scope Boundaries

#### In scope

- Chat rename/delete; source/template composer refs UI; provider Settings contract/parity/implementation; generated runtime-setting DTO adoption; conditional/idempotent mutation headers; approved model-profile visibility; operation history panels; component tests; evidence.

#### Deferred to Follow-Up Work

- Playwright production matrix (P12-07)
- User admin mutation UI (no contract)
- Evidence attach chips (P11-04)
- Browser model-profile create/edit/delete until a public closed-catalog projection and interaction contract are approved

#### Outside this product's identity

- Wiki/observability routes; member-selected models/providers; browser-selected runtime targets/URLs; provider model discovery outside the closed catalog.

---

## Planning Contract

### Key Technical Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| KTD1 | Use generated clients only | DRIFT-01 chat precedent |
| KTD2 | allowedActions advisory; reauthorize every mutation | Backend authority |
| KTD3 | Vitest altitude for DONE; Playwright residual P12-07 | Matches P9-04 |
| KTD4 | Treat `docs/_scratch/provider-settings-imagined.html` as visual guidance, then land a cataloged parity trio before changing live provider chrome | P9-06 HTML steers appearance; contracts/React own behavior |
| KTD5 | Keep the provider page quiet: rows and on-demand modals, not provider cards, dashboards, or always-open secret fields | Matches the compact workstation and existing Settings primitives |
| KTD6 | Separate global synthesis defaults from per-domain immutable embeddings | Preserves FR-02, A-02, A-13 and prevents per-user/model-selection drift |
| KTD7 | Do not equate `configured` with runtime-ready or mirror the private model catalog in TypeScript | Closed DTOs expose neither runtime readiness nor safe catalog choices |
| KTD8 | Conversation PATCH/DELETE send `If-Match` from `ConversationSummaryDto.version` (same helper pattern as `domains/api.ts` `ifMatchHeader`); reject missing version before call; on 428/409 preserve intent and refresh | OpenAPI requires `If-Match`; current adapters omit it |
| KTD9 | Prefer DTO `version` for If-Match when the closed response exposes it; use a narrow feature/shared helper that can also surface response ETag when contracts require header-only concurrency. Do not treat JSON-only `ceFetch` body return as sufficient for conditional Settings work, and never persist version/ETag in browser storage | `ceFetch` today drops headers; runtime/provider/model-profile DTOs already carry `version` |
| KTD10 | Attach session CSRF on every unsafe browser call through one shared path; reuse chat's `csrf_invalid` recovery. U1 must locate or introduce that accessor — BFF allowlists `x-csrf-token` but `ceFetch` does not attach it today | Avoid a second CSRF stack; Vitest mocks must not hide missing headers |
| KTD11 | Delete lifted Settings aliases (`providerKind`/`isConfigured`) and project only generated `ProviderSummaryDto` / `ModelProfileDto` / `RuntimeSettingsDto` field names | Live provider section already mounts; drift is a correctness bug |
| KTD12 | Operation history is read-only list UX from catalog GETs; retry/cancel bind only to existing documents current-operation endpoints + advisory `allowedActions` | Prevents invented historical-row mutations |

### Assumptions

- P11-02 discover/consume APIs remain green.
- P10-05 owns real Bedrock/Ollama/embedding provider packaging and staging smoke; this plan must not convert catalog presence into a production-support claim.
- Users section remains a read-only list; no mutation UI in this slice.

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Storing composer tokens | Memory-only; clear on identity change |
| Scope creep into users CRUD | Explicit out of scope |
| HTML concept mistaken for product authority | Amend normative contracts first; fixture is static appearance guidance only |
| Provider UI implies unsupported runtime readiness | Never derive readiness from `configured` or profile facts; use neutral copy and preserve the P10-05 proof boundary |
| ETag/version lost by JSON-only adapter | KTD9 feature-owned metadata helper; prefer DTO `version`; never persist in browser storage |
| Private model catalog duplicated in the browser | Keep profile rows read-only and defer browser CRUD until a closed public projection is approved |
| Unsafe mutations fail CSRF validation | KTD10: inventory must find/add one shared CSRF attach path; test valid, missing, mismatched, and refreshed tokens |
| Rename/delete adapters omit required If-Match today | KTD8 before enabling UI controls; treat as correctness gap |
| Lifted provider DTO drift (`providerKind`/`isConfigured`) | KTD11 before credential/synthesis UX polish |
| `reducto` appears in `ProviderSummaryDto.kind` | Project only contracted facts; credential action only when `requiresCredentials`; no parser-readiness claim |
| Operation-history vs current-op confusion | KTD12 + AE4 tests; reuse existing documents retry/cancel |

### System-Wide Impact

- **Surfaces:** `chat-shell` (rename/delete, ref picker, submit tokens), `settings-panel` (provider section + domains concurrency consumers), `documents` (current-op retry/cancel + source operation history), shared API transport, parity catalog (`provider-settings` plus reuse of `settings-*`, `operation-status`, `source-operation-panel`, `confirm-action-dialog`), generated OpenAPI client.
- **Failure propagation:** Missing/stale If-Match preserves intent and refreshes; never unconditional retry. CSRF refresh must not drop typed secrets or pending synthesis changes.
- **Cache/privacy:** Composer-ref tokens, credentials, ETags/versions stay memory-only; clear on logout/identity change with existing auth-store boundaries. No new local/session storage keys.
- **Parity knock-on:** `provider-settings` catalog + docs + fixture/manifest/React trio land before or with live chrome (P9-06 integrity gate).
- **Non-impact:** Users read-only list unchanged; Evidence attach deferred (P11-04); browser model-profile CRUD deferred; Playwright/visual matrix P12-07; provider packaging smoke P10-05.

---

## Implementation Units

### U1. Browser workflow inventory

**Goal:** Freeze disabled controls, provider Settings drift, CSRF/header readiness, and API readiness.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `docs/_scratch/p9-07-contracted-browser-workflows-inventory.md`

**Approach:** Call-site table covering: `chat-shell/api.ts` rename/delete missing If-Match; hard-disabled `data-testid="ref-picker"` and unused `discoverComposerRefs`; hardcoded `composerRefTokens: []` in `use-chat-shell.ts`; Settings lifted DTO field map vs generated `kind`/`configured`/`requiresCredentials`/`version`; whether a browser CSRF accessor exists (today: BFF allowlist only, `ceFetch` does not attach); conditional/idempotent header matrix; operation history GETs vs documents current-op retry/cancel; HTML guidance disposition; Evidence attach and browser profile CRUD deferrals.

**Patterns to follow:** p9-02/p9-04 inventories

**Test scenarios:**
- Test expectation: none -- inventory.

**Verification:** Every required workflow has disposition, including CSRF accessor find-or-add.

---

### U2. Chat rename/delete and composer refs

**Goal:** M-08 plus the non-Evidence portion of M-09 UI (F1, F2).

**Requirements:** R2,R3,AE1,AE2,AE5

**Dependencies:** U1

**Files:**
- Modify: `app/client/src/features/chat-shell/api.ts`
- Modify: `app/client/src/features/chat-shell/ChatShell.tsx`
- Modify: `app/client/src/features/chat-shell/use-chat-shell.ts`
- Modify: `app/client/tests/chat.test.mjs`
- Modify: `app/client/tests/chat-inspector.test.tsx`
- Create: `app/client/tests/chat-rename-delete.test.mjs` (or equivalent focused file if suite conventions prefer colocating in `chat.test.mjs`)
- Create: `app/client/tests/composer-refs.test.mjs` (or equivalent focused file)

**Approach:** Fix rename/delete adapters to send `If-Match` from conversation `version` (KTD8) before enabling UI. Preserve pending rename/delete intent across 428/409; refresh server truth; no optimistic deletion. Unlock ordered source/template discovery/attach via existing `discoverComposerRefs`; keep Evidence attach deferred; wire submit to real `composerRefTokens` while preserving drafts on recoverable failures; never persist raw tokens. Reuse `confirm-action-dialog` for delete confirmation.

**Patterns to follow:** P9-02 workbench; P11-02 contracts; `domains/api.ts` `ifMatchHeader`

**Test scenarios:**
- Happy: rename commits on the contracted action, delete uses a target-and-consequence confirmation, and both update only after server confirmation.
- Concurrency: missing/stale If-Match preserves rename/delete intent, refreshes authoritative state, and never retries unconditionally.
- Accessibility: rename supports keyboard save/cancel; delete dialog uses safe initial focus and returns focus to the logical neighboring conversation.
- Happy: ordered source/template refs attach/submit and chips preserve order.
- State: ref picker covers loading, empty, ready, refresh failure, fatal failure, disabled-with-reason, and superseded request generations.
- Accessibility: keyboard/touch picker operation, Escape focus return, named chip removal, and narrow chip wrapping.
- Error: each contracted invalid source/template ref state uses safe labels and preserves the draft.
- Privacy: no token in storage.

**Verification:** Node/Vitest tests green; adapters reject calls without version.

---

### U3. Settings concurrency and operation history

**Goal:** Shared unsafe-request, conditional/idempotent mutation handling plus safe operations UX (F4).

**Requirements:** R4,R5,AE3,AE4,AE5

**Dependencies:** U1

**Files:**
- Modify: `app/client/src/lib/api/client.ts` (and/or a narrow shared helper beside it for CSRF attach + optional metadata return)
- Modify: `app/client/src/features/settings-panel/api.ts`
- Modify: `app/client/src/features/domains/api.ts` (domain operations list wrapper if absent)
- Modify: `app/client/src/features/documents/api.ts` (source operations list wrapper if absent)
- Modify: `app/client/src/features/settings-panel/SettingsPanel.tsx` and/or domain accordion helpers for domain history UX
- Modify: `app/client/src/features/documents/DocumentsPage.tsx` for source history UX beside existing retry/cancel
- Modify: `app/client/tests/domains-settings.test.mjs`
- Modify: `app/client/tests/domains-api.test.mjs`
- Create: `app/client/tests/api-mutation-headers.test.mjs` (CSRF/If-Match/Idempotency-Key transport)
- Create: `app/client/tests/operation-history.test.mjs` (domain/source history UX)

**Approach:** Implement KTD9/KTD10: shared CSRF attach for unsafe methods; prefer DTO `version` for If-Match on provider/runtime/model-profile mutations; expose Idempotency-Key path for model-profile POST. Handle CSRF refresh and 428/409 without discarding pending intent or retained secret input. Add list wrappers for `GET /admin/domains/{domainId}/operations` and `GET /admin/domains/{domainId}/sources/{sourceId}/operations`. Keep retry/cancel on existing documents current-operation endpoints only (KTD12). U2 and U6 consume these shared transport mechanics. Reuse parity targets `operation-status` and `source-operation-panel`.

**Patterns to follow:** P2-02 ETag; P9-04 domains accordion; `domains/api.ts` `ifMatchHeader`

**Test scenarios:**
- Happy: matching If-Match succeeds.
- Happy: stable Idempotency-Key replays model-profile create without duplicate work.
- Security: valid CSRF succeeds; missing/mismatched CSRF fails closed; refreshed CSRF retries safely without duplicating a mutation.
- Error: missing precondition never silently retries as unconditional mutation.
- Error: stale_revision preserves intent, refreshes server truth, and lets the admin review/retry.
- State: operation history covers loading, empty, ready, refreshing/stale, refresh-error, fatal, forbidden, accepted/reconciling, failed, retrying, cancelling, and cancelled where reachable from approved DTOs.
- Boundary: historical failed cleanup shows state/request ID but no action; current-operation retry/cancel appears only when a contracted endpoint and allowedActions permit it.
- Accessibility: progress/action labels remain keyboard/touch reachable at narrow widths.
- Privacy: ETag/version and mutation intent are not persisted in local/session storage.

**Verification:** Focused frontend tests green.

---

### U5. Provider Settings contracts and parity target

**Goal:** Approve the compact provider/model Settings interaction and visual target before live implementation (F3, F5 visual).

**Requirements:** R8,R10,AE6,AE8,AE9

**Dependencies:** U1

**Files:**
- Modify: `docs/frontend/component-contracts.md`
- Modify: `docs/frontend/interaction-state-catalog.md`
- Modify: `docs/frontend/accessibility-and-responsive-contract.md`
- Modify: `docs/frontend/ui-parity-contract.md`
- Modify: `docs/frontend/ui-parity-catalog.md`
- Create: `app/client/tests/parity/fixtures/provider-settings.html`
- Create: `app/client/tests/parity/manifests/provider-settings.json`
- Create: `app/client/tests/parity/react/provider-settings.test.tsx`
- Guidance input: `docs/_scratch/provider-settings-imagined.html`

**Approach:** Convert the scratch concept into an approved provider Settings target without treating its sample data as contract truth. Preserve compact grouped rows, semantic status, dark/light token use, and the normative Settings section-list/detail behavior: persistent section navigation at 1024 px and above, accessible section navigation/drawer behavior below 1024 px, and stacked row content where required. Add only interaction states the static concept cannot show: loading, stale/refresh, credential-modal validation, safe failure with request ID, conflict, forbidden/not-found, and unconfigured-provider states. Use neutral profile/configuration copy; do not encode runtime readiness. Reuse existing primitives (`settings-nav`, `settings-group`, `settings-row`, `button`, `select`, `status-pill`, `input`, `ui-modal`) and record any genuinely missing composition contract before creating it.

**Patterns to follow:** P9-04 Settings Domain accordion amendment; P9-06 catalog/fixture/manifest/React parity trio.

**Test scenarios:**
- Happy: fixture and React target agree on provider rows, global synthesis selector, and compact embedding-profile facts in both themes.
- Responsive: 320×640, 768×1024, and 1024×768 verify the normative section navigation transition; 200%/400% zoom introduces no horizontal viewport push and retains keyboard order.
- Accessibility: provider status is not color-only; credential modal labels/describes inputs, associates validation, moves focus to the first error, traps and returns focus, and exposes busy state without disabling cancellation.
- Scope: target contains no member model picker, runtime URL, raw provider payload, secret value, or unsupported free-form model entry.
- Contract: fixture never represents `configured` as runtime-ready and does not introduce browser profile CRUD.

**Verification:** Catalog/docs/files integrity gate and provider-settings React parity test pass; visual review shows no duplicate primitive or dashboard-card grammar.

---

### U6. Provider credentials, profile visibility, and runtime defaults

**Goal:** Implement the contracted administrator Model Provider section against generated DTOs and conditional mutations (F3, F5).

**Requirements:** R4,R8,R9,R10,AE3,AE5,AE6,AE7,AE8,AE9

**Dependencies:** U3,U5

**Files:**
- Modify: `app/client/src/features/settings-panel/api.ts`
- Modify or split: `app/client/src/features/settings-panel/SettingsPanel.tsx` (`ProviderSection` already mounts at `/settings?section=provider`)
- Create: `app/client/tests/settings-provider.test.mjs`
- Modify: `app/client/tests/domains-settings.test.mjs` only if shared Settings fixtures require it

**Approach:** Apply KTD11: remove lifted `ProviderStatus`/`ModelProfile`/`RuntimeSettings` aliases; use generated DTO field names (`kind`, `configured`, `requiresCredentials`, `displayName`, `inUse`, `version`). Keep credentials write-only in an on-demand modal; after mutation clear the field and reload the authoritative snapshot with If-Match from DTO version (KTD9). Offer active synthesis choices from snapshot profiles; require `configured` only where credentials are required; describe deployment-wide effect; never label runtime-ready. Render embedding profiles as compact read-only facts; keep selection in Knowledge Domain creation/deploy. No browser profile CRUD. Ollama: no credential action. `reducto`: project contracted facts only; no invented credential/model flows. Members never see provider chrome.

**Patterns to follow:** U3 conditional mutation adapter; U5 parity target; P9-04 server-truth Settings mutation pattern; generated client usage from P9-02.

**Test scenarios:**
- Happy: backend `kind`/`configured`/`inUse` fields render correct provider/profile states without handwritten DTO drift.
- Happy: OpenAI/Bedrock credential replacement submits once with If-Match, never displays the stored value, clears typed secret on completion, and reloads the snapshot.
- Happy: changing active synthesis updates new-work default while copy states that in-flight work keeps its frozen configuration.
- Boundary: model profiles are read-only on this page; existing domains show the immutable embedding profile and no replacement control.
- Boundary: Ollama has no credential action; unconfigured credential-requiring providers cannot become active; no UI state claims runtime readiness; `reducto` does not invent unsupported credential UX.
- Error: 428/409 retains safe intent and presents refresh/retry; 404/403 use the contracted indistinguishable/safe state; failures show request ID without raw exception data.
- Accessibility: credential modal validation, busy/cancel behavior, focus trap/return, and keyboard/touch operation match U5.
- Privacy: no credential, model payload, runtime endpoint, private ID, prompt, or ETag is written to browser storage or logs.

**Verification:** Typecheck proves generated DTO alignment; focused API/state/component tests prove A-01/A-02/A-13 within the public DTO boundary and the static parity target remains visually representative.

---

### U4. Evidence and tracker

**Goal:** Close P9-07.

**Requirements:** R7,R8,R9,R10

**Dependencies:** U2,U3,U5,U6

**Files:**
- Create: `docs/_scratch/p9-07-contracted-browser-workflows-evidence.md`
- Modify: `docs/master-build-plan.md`

**Approach:** Record residuals for P12-07 Playwright and P10-05 real provider smoke, preserve the provider HTML concept/final fixture relationship, and record browser profile CRUD/Evidence attach as deferred contract work. Mark P9 phase DONE if no other open P9 tasks.

**Patterns to follow:** p9-04 evidence

**Test scenarios:**
- Test expectation: none -- docs.

**Verification:** Tracker DONE with residuals.

---

## Verification Contract

- Frontend typecheck + focused Vitest/node tests (`chat.test.mjs`, rename/delete/ref-picker coverage, domains/settings/provider/header tests).
- Provider Settings contract/catalog/files/parity trio gate.
- Generated-client drift check; no handwritten substitute provider/model/runtime DTO.
- No Playwright required for P9-07 DONE.
- Privacy storage/log checks for composer tokens, credentials, provider payloads, private IDs, and ETags.
- Focused two-admin Settings conflict proof for credential and active-synthesis mutations; mutation-header adapter tests cover profile POST/PATCH/DELETE even though browser profile CRUD is deferred.
- Narrow responsive/theme/accessibility review for the provider target; production visual/browser matrix remains P12-07.

## Definition of Done

All active requirements (R1–R5 and R7–R10) and AE1–AE9 are satisfied at component altitude; the provider Settings contracts and parity trio are approved; generated DTOs and the endpoint-specific CSRF/If-Match/Idempotency-Key matrix govern unsafe workflows; immutable embedding selection remains in the Knowledge Domain creation/deploy form; Evidence attach and browser profile CRUD stay deferred; P9-07 is DONE; P10-05 provider smoke and P12-07 Playwright/visual residuals are explicit.

## Sources & Research

- docs/frontend/chat-and-evidence-workbench.md
- docs/frontend/route-and-workspace-spec.md
- docs/frontend/implementation-slices.md FE-04/FE-06/FE-10
- docs/contracts/http-api-catalog.md
- docs/contracts/dto-schema-catalog.md
- docs/interaction-behavior-prd.md M-08/M-09/A-01/A-02/A-03/A-07/A-09/A-10/A-13
- docs/_scratch/provider-settings-imagined.html
- docs/master-build-plan.md P9-07
- docs/_scratch/legacy-gap-plan-bundle.md
- Live adapters audited 2026-07-28: `app/client/src/features/chat-shell/*`, `settings-panel/*`, `documents/api.ts`, `domains/api.ts`, `lib/api/client.ts`, `lib/api/generated/openapi.ts`
