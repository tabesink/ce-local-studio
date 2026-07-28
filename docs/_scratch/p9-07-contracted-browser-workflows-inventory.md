# P9-07 Contracted Browser Workflows Inventory

Date: 2026-07-28  
Status: complete for P9-07 U1 inventory. Not a release completion record.

Authority: `docs/master-build-plan.md` P9-07; `docs/plans/2026-07-28-010-feat-p9-07-contracted-browser-workflows-plan.md`; P9-02/P9-04/P9-06/P11-02 closed deps; FE-04/FE-06/FE-10; interaction M-08/M-09/A-01/A-02/A-03/A-07/A-09/A-10/A-13.

## Surfaces inventoried

| Surface | Path | Disposition |
| --- | --- | --- |
| Chat API | `app/client/src/features/chat-shell/api.ts` | **modify** — add `If-Match` from conversation `version` to rename/delete; keep `discoverComposerRefs` and wire UI |
| Chat shell UI | `app/client/src/features/chat-shell/ChatShell.tsx` | **modify** — enable rename/delete controls; unlock source/template ref picker (`data-testid="ref-picker"` currently hard-disabled) |
| Chat hook | `app/client/src/features/chat-shell/use-chat-shell.ts` | **modify** — stop hardcoding `composerRefTokens: []`; memory-only ref chips; clear on identity change; already recognizes `csrf_invalid` |
| Settings API | `app/client/src/features/settings-panel/api.ts` | **replace** lifted `ProviderStatus`/`ModelProfile`/`RuntimeSettings` (`providerKind`/`isConfigured`) with generated DTOs; add If-Match / Idempotency-Key paths |
| Settings panel | `app/client/src/features/settings-panel/SettingsPanel.tsx` | **modify** — rewrite `ProviderSection` (already mounts at `?section=provider`); keep users read-only |
| Domains API | `app/client/src/features/domains/api.ts` | **extend** — add `GET .../operations` list wrapper; reuse `ifMatchHeader` pattern |
| Documents API | `app/client/src/features/documents/api.ts` | **extend** — add source operations list wrapper; retain current-op retry/cancel |
| Documents page | `app/client/src/features/documents/DocumentsPage.tsx` | **modify** — operation-history UX beside existing retry/cancel |
| Shared fetch | `app/client/src/lib/api/client.ts` | **modify** — attach CSRF on unsafe methods; optional metadata helper for ETag when needed |
| Auth API | `app/client/src/lib/api/auth.ts` | **extend** — CSRF bootstrap via `GET /auth/csrf` if not already covered by shared accessor |
| BFF proxy | `app/client/src/lib/server/bff-proxy.ts` | **retain** — already allowlists `x-csrf-token` |
| Generated OpenAPI | `app/client/src/lib/api/generated/openapi.ts` | **retain** — authority for DTO field names and required headers |
| Provider HTML guidance | `docs/_scratch/provider-settings-imagined.html` | **guidance only** — promote approved look via parity fixture in U5 |
| Parity primitives | `settings-nav`, `settings-group`, `settings-row`, `button`, `select`, `status-pill`, `input`, `ui-modal`, `confirm-action-dialog`, `operation-status`, `source-operation-panel` | **reuse** — do not duplicate |
| Provider parity trio | absent | **create in U5** |
| Users section | `SettingsPanel` `UsersSection` | **retain read-only** — no mutation UI |

## Call-site gaps (must fix)

| Workflow | Live state | Contracted / plan target |
| --- | --- | --- |
| Rename conversation | `renameConversation` PATCH without `If-Match`; no UI control | `If-Match` from `ConversationSummaryDto.version`; owner UI + 428/409 intent preserve (M-08) |
| Delete conversation | `deleteConversation` DELETE without `If-Match`; no UI control | Same + confirm dialog (`confirm-action-dialog`) |
| Composer refs | Ref picker disabled; `discoverComposerRefs` unused; submit always `composerRefTokens: []` | Unlock source/template discover/attach; Evidence attach **deferred** (P11-04) |
| CSRF attach | `ceFetch` / `postSse` send cookies but **no** `X-CSRF-Token`; no browser accessor found; BFF allowlists header; `GET /auth/csrf` exists in OpenAPI | Shared transient accessor (cookie/`csrfToken`); attach on every unsafe method (KTD10) |
| Provider DTOs | Handwritten `providerKind` / `isConfigured` | Generated `kind` / `configured` / `requiresCredentials` / `displayName` / `version` |
| Provider credential PUT | No `If-Match` | `If-Match` from provider `version` (A-01) |
| Runtime settings PATCH | No `If-Match` | `If-Match` from `RuntimeSettingsDto.version` (A-13) |
| Model-profile POST/PATCH/DELETE | Present in adapter; browser CRUD **deferred** | Header matrix still tested at adapter altitude; UI stays read-only (KTD11/KTD7) |
| Domain operations history | OpenAPI `GET /admin/domains/{id}/operations` — **no** feature wrapper/UI | Read-only history list + safe request IDs |
| Source operations history | OpenAPI `GET .../sources/{id}/operations` — **no** feature wrapper/UI | Same; retry/cancel remain current-op only (documents) |
| Current-op retry/cancel | Wired in `documents/api.ts` + DocumentsPage | **retain**; do not invent historical-row actions |
| `reducto` provider kind | In generated `ProviderSummaryDto.kind` | Project contracted facts only; credential action only if `requiresCredentials` |
| Embedding lock | Domains accordion shows locked embedding facts (P9-04) | Keep selection in domain create/deploy; Model Provider shows compact read-only list |

## Mutation header matrix

| Endpoint | Required headers (catalog/OpenAPI) | Live client |
| --- | --- | --- |
| `PATCH /conversations/{id}` | `If-Match`, CSRF | CSRF missing; If-Match missing |
| `DELETE /conversations/{id}` | `If-Match`, CSRF | CSRF missing; If-Match missing |
| `PUT /admin/runtime-settings/providers/{kind}` | `If-Match`, CSRF | CSRF missing; If-Match missing |
| `PATCH /admin/runtime-settings` | `If-Match`, CSRF | CSRF missing; If-Match missing |
| `POST /admin/runtime-settings/model-profiles` | `Idempotency-Key`, CSRF | CSRF missing; Idempotency-Key missing |
| `PATCH /admin/runtime-settings/model-profiles/{id}` | `If-Match`, CSRF | CSRF missing; If-Match missing |
| `DELETE /admin/runtime-settings/model-profiles/{id}` | CSRF (+ contracted headers only) | CSRF missing |
| Domain/source current-op POST retry/cancel | CSRF (+ If-Match where catalog requires) | Partial If-Match on some cancels; CSRF missing |

## Explicit deferrals

| Item | Owner |
| --- | --- |
| Evidence attach chips / suggest-and-confirm | P11-04 (product DEFER) |
| Browser model-profile create/edit/delete | Blocked until public closed-catalog projection + interaction contract |
| User admin mutation UI | No approved contract |
| Playwright / production visual matrix | P12-07 |
| Real Bedrock/Ollama/embedding packaging smoke | P10-05 |
| Claiming `configured` == runtime-ready | Forbidden; P10-05 owns support proof |

## HTML guidance disposition

| Artifact | Role |
| --- | --- |
| `docs/_scratch/provider-settings-imagined.html` | Non-normative visual guidance only |
| `app/client/tests/parity/fixtures/provider-settings.html` (+ manifest + React test) | Approved static appearance target after U5 contract amendment |
| Live `ProviderSection` | Must match approved target after U5/U6; no dashboard card grid |

## U1 exit checklist

- [x] Rename/delete, ref picker, CSRF, provider DTO, operation history dispositions recorded
- [x] Mutation header matrix recorded
- [x] Evidence attach + browser profile CRUD + users CRUD deferred explicitly
- [x] CSRF accessor marked **find-or-add** (absent today; U3 owns shared path)
- [x] Provider HTML guidance disposition recorded

U1 complete — proceed to U2/U3/U5 per plan dependencies.
