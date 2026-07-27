# Playwright E2E (F-009 pilot happy path)

Live-stack browser proof for login, direct chat, domain RAG + Evidence Panel, logout, documents PDF/text preview (admin + member read-only), and the DESIGN screenshot matrix.

Settings domains production-boundary acceptance (F3 / R12 / AE1) is **P12-07** (domains implementation **P9-04**). It is not a P9-01 exit gate. Do not add intercepted or mocked Settings-domains acceptance specs under this tree for factory readiness.

## Prerequisites

1. Start the runnable stack and wait until healthy:

   ```bash
   docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d
   ```

2. Ensure `.env.stack.local` has `CE_ADMIN_USERNAME` / `CE_ADMIN_PASSWORD` (same values the stack seeds).
3. Optional: `PLAYWRIGHT_BASE_URL` (default `http://127.0.0.1:3000`).
4. Optional member overrides: `CE_E2E_MEMBER_USERNAME` / `CE_E2E_MEMBER_PASSWORD` (defaults used by seed via `docker compose exec api`).
5. One-time browser install: `npx playwright install chromium` from `app/client`.

Global setup fails fast if `/login` is unreachable, seeds one indexed Knowledge Domain plus a PDF preview fixture via the frontend `/api/v1` proxy, and ensures the E2E member user exists.

## Commands

```bash
cd app/client
npm run test:e2e
npm run test:e2e:headed
# focused documents preview:
npx playwright test tests/e2e/documents-preview.spec.ts
```

## Artifacts

- Seed metadata: `tests/e2e/artifacts/seed.json` (no secrets)
- Screenshots: `tests/e2e/artifacts/*.png`
- Playwright output: `test-results/`, `playwright-report/`

All of the above are gitignored. Review screenshots locally for AC-008; do not commit filled password fields or secrets.

If host ports `8000`/`3000` are already taken, override when starting compose and point Playwright at the frontend port:

```bash
STACK_API_PORT=8012 STACK_FRONTEND_PORT=3010 docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d
cd app/client && PLAYWRIGHT_BASE_URL=http://127.0.0.1:3010 npm run test:e2e
```
