import type { FullConfig } from "@playwright/test";
import { request } from "@playwright/test";
import { ensureFixtureActors } from "./helpers/actors";
import { seedIndexedDomain } from "./helpers/stack-seed";

async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0]?.use?.baseURL ?? "http://127.0.0.1:3000";

  if (!baseURL.includes("127.0.0.1")) {
    throw new Error(
      `Playwright global setup: public origin must use 127.0.0.1 (got ${baseURL}). ` +
        "Align PLAYWRIGHT_BASE_URL with CE_STACK_PUBLIC_ORIGIN.",
    );
  }

  const probe = await request.newContext({ baseURL });
  try {
    const loginPage = await probe.get("/login");
    if (!loginPage.ok()) {
      throw new Error(
        `Playwright global setup: ${baseURL}/login returned HTTP ${loginPage.status()}. ` +
          "Start the stack first: bash scripts/dev.sh (or compose.stack.yml).",
      );
    }
  } catch (error) {
    if (error instanceof Error && error.message.includes("Playwright global setup")) {
      throw error;
    }
    throw new Error(
      `Playwright global setup: ${baseURL}/login is unreachable. ` +
        "Start the stack first: bash scripts/dev.sh (or compose.stack.yml).",
      { cause: error },
    );
  } finally {
    await probe.dispose();
  }

  ensureFixtureActors();
  await seedIndexedDomain(baseURL);
}

export default globalSetup;
