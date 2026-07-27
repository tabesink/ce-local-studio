# P9-05 CI Validators Inventory

Date: 2026-07-27  
Status: complete for U1 inventory only; no gate/BFF mutations in this record.  
Plan: `docs/plans/2026-07-27-012-feat-p9-05-ci-validators-plan.md`  
Authority: `docs/master-build-plan.md` P9-05; `docs/architecture/frontend-security-boundary.md`; `docs/frontend/source-adaptation-map.md`; P9-01 ownership evidence.

## Disposition legend

| Value | Meaning |
| --- | --- |
| `migrate` | Change in this slice so validators pass |
| `allowlist-shrink` | Keep allowlisted; ban new offenders |
| `defer-FE-01` | Residual mega-kit sole home until FE-01 |
| `P10` | Compose / deployed topology residual |
| `P12` | Deployed cache / two-user / BFCache residual |
| `retain` | Already compliant; characterization only |

## Product routes (`page.tsx` / `not-found.tsx`)

| Path | Shape today | Disposition |
| --- | --- | --- |
| `src/app/page.tsx` | thin redirect | `retain` |
| `src/app/chat/page.tsx` | thin → shell + ChatShell | `retain` |
| `src/app/documents/page.tsx` | thin → shell + DocumentsPage | `retain` |
| `src/app/settings/page.tsx` | thin → shell + SettingsPanel | `retain` |
| `src/app/database-visualize/page.tsx` | thin → shell + GraphPage | `retain` |
| `src/app/forbidden/page.tsx` | thin → shell + PageState alias | `retain` (alias via design-kit allowlist path) |
| `src/app/not-found.tsx` | thin → shell + PageState alias | `retain` |
| `src/app/login/page.tsx` | **thick** form + `useAuthStore` | `migrate` → `features/auth` |

Non-page app chrome (not thin-route targets; shrink-only exception):

| Path | Notes | Disposition |
| --- | --- | --- |
| `src/app/providers.tsx` | bootstrap + unauthorized handler + AppearanceProvider | `allowlist-shrink` (non-page) |
| `src/app/layout.tsx` | root layout | `allowlist-shrink` (non-page) |

## `state/` and auth DTO forks

| Offender | Fact | Disposition |
| --- | --- | --- |
| `src/state/auth-store.ts` | Sole orphan layer; 7 importers | `migrate` → `features/auth/auth-store.ts` |
| Importers | login, providers, AppLayout, DocumentsPage, NavigationSidebar (+ hook), SettingsPanel | `migrate` import paths |
| `src/types/auth.ts` | Handwritten `CurrentUser` (`username`/`isDisabled`) + `SessionUserResponse` with `session`; OpenAPI has `CurrentUserDto` (`displayName`/`disabled`) | `migrate` to generated aliases + consumer field rename |

## `CONTEXT_ENGINE_*` locality

| File | Usage | Disposition |
| --- | --- | --- |
| `src/lib/server/bff-proxy.ts` | `API_BASE`, `PUBLIC_ORIGIN` | `retain` (server) |
| `src/middleware.ts` | `API_BASE` health rewrite | `retain` (server) |
| Browser modules | none observed | `retain` — gate must keep absence |

## BFF trust gaps vs `frontend-security-boundary.md`

| Gap | Live | Target (U2) |
| --- | --- | --- |
| Trust headers | Emits `x-forwarded-host/proto` | Emit `X-CE-Public-Host` / `X-CE-Public-Proto` / `X-CE-Client-Bucket` |
| Request allowlist | Extra: `accept-language`, `if-none-match`, `x-request-id`; missing: `Idempotency-Key`, `X-Client-Request-Id` | Exclusive step-3 list + body/method/path/query plumbing |
| Origin | Overwrites to public origin | Copy browser `Origin` when present (FastAPI validates) |
| Caller `X-CE-*` / forwarding | Partially stripped | Strip all contracted forbidden; never accept browser bucket |
| Client bucket | Absent | Opaque SHA-256-derived local recipe (see U2); injectable in tests; P10 hardens ingress |
| Multi-`Set-Cookie` | `headers.get` collapses | Preserve via `getSetCookie()` |
| Cache | Forces `private, no-store, no-transform` | `retain` + keep tests |
| Abort / Range / If-Range | Proven | `retain` |

## Shared allowlist reuse (`defer-FE-01`)

Reuse exactly (monotonic shrink) from `app/client/tests/design-kit-contract.test.mjs`:

```text
components/ui/index.ts
components/ui/AppLogo.tsx
features/documents/DocumentsPage.tsx
features/documents/PdfPreview.tsx
features/graph/GraphPage.tsx
features/navigation-sidebar/NavigationSidebar.tsx
features/settings-panel/SettingsRow.tsx
features/user-preferences/PreferencesPanel.tsx
```

Plus ui-ownership alias rules for Button/Input/StatusPill/AppShell/SettingsRow. No FE-01 demolition in P9-05.

## Layer map for import-direction gate

| Layer | Paths | May import |
| --- | --- | --- |
| app | `src/app/**` | features, ui, allowlisted components aliases, lib (browser-safe), `lib/server` only from API route |
| features | `src/features/**` | features (peers), lib (browser-safe), ui, allowlisted components/_shared |
| lib (browser) | `src/lib/**` except `server/` | lib (non-server), ui, types, generated |
| lib/server | `src/lib/server/**` | lib, types — not features/app |
| ui | `src/ui/**` | ui only (no features/app) |
| components / _shared | residual | design-kit allowlist only for new edges |

Cross-feature imports observed and **allowed** (examples): shell→nav, nav→chat-shell/api, chat-shell→domains, documents→domains, settings→preferences/domains.

## Planned validator files

| File | Covers |
| --- | --- |
| `tests/structure/import-direction.test.ts` | Layer edges, `.references` ban, browser↛server |
| `tests/structure/thin-routes.test.ts` | page/not-found shells; login migrate; providers/layout exception |
| `tests/structure/server-browser-boundary.test.ts` | `CONTEXT_ENGINE_*` locality |
| `tests/structure/generated-contract-homes.test.ts` | generated path + no handwritten public DTO substitutes |
| `tests/bff-proxy.test.mjs` | U2 trust/cache/Set-Cookie |

## Residuals (must not absorb into DONE)

| Residual | Owner |
| --- | --- |
| FE-01 mega-kit demolition | FE-01 |
| Compose `CONTEXT_ENGINE_PUBLIC_ORIGIN` topology green | P10 |
| Deployed-ingress negatives / direct FastAPI denial | P10/P12 |
| Two-user / logout / BFCache browser cache isolation | P12 |
| Browser CSRF bootstrap product fix | named residual (not P9-05) |
| Middleware wholesale auth rewrite | DRIFT-05 residual text clarify; not DONE blocker after BFF local half |
