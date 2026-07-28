# P9-07 Contracted Browser Workflows — Evidence

Date: 2026-07-28  
Branch: `feat/p9-07-contracted-browser-workflows`  
Plan: `docs/plans/2026-07-28-010-feat-p9-07-contracted-browser-workflows-plan.md`  
Inventory: `docs/_scratch/p9-07-contracted-browser-workflows-inventory.md`

## Scope delivered

| Unit | Outcome |
| --- | --- |
| U1 | Inventory frozen (CSRF find-or-add, If-Match gaps, DTO drift, deferrals) |
| U2 | Conversation rename/delete with `If-Match`; source/template composer-ref picker + memory-only chips; Evidence attach deferred |
| U3 | Shared CSRF attach + refresh on `ceFetch`/`postSse`; settings If-Match/Idempotency-Key adapters; domain/source operation-history lists (read-only) |
| U5 | Provider Settings contracts amended; `provider-settings` parity trio + catalog register |
| U6 | Live `/settings?section=provider` uses generated DTOs, credential modal, synthesis select, embedding facts |
| U4 | This evidence + tracker update |

## Verification run (component altitude)

```text
cd app/client
npx tsc --noEmit
node --experimental-strip-types --test \
  tests/api-mutation-headers.test.mjs \
  tests/operation-history.test.mjs \
  tests/chat.test.mjs \
  tests/chat-rename-delete.test.mjs \
  tests/composer-refs.test.mjs \
  tests/settings-provider.test.mjs \
  tests/domains-api.test.mjs \
  tests/domains-settings.test.mjs \
  tests/structure/parity-catalog.test.ts
npx vitest run tests/parity/react/provider-settings.test.tsx
```

Results: typecheck clean; focused node + Vitest suites green at close of this slice.

## Residuals

| Residual | Owner |
| --- | --- |
| Production-boundary Playwright / visual matrix / two-user cache | P12-07 |
| Real Bedrock/Ollama/embedding packaging smoke | P10-05 |
| Evidence attach chips | P11-04 (product DEFER) |
| Browser model-profile create/edit/delete | Blocked until public closed-catalog projection |

## Privacy / authority checks

- Composer-ref tokens and credentials remain memory-only (no local/session storage writes in chat/settings adapters).
- Provider UI projects `configured` / profile facts only; no runtime-readiness claim.
- Historical operation rows have no invented retry/cancel; current-op actions remain on documents admin panel.
- `docs/_scratch/provider-settings-imagined.html` remains non-normative guidance; approved fixture is `app/client/tests/parity/fixtures/provider-settings.html`.

## Tracker disposition

Mark **P9-07 DONE**. Phase **P9 DONE** if no other open P9 tasks remain (P9-01..P9-06 already DONE).
