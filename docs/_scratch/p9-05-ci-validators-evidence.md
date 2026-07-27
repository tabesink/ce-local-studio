# P9-05 CI Validators Evidence

Date: 2026-07-27  
Slice: P9-05  
Status: DONE (local structure + BFF trust/cache half; FE-01 / P10 / P12 residuals explicit)  
Plan: `docs/plans/2026-07-27-012-feat-p9-05-ci-validators-plan.md`  
Inventory: `docs/_scratch/p9-05-ci-validators-inventory.md`

## What landed

- Inventory froze thick routes, `state/` orphan, BFF header gaps, handwritten auth DTO forks, and residual mega-kit allowlist reuse.
- BFF (`bff-proxy.ts`) aligned to `frontend-security-boundary.md`: exclusive step-3 request allowlist; browser `Origin` copy; server-derived `X-CE-Public-Host` / `X-CE-Public-Proto` / opaque hashed `X-CE-Client-Bucket`; forward `Idempotency-Key` + `X-Client-Request-Id`; multi-`Set-Cookie` preservation; forced `Cache-Control: private, no-store, no-transform`; abort + Range/`If-Range` retained.
- Structure gates under `app/client/tests/structure/`: import-direction, thin-routes, server-browser-boundary, generated-contract-homes (plus existing ui-ownership).
- Login thinned to `features/auth/LoginPage`; auth store relocated to `features/auth/auth-store`; `src/state/` removed; `types/auth.ts` aliases `CurrentUserDto` / `LoginRequest`; Settings users UI uses `displayName` / `disabled`.
- design-kit `SHARED_UI_IMPORT_ALLOWLIST` reused — no FE-01 demolition.

## Commands

```text
cd app/client
node --experimental-strip-types --test `
  tests/bff-proxy.test.mjs `
  tests/design-kit-contract.test.mjs `
  tests/structure/**/*.test.ts
npm run typecheck
```

Result (2026-07-27): 28 structure/BFF/design-kit tests passed; typecheck passed.

Interaction cases covered (local half): M-01 / C-05 (BFF strip/emit/cache). Not claimed: C-03 two-user cache.

## Residuals / non-claims

| Residual | Owner |
| --- | --- |
| FE-01 mega-kit demolition | FE-01 |
| Compose `CONTEXT_ENGINE_PUBLIC_ORIGIN` topology green | P10 |
| Deployed-ingress negatives / direct FastAPI denial | P10/P12 |
| Two-user / logout / BFCache browser cache isolation | P12 |
| Browser CSRF bootstrap product fix | named residual |
| Middleware wholesale auth rewrite | DRIFT-05 residual (not DONE blocker after BFF local half) |

## Tracker closure

- `docs/master-build-plan.md`: P9-05 DONE; Phase P9 DONE.
- `docs/brownfield-refactor-register.md`: DRIFT-05 / DRIFT-19 **local half DONE**; deployed residuals P10/P12.

## Artifact revision

Branch: `feat/p9-05-ci-validators`  
Base HEAD at branch creation: `1b906c9`
