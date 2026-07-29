# Playwright E2E (P12-07)

Production-boundary browser proofs against the Compose stack (Next production build / BFF / FastAPI / worker / PostgreSQL 16 / object store).

## Lanes

| Script | Tag | When |
| --- | --- | --- |
| `npm run test:e2e:pr-fast` | `@pr-fast` | Every PR (named CI job `verify-playwright-pr-fast`) |
| `npm run test:e2e:release` | `@release` | Gated live/capacity lane (U4); requires `CE_P12_07_RELEASE=1` or specs skip |
| `npm run release:capacity -- check\|unit` | n/a | Budget freeze + in-process L/L+1 (`CE_P12_07_RELEASE=1`) |
| `npm run test:visual-gate -- check\|enforce` | n/a | Visual parity manifest schema / fail-closed approve+PNG gate (U6) |

Default `npm run test:e2e` runs the PR-fast set (includes axe golden routes). `@release` and `visual-gate enforce` are never part of `scripts/verify.sh` until baselines are `approved`.

## Prerequisites

1. Start the local demo stack and wait until healthy:

   ```bash
   bash scripts/dev.sh
   # or:
   cd app && docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d
   ```

   Recreate `.env.stack.local` from `app/.env.stack.example`. Set
   `CE_STACK_PUBLIC_ORIGIN=http://127.0.0.1:<STACK_FRONTEND_PORT>` (use `127.0.0.1`, not `localhost`).
   Include `CE_GRAPH_REF_KEY` (≥32 chars).

2. `CE_ADMIN_USERNAME` / `CE_ADMIN_PASSWORD` for bootstrap (Compose one-shot only).
3. Optional: `PLAYWRIGHT_BASE_URL` (default `http://127.0.0.1:3000`; must match public origin).
4. Optional actors: `CE_E2E_MEMBER_*`, `CE_E2E_NOAH_*`.
5. One-time: `npx playwright install chromium` from `app/client`.

Global setup fails fast if `/login` is unreachable, requires `127.0.0.1`, seeds fixture actors (Ava/Mina/Noah jars via separate contexts), and indexes the pilot domain (including `doc_pump_manual.pdf` when present under `app/tests/fixtures/documents/`).

Settings domains F3 uses live server DTOs only — no intercepted product responses.

## Commands

```bash
cd app/client
npm run test:e2e:pr-fast
npm run test:e2e:release
npm run test:e2e:headed
npx playwright test tests/e2e/graph-workbench.spec.ts --grep @pr-fast
```

## Matrix ownership (inventory)

PR-fast specs cover E2E-M01 (auth/CSRF/BFCache), isolation/C04, graph M14–M17 smoke, Settings domains F3, M-11 open-panel half, plus retained pilot/documents/evidence paths. Visual baseline comparison hardening is U6; capacity/live pipeline is U4 `@release`.

## Artifacts

- Seed metadata: `tests/e2e/artifacts/seed.json` (no secrets)
- Screenshots: `tests/e2e/artifacts/*.png`
- Playwright output: `test-results/`, `playwright-report/` (gitignored; traces on failure)

## Port overrides

```bash
STACK_API_PORT=8012 STACK_FRONTEND_PORT=3010 docker compose --env-file .env.stack.local -f compose.stack.yml up --build -d
cd app/client && PLAYWRIGHT_BASE_URL=http://127.0.0.1:3010 npm run test:e2e:pr-fast
```
